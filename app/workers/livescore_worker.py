"""Polls API-Football for live scores and updates the fixtures table."""
import logging
from datetime import datetime, timezone

from ..models import db, Fixture
from ..clients.api_football import get_live_fixtures, LEAGUE_IDS

logger = logging.getLogger(__name__)

STATUS_MAP: dict[str, str] = {
    '1H': 'live', '2H': 'live', 'ET': 'live', 'BT': 'live',
    'P': 'live', 'INT': 'live', 'HT': 'live',
    'FT': 'finished', 'AET': 'finished', 'PEN': 'finished',
    'PST': 'postponed', 'CANC': 'cancelled', 'ABD': 'cancelled',
    'NS': 'scheduled', 'TBD': 'scheduled',
}


def run() -> int:
    """Poll all tracked leagues for live matches and update local fixtures."""
    updated = 0
    for league_name, league_id in LEAGUE_IDS.items():
        live = get_live_fixtures(league_id)
        for match in live:
            updated += _update_fixture(match)
    if updated:
        db.session.commit()
        logger.info("livescore_worker: %d fixtures updated", updated)
    return updated


def _update_fixture(match: dict) -> int:
    fixture_info = match.get('fixture', {})
    source_id = str(fixture_info.get('id', ''))
    if not source_id:
        return 0

    # match against any source — livescore can update football-data.org fixtures
    fixture = Fixture.query.filter_by(source_id=source_id).first()
    if not fixture:
        return 0

    status_short = fixture_info.get('status', {}).get('short', 'NS')
    score = match.get('goals', {})

    fixture.status = STATUS_MAP.get(status_short, 'scheduled')
    fixture.home_score = score.get('home')
    fixture.away_score = score.get('away')
    fixture.updated_at = datetime.now(timezone.utc)
    return 1
