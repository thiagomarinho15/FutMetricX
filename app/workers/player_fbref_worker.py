"""Worker 5 — Weekly FBref advanced stats via soccerdata.

Updates progressive_carries, progressive_passes, pressures, defensive_actions
in PlayerSeasonStats. Runs Sunday nights.
"""
import logging

from ..models import db, Competition, Player, PlayerSeasonStats
from ..clients.fbref_client import get_player_stats, FBREF_LEAGUES
from ..utils.player_utils import normalize_player_name

logger = logging.getLogger(__name__)

SEASON_YEAR = '2024'
SEASON_LABEL = '2024-25'


def run(league: str | None = None) -> int:
    """Update FBref advanced metrics for all supported leagues or a specific one."""
    leagues = [league] if league else list(FBREF_LEAGUES.keys())
    total = 0
    for lg in leagues:
        try:
            total += _process_league(lg)
        except Exception as e:
            logger.error("player_fbref_worker %s: %s", lg, e)

    db.session.commit()
    logger.info("player_fbref_worker: %d rows updated", total)
    return total


def _process_league(league_name: str) -> int:
    comp = Competition.query.filter_by(name=league_name).first()
    if not comp:
        logger.debug("fbref: no competition in DB for %r", league_name)
        return 0

    fbref_rows = get_player_stats(league_name, SEASON_YEAR)
    if not fbref_rows:
        return 0

    # Build lookup: normalised name → fbref row
    fbref_map = {
        normalize_player_name(r.get('player_name', '')): r
        for r in fbref_rows
    }

    players = Player.query.filter_by(source_name='api-football').all()
    updated = 0
    for player in players:
        norm = normalize_player_name(player.name)
        fbref_row = fbref_map.get(norm)
        if not fbref_row:
            continue

        row = PlayerSeasonStats.query.filter_by(
            player_id=player.id,
            competition_id=comp.id,
            season=SEASON_LABEL,
        ).first()
        if not row:
            continue

        changed = False
        for field, alias in [
            ('progressive_carries', 'progressive_carries'),
            ('progressive_passes', 'progressive_passes_fbref'),
            ('pressures', 'pressures'),
            ('defensive_actions', 'defensive_actions'),
        ]:
            val = fbref_row.get(field)
            if val is not None:
                setattr(row, alias, int(val))
                changed = True

        if changed:
            from datetime import datetime, timezone
            row.source_base = 'api-football+fbref'
            row.updated_at = datetime.now(timezone.utc)
            updated += 1

    return updated
