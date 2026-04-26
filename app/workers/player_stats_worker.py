"""Fetches per-player match statistics from API-Football for finished fixtures."""
import logging
from datetime import datetime, timezone

from ..models import db, Fixture, Player, Team, MatchStats
from ..clients.api_football import get_fixture_players

logger = logging.getLogger(__name__)


def run(fixture_ids: list[int] | None = None) -> int:
    """Process player stats for finished fixtures not yet in match_stats."""
    logger.info("player_stats_worker: starting")

    if fixture_ids:
        fixtures = Fixture.query.filter(Fixture.id.in_(fixture_ids)).all()
    else:
        finished = Fixture.query.filter_by(status='finished').all()
        fixtures = [
            f for f in finished
            if not MatchStats.query.filter_by(fixture_id=f.id).first()
        ]

    total = 0
    for fixture in fixtures:
        try:
            total += _process(fixture)
        except Exception as e:
            logger.error("player_stats_worker fixture %d: %s", fixture.id, e)
    db.session.commit()
    logger.info("player_stats_worker: done, %d records added", total)
    return total


def _process(fixture: Fixture) -> int:
    if not fixture.source_id:
        return 0
    blocks = get_fixture_players(int(fixture.source_id))
    if not blocks:
        return 0

    added = 0
    for block in blocks:
        team_info = block.get('team', {})
        team = Team.query.filter_by(
            source_id=str(team_info.get('id', '')),
            source_name='api-football',
        ).first()

        for p_block in block.get('players', []):
            p_info = p_block.get('player', {})
            stats = p_block.get('statistics', [{}])[0]
            player = _get_or_create_player(p_info, team)

            if MatchStats.query.filter_by(
                fixture_id=fixture.id,
                player_id=player.id,
                source_name='api-football',
            ).first():
                continue

            goals = stats.get('goals', {})
            passes = stats.get('passes', {})
            shots = stats.get('shots', {})
            cards = stats.get('cards', {})
            games = stats.get('games', {})

            db.session.add(MatchStats(
                fixture_id=fixture.id,
                team_id=team.id if team else None,
                player_id=player.id,
                goals=goals.get('total') or 0,
                assists=goals.get('assists') or 0,
                shots=shots.get('total'),
                shots_on_target=shots.get('on'),
                passes=passes.get('total'),
                pass_accuracy=_pct(passes.get('accuracy')),
                yellow_cards=cards.get('yellow') or 0,
                red_cards=cards.get('red') or 0,
                minutes_played=games.get('minutes'),
                source_name='api-football',
            ))
            added += 1
    return added


def _get_or_create_player(p_info: dict, team: Team | None) -> Player:
    source_id = str(p_info.get('id', ''))
    player = Player.query.filter_by(source_id=source_id, source_name='api-football').first()
    if not player:
        player = Player(
            name=p_info.get('name', ''),
            nationality=p_info.get('nationality'),
            position=p_info.get('position'),
            age=p_info.get('age'),
            team_id=team.id if team else None,
            source_id=source_id,
            source_name='api-football',
        )
        db.session.add(player)
        db.session.flush()
    return player


def _pct(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace('%', ''))
    except (ValueError, TypeError):
        return None
