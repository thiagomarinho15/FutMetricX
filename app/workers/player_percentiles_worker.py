"""Percentile calculator — recalculated after each round.

For each competition+season, ranks every player in the same position_group
(GK, DEF, MID, ATT) on each metric and writes 0-100 percentile scores
to PlayerPercentiles.
"""
import logging
from datetime import datetime, timezone

from ..models import db, Competition, PlayerSeasonStats, PlayerPercentiles, Player
from ..utils.player_utils import position_group

from ..season_config import season_label

logger = logging.getLogger(__name__)
MIN_MINUTES = 90  # exclude players with <90 min to avoid skewed distributions

METRICS: list[str] = [
    'goals', 'assists', 'xg', 'xa', 'xg_per90',
    'progressive_passes_fbref', 'progressive_carries',
    'pressures', 'pass_accuracy_pct', 'aerial_duels_won', 'dribbles_success',
]

PCT_FIELDS: dict[str, str] = {
    'goals': 'pct_goals',
    'assists': 'pct_assists',
    'xg': 'pct_xg',
    'xa': 'pct_xa',
    'xg_per90': 'pct_xg_per90',
    'progressive_passes_fbref': 'pct_progressive_passes',
    'progressive_carries': 'pct_progressive_carries',
    'pressures': 'pct_pressures',
    'pass_accuracy_pct': 'pct_pass_accuracy',
    'aerial_duels_won': 'pct_aerial_duels_won',
    'dribbles_success': 'pct_dribbles_success',
}


def run() -> int:
    """Recompute percentiles for all competitions with season stats."""
    comps = Competition.query.all()
    total = 0
    for comp in comps:
        try:
            total += _process_competition(comp)
        except Exception as e:
            logger.error("percentiles_worker comp %d: %s", comp.id, e)

    db.session.commit()
    logger.info("player_percentiles_worker: %d rows upserted", total)
    return total


def _process_competition(comp: Competition) -> int:
    s_label = season_label(comp.name)
    rows = (
        PlayerSeasonStats.query
        .filter_by(competition_id=comp.id, season=s_label)
        .filter(PlayerSeasonStats.minutes_played >= MIN_MINUTES)
        .all()
    )
    if not rows:
        return 0

    # Group by position_group
    groups: dict[str, list[PlayerSeasonStats]] = {}
    for row in rows:
        player = Player.query.get(row.player_id)
        grp = position_group(player.position if player else None)
        groups.setdefault(grp, []).append(row)

    updated = 0
    for grp, grp_rows in groups.items():
        updated += _rank_group(comp.id, grp, grp_rows, s_label)
    return updated


def _rank_group(comp_id: int, grp: str, rows: list[PlayerSeasonStats], s_label: str) -> int:
    n = len(rows)
    if n < 2:
        return 0

    # For each metric, sort and assign ranks
    metric_ranks: dict[str, dict[int, int]] = {}
    for metric in METRICS:
        values = [(r.player_id, _get_float(r, metric)) for r in rows]
        values = [(pid, v) for pid, v in values if v is not None]
        values.sort(key=lambda x: x[1])
        for rank, (pid, _) in enumerate(values):
            pct = int(rank / max(len(values) - 1, 1) * 100)
            metric_ranks.setdefault(metric, {})[pid] = pct

    updated = 0
    for row in rows:
        pct_row = PlayerPercentiles.query.filter_by(
            player_id=row.player_id,
            competition_id=comp_id,
            season=s_label,
        ).first()
        if not pct_row:
            pct_row = PlayerPercentiles(
                player_id=row.player_id,
                competition_id=comp_id,
                season=s_label,
                position_group=grp,
            )
            db.session.add(pct_row)

        for metric, pct_field in PCT_FIELDS.items():
            pct = metric_ranks.get(metric, {}).get(row.player_id)
            if pct is not None:
                setattr(pct_row, pct_field, pct)

        pct_row.updated_at = datetime.now(timezone.utc)
        updated += 1

    return updated


def _get_float(row: PlayerSeasonStats, field: str) -> float | None:
    val = getattr(row, field, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
