"""Fetches xG, xA, npxG and related metrics from Understat (primary for advanced metrics).

Also cross-references existing api-football Player records by name and updates
their external_id_understat for future lookups.
"""
import logging
from datetime import datetime, timezone

from ..models import db, Competition, Player, Team, AdvancedMetrics, PlayerSeasonStats, PlayerIdMapping
from ..clients.understat import get_league_players, LEAGUES
from ..season_config import CURRENT_SEASON_YEAR as CURRENT_SEASON, season_label
from ..utils.player_utils import normalize_player_name

logger = logging.getLogger(__name__)


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

    s_label = season_label(league)
    comp = Competition.query.filter_by(name=league, season=s_label).first()
    added = 0

    for p_data in players_data:
        player = _resolve_player(p_data, comp)

        xg = _f(p_data.get('xG'))
        xa = _f(p_data.get('xA'))
        npxg = _f(p_data.get('npxG'))
        xg_chain = _f(p_data.get('xGChain'))
        xg_buildup = _f(p_data.get('xGBuildup'))

        # Upsert AdvancedMetrics (season-aggregate, fixture_id=NULL)
        existing = AdvancedMetrics.query.filter_by(
            player_id=player.id,
            fixture_id=None,
            source_name='understat',
        ).first()

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

        # Mirror xG into PlayerSeasonStats if row exists
        if comp:
            _sync_season_stats(player, comp, s_label, xg, xa, npxg, xg_chain, xg_buildup)

    db.session.commit()
    return added


def _resolve_player(p_data: dict, comp: Competition | None) -> Player:
    """Try to find an api-football player by name; fallback to understat-sourced entry."""
    understat_id = str(p_data.get('id', ''))
    player_name = p_data.get('player_name', '')

    # 1. Try existing understat-sourced Player record
    player = Player.query.filter_by(source_id=understat_id, source_name='understat').first()
    if player:
        return player

    # 2. Try to match an api-football player by normalised name and update its external_id
    if player_name:
        norm = normalize_player_name(player_name)
        api_player = Player.query.filter_by(source_name='api-football').all()
        for p in api_player:
            if normalize_player_name(p.name) == norm:
                if not p.external_id_understat and understat_id:
                    p.external_id_understat = int(understat_id) if understat_id.isdigit() else None
                    _upsert_id_mapping(p.id, 'understat', understat_id)
                return p

    # 3. Create a new understat-sourced player as fallback
    team_name = p_data.get('team_title', '')
    team = None
    if comp and team_name:
        team = Team.query.filter(
            Team.name == team_name,
            Team.competition_id == comp.id,
        ).first()

    player = Player(
        name=player_name,
        team_id=team.id if team else None,
        source_id=understat_id,
        source_name='understat',
    )
    db.session.add(player)
    db.session.flush()
    return player


def _sync_season_stats(
    player: Player,
    comp: Competition,
    s_label: str,
    xg, xa, npxg, xg_chain, xg_buildup,
) -> None:
    row = PlayerSeasonStats.query.filter_by(
        player_id=player.id,
        competition_id=comp.id,
        season=s_label,
    ).first()
    if not row:
        return
    row.xg = xg
    row.xa = xa
    row.npxg = npxg
    row.xg_chain = xg_chain
    row.xg_buildup = xg_buildup
    row.source_advanced = 'understat'
    row.updated_at = datetime.now(timezone.utc)


def _upsert_id_mapping(player_id: int, source: str, external_id: str) -> None:
    existing = PlayerIdMapping.query.filter_by(source=source, external_id=external_id).first()
    if not existing:
        db.session.add(PlayerIdMapping(
            player_id=player_id,
            source=source,
            external_id=external_id,
            confidence='auto',
        ))


def _f(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
