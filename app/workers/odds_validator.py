"""Cross-validates live scores against The-Odds-API (500 req/mês — use sparingly)."""
import logging
from datetime import datetime, timezone

from ..models import db, Fixture
from ..clients.odds_api import get_scores, SPORT_KEYS
from .conflict_resolver import log_conflict

logger = logging.getLogger(__name__)


def run(competitions: list[str] | None = None) -> int:
    """
    Compare finished fixture scores in DB against The-Odds-API scores.
    Only called when a score conflict is suspected — not on a continuous poll.
    Returns the number of conflicts detected.
    """
    logger.info("odds_validator: starting")
    targets = competitions or list(SPORT_KEYS.keys())
    conflicts = 0

    for comp_name in targets:
        sport_key = SPORT_KEYS.get(comp_name)
        if not sport_key:
            continue
        try:
            conflicts += _validate_competition(comp_name, sport_key)
        except Exception as e:
            logger.error("odds_validator %s: %s", comp_name, e)

    if conflicts:
        db.session.commit()
    logger.info("odds_validator: %d conflicts detected", conflicts)
    return conflicts


def _validate_competition(comp_name: str, sport_key: str) -> int:
    scores = get_scores(sport_key, days_from=3)
    if not scores:
        return 0

    conflicts = 0
    for game in scores:
        if not game.get('completed'):
            continue
        home_name = game.get('home_team', '')
        away_name = game.get('away_team', '')
        scores_data = game.get('scores', [])
        if not scores_data:
            continue

        home_score_odds = _extract_score(scores_data, home_name)
        away_score_odds = _extract_score(scores_data, away_name)
        if home_score_odds is None or away_score_odds is None:
            continue

        fixture = _find_fixture(home_name, away_name)
        if not fixture or fixture.home_score is None:
            continue

        if fixture.home_score != home_score_odds or fixture.away_score != away_score_odds:
            log_conflict(
                entity_type='fixture',
                entity_id=fixture.id,
                field='score',
                val_primary=f"{fixture.home_score}-{fixture.away_score}",
                val_fallback=f"{home_score_odds}-{away_score_odds}",
                source_primary=fixture.source_primary or 'unknown',
                source_fallback='odds-api',
            )
            conflicts += 1

    return conflicts


def _find_fixture(home_name: str, away_name: str) -> Fixture | None:
    from ..models import Team
    home = Team.query.filter(Team.name.ilike(f'%{home_name[:8]}%')).first()
    away = Team.query.filter(Team.name.ilike(f'%{away_name[:8]}%')).first()
    if not home or not away:
        return None
    return Fixture.query.filter_by(
        home_team_id=home.id,
        away_team_id=away.id,
        status='finished',
    ).order_by(Fixture.scheduled_at.desc()).first()


def _extract_score(scores: list[dict], team_name: str) -> int | None:
    for entry in scores:
        if team_name.lower() in entry.get('name', '').lower():
            try:
                return int(entry['score'])
            except (KeyError, ValueError, TypeError):
                return None
    return None
