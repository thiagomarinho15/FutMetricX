"""Ingests fixtures from football-data.org (primary source for schedules)."""
import logging
from datetime import datetime, timezone

from ..models import db, Competition, Team, Fixture
from ..clients.football_data import get_fixtures, COMPETITION_IDS, STATUS_MAP
from ..season_config import CURRENT_SEASON_YEAR as CURRENT_SEASON, season_label

logger = logging.getLogger(__name__)


def run(season: int = CURRENT_SEASON) -> int:
    """Fetch all fixtures for all tracked competitions and upsert into DB."""
    logger.info("fixtures_worker: starting season=%s", season)
    total = 0
    for comp_name, fd_id in COMPETITION_IDS.items():
        comp = _get_or_create_competition(comp_name, fd_id, season)
        matches = get_fixtures(fd_id, season=season)
        for m in matches:
            total += _upsert_fixture(comp, m)
        db.session.commit()
        logger.info("fixtures_worker: %s — %d matches processed", comp_name, len(matches))
    logger.info("fixtures_worker: done, %d upserted", total)
    return total


def _get_or_create_competition(name: str, fd_id: int, season: int) -> Competition:
    s_label = season_label(name)
    comp = Competition.query.filter_by(name=name, season=s_label).first()
    if not comp:
        comp = Competition(
            name=name,
            season=s_label,
            source_id=str(fd_id),
            source_name='football-data',
        )
        db.session.add(comp)
        db.session.flush()
    return comp


def _upsert_fixture(comp: Competition, match: dict) -> int:
    source_id = str(match.get('id', ''))
    if not source_id:
        return 0

    home_team = _get_or_create_team(match.get('homeTeam', {}), comp)
    away_team = _get_or_create_team(match.get('awayTeam', {}), comp)
    if not home_team or not away_team:
        return 0

    status = STATUS_MAP.get(match.get('status', 'SCHEDULED'), 'scheduled')
    full = match.get('score', {}).get('fullTime', {})

    scheduled_at = None
    raw_date = match.get('utcDate')
    if raw_date:
        try:
            scheduled_at = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
        except ValueError:
            pass

    fixture = Fixture.query.filter_by(source_id=source_id, source_primary='football-data').first()
    if fixture:
        fixture.status = status
        fixture.home_score = full.get('home')
        fixture.away_score = full.get('away')
        fixture.scheduled_at = scheduled_at
        fixture.updated_at = datetime.now(timezone.utc)
    else:
        fixture = Fixture(
            competition_id=comp.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            scheduled_at=scheduled_at,
            status=status,
            home_score=full.get('home'),
            away_score=full.get('away'),
            source_primary='football-data',
            source_id=source_id,
        )
        db.session.add(fixture)
    return 1


def _get_or_create_team(team_data: dict, comp: Competition) -> Team | None:
    if not team_data:
        return None
    source_id = str(team_data.get('id', ''))
    if not source_id or source_id == 'None':
        return None

    team = Team.query.filter_by(source_id=source_id, source_name='football-data').first()
    if not team:
        team = Team(
            name=team_data.get('name', ''),
            short_name=team_data.get('shortName') or team_data.get('tla'),
            competition_id=comp.id,
            source_id=source_id,
            source_name='football-data',
        )
        db.session.add(team)
        db.session.flush()
    return team
