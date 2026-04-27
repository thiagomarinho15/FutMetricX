"""Worker 1 — Seed player profiles from API-Football + TheSportsDB.

Run once per competition to populate the players table with identity data,
photos, and bio text. Respects API-Football 100 req/day free tier limit.
"""
import logging
import time

from ..models import db, Competition, Team, Player
from ..clients import api_football, thesportsdb
from ..utils.player_utils import normalize_player_name

from ..season_config import CURRENT_SEASON_YEAR as CURRENT_SEASON

logger = logging.getLogger(__name__)


def run(competition_name: str | None = None) -> int:
    """Seed players for all competitions (or a specific one if named)."""
    query = Competition.query
    if competition_name:
        query = query.filter_by(name=competition_name)
    competitions = query.all()

    total = 0
    for comp in competitions:
        try:
            total += _seed_competition(comp)
        except Exception as e:
            logger.error("player_seed_worker comp %d (%s): %s", comp.id, comp.name, e)

    db.session.commit()
    logger.info("player_seed_worker: done — %d players seeded/updated", total)
    return total


def _seed_competition(comp: Competition) -> int:
    logger.info("Seeding competition: %s", comp.name)
    teams = Team.query.filter_by(competition_id=comp.id, source_name='api-football').all()
    added = 0
    for team in teams:
        if not team.source_id:
            continue
        added += _seed_team(team)
        time.sleep(0.5)  # stay well within 100 req/day
    return added


def _seed_team(team: Team) -> int:
    blocks = api_football.get_squad(int(team.source_id), CURRENT_SEASON)
    if not blocks:
        return 0

    players_data = []
    for block in blocks:
        players_data.extend(block.get('players', []))

    added = 0
    for p_data in players_data:
        try:
            added += _upsert_player(p_data, team)
        except Exception as e:
            logger.warning("player_seed_worker player %s: %s", p_data.get('name'), e)
    db.session.flush()
    return added


def _upsert_player(p_data: dict, team: Team) -> int:
    source_id = str(p_data.get('id', ''))
    if not source_id:
        return 0

    player = Player.query.filter_by(source_id=source_id, source_name='api-football').first()
    is_new = player is None

    if is_new:
        player = Player(source_id=source_id, source_name='api-football')
        db.session.add(player)

    player.name = p_data.get('name', '')
    player.name_full = p_data.get('name', '')
    player.age = p_data.get('age')
    player.position = p_data.get('position', '')
    player.team_id = team.id
    photo_url = p_data.get('photo')
    if photo_url:
        player.photo_url_apifootball = photo_url

    # Enrich from TheSportsDB (bio + cutout photo)
    _enrich_from_sportsdb(player)

    return 1 if is_new else 0


def _enrich_from_sportsdb(player: Player) -> None:
    if player.bio_text and player.photo_url_sportsdb_cutout:
        return  # already enriched

    time.sleep(1.0)
    info = thesportsdb.search_player(player.name_full or player.name)
    if not info:
        return

    if not player.bio_text and info.get('bio'):
        player.bio_text = info['bio'][:2000]
    if not player.photo_url_sportsdb_cutout and info.get('cutout'):
        player.photo_url_sportsdb_cutout = info['cutout']
    if not player.photo_url_sportsdb_thumb and info.get('thumb'):
        player.photo_url_sportsdb_thumb = info['thumb']
    if not player.external_id_sportsdb and info.get('sportsdb_id'):
        player.external_id_sportsdb = str(info['sportsdb_id'])
    if not player.date_of_birth and info.get('date_of_birth'):
        try:
            from datetime import date
            player.date_of_birth = date.fromisoformat(info['date_of_birth'])
        except (ValueError, TypeError):
            pass
