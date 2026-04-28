"""Worker 0 — Refresh squads and teams from API-Football (current season rosters).

Free-tier constraints:
  - GET /teams requires season ≤ 2024 → use SQUAD_API_SEASON=2024
  - GET /players/squads works WITHOUT season param → returns most recent roster
  - TheSportsDB: free, no auth, 1s between calls

Run once per competition to populate/update Teams and Players with the
latest 2025-2026 rosters. Logo_url fetched from API-Football; if missing,
falls back to TheSportsDB badge.
"""
import logging
import time
from datetime import datetime, timezone

from ..models import db, Competition, Team, Player
from ..clients import api_football, thesportsdb
from ..season_config import SQUAD_API_SEASON, season_label

logger = logging.getLogger(__name__)


def run(competition_name: str | None = None) -> int:
    """Refresh squads for all leagues (or a specific one).

    Returns total number of players upserted.
    """
    from ..clients.api_football import LEAGUE_IDS
    targets = (
        {competition_name: LEAGUE_IDS[competition_name]}
        if competition_name and competition_name in LEAGUE_IDS
        else dict(LEAGUE_IDS)
    )

    total_players = 0
    for comp_name, league_id in targets.items():
        try:
            total_players += _refresh_league(comp_name, league_id)
        except Exception as e:
            logger.error("squad_refresh_worker %s: %s", comp_name, e)

    db.session.commit()
    logger.info("squad_refresh_worker: done — %d players upserted", total_players)
    return total_players


def _refresh_league(comp_name: str, league_id: int) -> int:
    logger.info("squad_refresh: league=%s id=%d (teams season=%d, squads=current)",
                comp_name, league_id, SQUAD_API_SEASON)

    comp = _get_or_create_competition(comp_name, league_id)

    # /teams requires season ≤ 2024 on free tier
    teams_data = _fetch_teams(league_id)
    if not teams_data:
        logger.warning("squad_refresh: no teams returned for %s (league_id=%d)", comp_name, league_id)
        return 0

    logger.info("squad_refresh: %s — %d times encontrados", comp_name, len(teams_data))
    total = 0
    for team_block in teams_data:
        team_info = team_block.get('team', {})
        team = _upsert_team(team_info, comp)
        if not team:
            continue
        upserted = _refresh_squad(team)
        total += upserted
        logger.info("squad_refresh:   %s → %d jogadores", team.name, upserted)
        time.sleep(0.6)

    db.session.flush()
    return total


def _fetch_teams(league_id: int) -> list[dict]:
    """GET /teams?league={id}&season={SQUAD_API_SEASON}  (free tier: season≤2024)."""
    resp = api_football._get('teams', {'league': league_id, 'season': SQUAD_API_SEASON})
    return resp.get('response', [])


def _get_or_create_competition(comp_name: str, league_id: int) -> Competition:
    s_label = season_label(comp_name)
    comp = Competition.query.filter_by(name=comp_name, season=s_label).first()
    if not comp:
        comp = Competition(
            name=comp_name,
            season=s_label,
            source_id=str(league_id),
            source_name='api-football',
        )
        db.session.add(comp)
        db.session.flush()
    return comp


def _upsert_team(team_info: dict, comp: Competition) -> Team | None:
    source_id = str(team_info.get('id', ''))
    if not source_id:
        return None

    team = Team.query.filter_by(source_id=source_id, source_name='api-football').first()
    is_new = team is None
    if is_new:
        team = Team(source_id=source_id, source_name='api-football')
        db.session.add(team)

    team.name = team_info.get('name', '')
    team.short_name = team_info.get('code') or team_info.get('name', '')[:10]
    team.country = team_info.get('country', '')
    team.competition_id = comp.id

    # API-Football provides logo URL in the teams response
    logo = team_info.get('logo')
    if logo and not team.logo_url:
        team.logo_url = logo

    # Fallback to TheSportsDB for teams still missing a logo
    if not team.logo_url:
        _enrich_team_logo(team)

    team.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return team


def _enrich_team_logo(team: Team) -> None:
    time.sleep(1.0)
    info = thesportsdb.search_team(team.name)
    if not info:
        return
    if info.get('badge'):
        team.logo_url = info['badge']
    if info.get('logo') and not team.banner_url:
        team.banner_url = info['logo']


def _refresh_squad(team: Team) -> int:
    """GET /players/squads?team={id}  (no season = most current roster)."""
    resp = api_football._get('players/squads', {'team': int(team.source_id)})
    blocks = resp.get('response', [])
    if not blocks:
        return 0

    players_raw: list[dict] = []
    for block in blocks:
        players_raw.extend(block.get('players', []))

    upserted = 0
    for p_data in players_raw:
        try:
            upserted += _upsert_player(p_data, team)
        except Exception as e:
            logger.warning("squad_refresh player %s: %s", p_data.get('name'), e)

    return upserted


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
    player.position = _map_position(p_data.get('position', ''))
    player.shirt_number = p_data.get('number')
    player.team_id = team.id
    player.is_active = True

    photo = p_data.get('photo')
    if photo:
        player.photo_url_apifootball = photo

    player.updated_at = datetime.now(timezone.utc)
    return 1 if is_new else 0


def _map_position(raw: str) -> str:
    return {'Goalkeeper': 'GK', 'Defender': 'DEF', 'Midfielder': 'MID', 'Attacker': 'ATT'}.get(raw, raw or 'UNK')
