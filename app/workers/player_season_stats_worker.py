"""Worker 2 — Season-aggregate stats: API-Football base + Understat xG/xA.

Runs after each round. Upserts PlayerSeasonStats and recomputes per-90 fields.
"""
import logging
from datetime import datetime, timezone

from ..models import db, Player, Competition, PlayerSeasonStats, PlayerIdMapping
from ..clients import api_football, understat
from ..utils.player_utils import calc_per90, normalize_player_name

logger = logging.getLogger(__name__)

CURRENT_SEASON = 2024
SEASON_LABEL = '2024-25'


def run(competition_name: str | None = None) -> int:
    """Upsert season stats for all players in tracked competitions."""
    query = Competition.query
    if competition_name:
        query = query.filter_by(name=competition_name)
    comps = query.all()

    total = 0
    for comp in comps:
        try:
            total += _process_competition(comp)
        except Exception as e:
            logger.error("player_season_stats_worker comp %s: %s", comp.name, e)

    db.session.commit()
    logger.info("player_season_stats_worker: %d upserted", total)
    return total


def _process_competition(comp: Competition) -> int:
    from ..clients.api_football import LEAGUE_IDS
    league_id = LEAGUE_IDS.get(comp.name)
    if not league_id:
        return 0

    # Understat xG data keyed by normalised player name
    xg_map = _build_understat_map(comp.name)
    players = Player.query.filter_by(source_name='api-football').all()

    updated = 0
    for player in players:
        if not player.source_id:
            continue
        try:
            updated += _upsert_player_season(player, comp, league_id, xg_map)
        except Exception as e:
            logger.debug("season_stats player %d: %s", player.id, e)

    return updated


def _build_understat_map(competition_name: str) -> dict[str, dict]:
    from ..clients.understat import LEAGUES
    slug = LEAGUES.get(competition_name)
    if not slug:
        return {}
    players_data = understat.get_league_players(competition_name, CURRENT_SEASON)
    return {
        normalize_player_name(p.get('player_name', '')): p
        for p in players_data
        if p.get('player_name')
    }


def _upsert_player_season(player: Player, comp: Competition, league_id: int,
                           xg_map: dict) -> int:
    block = api_football.get_player_season_stats(
        int(player.source_id), CURRENT_SEASON, league_id
    )
    if not block:
        return 0

    stats_list = block.get('statistics', [])
    # Find the stats block matching this competition
    stats = next(
        (s for s in stats_list if str(s.get('league', {}).get('id', '')) == str(league_id)),
        stats_list[0] if stats_list else {},
    )
    if not stats:
        return 0

    games = stats.get('games', {})
    goals = stats.get('goals', {})
    passes = stats.get('passes', {})
    shots = stats.get('shots', {})
    duels = stats.get('duels', {})
    dribbles = stats.get('dribbles', {})
    cards = stats.get('cards', {})
    fouls = stats.get('fouls', {})

    minutes = games.get('minutes') or 0
    goals_val = goals.get('total') or 0
    assists_val = goals.get('assists') or 0

    # Merge Understat xG
    norm_name = normalize_player_name(player.name)
    xg_data = xg_map.get(norm_name, {})
    xg_val = _safe_float(xg_data.get('xG'))
    xa_val = _safe_float(xg_data.get('xA'))
    npxg_val = _safe_float(xg_data.get('npxG'))
    xg_chain_val = _safe_float(xg_data.get('xGChain'))
    xg_buildup_val = _safe_float(xg_data.get('xGBuildup'))

    # Understat external ID mapping
    if xg_data.get('id') and not player.external_id_understat:
        player.external_id_understat = int(xg_data['id'])
        _upsert_id_mapping(player.id, 'understat', str(xg_data['id']))

    row = PlayerSeasonStats.query.filter_by(
        player_id=player.id,
        competition_id=comp.id,
        season=SEASON_LABEL,
    ).first()

    if not row:
        row = PlayerSeasonStats(
            player_id=player.id,
            competition_id=comp.id,
            season=SEASON_LABEL,
        )
        db.session.add(row)

    row.team_id = player.team_id
    row.appearances = games.get('appearences') or 0
    row.starts = games.get('lineups') or 0
    row.minutes_played = minutes
    row.goals = goals_val
    row.assists = assists_val
    row.shots_total = shots.get('total') or 0
    row.shots_on_target = shots.get('on') or 0
    row.passes_total = passes.get('total') or 0
    row.pass_accuracy_pct = _safe_float(str(passes.get('accuracy') or '').replace('%', ''))
    row.key_passes = passes.get('key') or 0
    row.dribbles_attempted = dribbles.get('attempts') or 0
    row.dribbles_success = dribbles.get('success') or 0
    row.duels_total = duels.get('total') or 0
    row.duels_won = duels.get('won') or 0
    row.yellow_cards = cards.get('yellow') or 0
    row.red_cards = cards.get('red') or 0
    row.fouls_committed = fouls.get('committed') or 0
    row.fouls_drawn = fouls.get('drawn') or 0
    row.rating_avg = _safe_float(games.get('rating'))

    row.xg = xg_val
    row.xa = xa_val
    row.npxg = npxg_val
    row.xg_chain = xg_chain_val
    row.xg_buildup = xg_buildup_val

    # Compute per-90
    row.goals_per90 = calc_per90(goals_val, minutes)
    row.assists_per90 = calc_per90(assists_val, minutes)
    row.xg_per90 = calc_per90(xg_val, minutes)
    row.xa_per90 = calc_per90(xa_val, minutes)

    row.updated_at = datetime.now(timezone.utc)
    return 1


def _upsert_id_mapping(player_id: int, source: str, external_id: str) -> None:
    existing = PlayerIdMapping.query.filter_by(source=source, external_id=external_id).first()
    if not existing:
        db.session.add(PlayerIdMapping(
            player_id=player_id, source=source,
            external_id=external_id, confidence='auto',
        ))


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
