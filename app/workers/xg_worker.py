"""Fetches xG, xA, npxG and related metrics from Understat (primary for advanced metrics)."""
import logging
from datetime import datetime, timezone

from ..models import db, Competition, Player, Team, AdvancedMetrics
from ..clients.understat import get_league_players, LEAGUES

logger = logging.getLogger(__name__)

CURRENT_SEASON = 2025


def run(league: str | None = None, season: int = CURRENT_SEASON) -> int:
    """Fetch season-aggregate xG metrics from Understat for all supported leagues."""
    logger.info("xg_worker: starting season=%s", season)
    leagues = [league] if league else list(LEAGUES.keys())

    total = 0
    for lg in leagues:
        if lg not in LEAGUES:
            logger.warning("xg_worker: %r not in supported leagues", lg)
            continue
        try:
            total += _process_league(lg, season)
        except Exception as e:
            logger.error("xg_worker %s: %s", lg, e)
    logger.info("xg_worker: done, %d records upserted", total)
    return total


def _process_league(league: str, season: int) -> int:
    players_data = get_league_players(league, season)
    if not players_data:
        return 0

    comp = Competition.query.filter_by(name=league, season=str(season)).first()
    added = 0

    for p_data in players_data:
        player = _get_or_create_player(p_data, comp)

        # Understat delivers season totals; store with fixture_id=None
        existing = AdvancedMetrics.query.filter_by(
            player_id=player.id,
            fixture_id=None,
            source_name='understat',
        ).first()

        xg = _f(p_data.get('xG'))
        xa = _f(p_data.get('xA'))
        npxg = _f(p_data.get('npxG'))
        xg_chain = _f(p_data.get('xGChain'))
        xg_buildup = _f(p_data.get('xGBuildup'))

        if existing:
            existing.xg = xg
            existing.xa = xa
            existing.npxg = npxg
            existing.xg_chain = xg_chain
            existing.xg_buildup = xg_buildup
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.session.add(AdvancedMetrics(
                fixture_id=None,
                player_id=player.id,
                xg=xg,
                xa=xa,
                npxg=npxg,
                xg_chain=xg_chain,
                xg_buildup=xg_buildup,
                source_name='understat',
            ))
            added += 1

    db.session.commit()
    return added


def _get_or_create_player(p_data: dict, comp: Competition | None) -> Player:
    source_id = str(p_data.get('id', ''))
    player = Player.query.filter_by(source_id=source_id, source_name='understat').first()
    if not player:
        team_name = p_data.get('team_title', '')
        team = None
        if comp and team_name:
            team = Team.query.filter(
                Team.name == team_name,
                Team.competition_id == comp.id,
            ).first()
        player = Player(
            name=p_data.get('player_name', ''),
            team_id=team.id if team else None,
            source_id=source_id,
            source_name='understat',
        )
        db.session.add(player)
        db.session.flush()
    return player


def _f(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
