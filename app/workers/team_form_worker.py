"""Computes team form (last 5/10, W/D/L, xG averages) from finished fixtures."""
import logging
from datetime import datetime, timezone

from sqlalchemy import or_

from ..models import db, Competition, Fixture, Team, TeamForm, AdvancedMetrics

logger = logging.getLogger(__name__)


def run(competition_id: int | None = None) -> int:
    """Recalculate TeamForm for all teams in tracked competitions."""
    logger.info("team_form_worker: starting")

    if competition_id:
        competitions = Competition.query.filter_by(id=competition_id).all()
    else:
        competitions = Competition.query.all()

    updated = 0
    for comp in competitions:
        teams = Team.query.filter_by(competition_id=comp.id).all()
        for team in teams:
            try:
                _upsert_form(team, comp)
                updated += 1
            except Exception as e:
                logger.error("team_form_worker team %d: %s", team.id, e)

    db.session.commit()
    logger.info("team_form_worker: %d team forms updated", updated)
    return updated


def _upsert_form(team: Team, comp: Competition) -> None:
    finished = (
        Fixture.query
        .filter(
            Fixture.competition_id == comp.id,
            Fixture.status == 'finished',
            or_(
                Fixture.home_team_id == team.id,
                Fixture.away_team_id == team.id,
            ),
        )
        .order_by(Fixture.scheduled_at.desc())
        .limit(10)
        .all()
    )

    if not finished:
        return

    results = []
    for f in finished:
        is_home = f.home_team_id == team.id
        team_score = f.home_score if is_home else f.away_score
        opp_score = f.away_score if is_home else f.home_score
        if team_score is None or opp_score is None:
            continue
        if team_score > opp_score:
            results.append('W')
        elif team_score == opp_score:
            results.append('D')
        else:
            results.append('L')

    wins = results.count('W')
    draws = results.count('D')
    losses = results.count('L')
    goals_scored = sum(
        (f.home_score if f.home_team_id == team.id else f.away_score) or 0
        for f in finished
    )
    goals_conceded = sum(
        (f.away_score if f.home_team_id == team.id else f.home_score) or 0
        for f in finished
    )

    xg_avg = _xg_avg(team.id, [f.id for f in finished])
    xga_avg = _xga_avg(team.id, [f.id for f in finished])

    form = TeamForm.query.filter_by(team_id=team.id, competition_id=comp.id).first()
    if form:
        form.last_5 = ''.join(results[:5])
        form.last_10 = ''.join(results[:10])
        form.wins = wins
        form.draws = draws
        form.losses = losses
        form.goals_scored = goals_scored
        form.goals_conceded = goals_conceded
        form.xg_avg = xg_avg
        form.xga_avg = xga_avg
        form.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(TeamForm(
            team_id=team.id,
            competition_id=comp.id,
            last_5=''.join(results[:5]),
            last_10=''.join(results[:10]),
            wins=wins,
            draws=draws,
            losses=losses,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            xg_avg=xg_avg,
            xga_avg=xga_avg,
        ))


def _xg_avg(team_id: int, fixture_ids: list[int]) -> float | None:
    rows = (
        AdvancedMetrics.query
        .filter(
            AdvancedMetrics.team_id == team_id,
            AdvancedMetrics.fixture_id.in_(fixture_ids),
        )
        .all()
    )
    vals = [r.xg for r in rows if r.xg is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def _xga_avg(team_id: int, fixture_ids: list[int]) -> float | None:
    # xGA = opponents' xG in those fixtures — fetch from advanced_metrics
    # where team_id != our team but fixture_id matches
    rows = (
        AdvancedMetrics.query
        .filter(
            AdvancedMetrics.team_id != team_id,
            AdvancedMetrics.fixture_id.in_(fixture_ids),
        )
        .all()
    )
    vals = [r.xg for r in rows if r.xg is not None]
    return round(sum(vals) / len(vals), 3) if vals else None
