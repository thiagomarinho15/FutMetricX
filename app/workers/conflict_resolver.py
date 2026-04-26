"""Detects and logs divergences between primary and fallback data sources."""
import logging
from datetime import datetime, timezone

from ..models import db, DataConflict

logger = logging.getLogger(__name__)

XG_THRESHOLD = 0.3
SCORE_THRESHOLD = 0  # any score divergence is critical


def log_conflict(
    entity_type: str,
    entity_id: int,
    field: str,
    val_primary,
    val_fallback,
    source_primary: str,
    source_fallback: str,
) -> DataConflict:
    """Record a detected conflict between two sources. Called by other workers."""
    try:
        delta = abs(float(val_primary) - float(val_fallback))
    except (TypeError, ValueError):
        delta = None

    conflict = DataConflict(
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field,
        value_primary=str(val_primary),
        value_fallback=str(val_fallback),
        delta=delta,
        source_primary=source_primary,
        source_fallback=source_fallback,
        detected_at=datetime.now(timezone.utc),
        resolved=False,
    )
    db.session.add(conflict)
    logger.warning(
        "conflict %s#%d.%s primary=%s(%s) fallback=%s(%s) Δ=%s",
        entity_type, entity_id, field,
        val_primary, source_primary,
        val_fallback, source_fallback,
        delta,
    )
    return conflict


def run() -> int:
    """Sweep open conflicts, resolve those below threshold, alert on critical ones."""
    logger.info("conflict_resolver: running sweep")
    open_conflicts = DataConflict.query.filter_by(resolved=False).all()
    resolved = 0

    for conflict in open_conflicts:
        if conflict.delta is None:
            continue
        threshold = XG_THRESHOLD if 'xg' in conflict.field_name.lower() else SCORE_THRESHOLD
        if conflict.delta <= threshold:
            conflict.resolved = True
            resolved += 1
        else:
            logger.error(
                "CRITICAL conflict %s#%d.%s Δ=%.3f (threshold=%.1f) — manual review needed",
                conflict.entity_type, conflict.entity_id, conflict.field_name,
                conflict.delta, threshold,
            )

    if resolved:
        db.session.commit()
    logger.info("conflict_resolver: %d resolved, %d still open",
                resolved, len(open_conflicts) - resolved)
    return resolved


def mark_resolved(conflict_id: int) -> bool:
    conflict = DataConflict.query.get(conflict_id)
    if not conflict:
        return False
    conflict.resolved = True
    db.session.commit()
    return True
