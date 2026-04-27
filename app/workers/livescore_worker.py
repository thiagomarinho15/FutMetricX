"""Smart livescore orchestrator — budget-aware, phase-adaptive polling.

Budget allocation (per day):
  football-data.org  : 20 req/min × 2 keys = 28.800 req/day
      → Used for ALL live score polling (one req covers all live games at once)
  API-Football       : 100 req/day × 2 keys = 200 req/day total
      → Reserved only for rich stats at match milestones:
          • Team stats at half-time  : 1 req per match
          • Player stats at full time: 1 req per match

Polling intervals by phase (football-data.org only):
  No games today/live          → 0 req  (skip entirely)
  Game imminent (< 60 min)     → every 10 min
  1st half active              → every  2 min
  Half-time break              → every  5 min
  2nd half / extra time / pens → every  2 min  (ET/P: 1 min)
  All games finished           → 0 req  (stop until next day)

State persisted in Redis (TTL 48h), with in-memory fallback.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from ..models import db, Fixture
from ..clients.football_data import get_live_matches, get_matches_today, STATUS_MAP
from ..services import budget_tracker

logger = logging.getLogger(__name__)

# ── Phase → polling interval in seconds ────────────────────────────────────────
_INTERVAL: dict[str, int] = {
    'imminent': 600,    # 10 min — game hasn't started yet
    '1H':       120,    # 2 min  — first half
    'HT':       300,    # 5 min  — half-time break
    '2H':       120,    # 2 min  — second half
    'ET':        60,    # 1 min  — extra time
    'BT':       120,    # 2 min  — break before extra time
    'P':         60,    # 1 min  — penalty shoot-out
}
_DEFAULT_INTERVAL = 120  # fallback for unknown live statuses

# football-data.org status → game phase tag
_PHASE_MAP: dict[str, str] = {
    'IN_PLAY': '1H',
    'PAUSED':  'HT',
}

# API-Football short status codes → game phase
_APIF_PHASE: dict[str, str] = {
    '1H': '1H', 'HT': 'HT', '2H': '2H',
    'ET': 'ET', 'BT': 'BT', 'P': 'P',
}

# Redis key templates (all expire after 48h)
_KEY_LAST_POLL  = 'fmx:livescore:last_poll'
_KEY_HT_DONE    = 'fmx:fixture:{}:ht_done'
_KEY_FT_DONE    = 'fmx:fixture:{}:ft_done'
_KEY_LAST_STATUS = 'fmx:fixture:{}:last_status'

# In-memory fallback when Redis is unavailable
_mem: dict[str, str] = {}


# ── Redis helpers ──────────────────────────────────────────────────────────────

def _redis():
    try:
        import redis as redis_lib
        url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        r = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=1)
        r.ping()
        return r
    except Exception:
        return None


def _rget(key: str) -> str | None:
    r = _redis()
    if r:
        try:
            return r.get(key)
        except Exception:
            pass
    return _mem.get(key)


def _rset(key: str, value: str, ex: int = 172800) -> None:
    r = _redis()
    if r:
        try:
            r.set(key, value, ex=ex)
            return
        except Exception:
            pass
    _mem[key] = value


def _rdel(key: str) -> None:
    r = _redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _mem.pop(key, None)


# ── Main entry point (called by scheduler every 1 min) ────────────────────────

def run() -> int:
    """
    Orchestrate live score updates.
    Returns number of fixtures updated in this invocation.
    """
    now = datetime.now(timezone.utc)

    # 1. Fast-exit: are there any active or imminent games?
    active_fixtures = _get_active_fixtures(now)
    if not active_fixtures:
        return 0

    # 2. Determine the most urgent polling interval across all active games
    target_interval = _compute_target_interval(active_fixtures, now)

    # 3. Has enough time elapsed since the last poll?
    last_poll = _rget(_KEY_LAST_POLL)
    if last_poll:
        elapsed = (now - datetime.fromisoformat(last_poll)).total_seconds()
        if elapsed < target_interval:
            return 0  # not yet time — skip this tick

    # 4. Poll football-data.org (ONE request covers ALL live games)
    updated = _poll_scores(now)

    # 5. Detect milestone transitions per fixture (budget-gated API-Football calls)
    _process_milestones(active_fixtures)

    return updated


# ── Score polling (football-data.org) ─────────────────────────────────────────

def _poll_scores(now: datetime) -> int:
    """Fetch all live matches from football-data.org and update the DB."""
    live_matches = get_live_matches()
    _rset(_KEY_LAST_POLL, now.isoformat())

    if not live_matches:
        # No live games returned — update any DB fixtures still marked 'live'
        _mark_stale_fixtures_finished()
        return 0

    updated = 0
    for match in live_matches:
        updated += _update_fixture_from_fdorg(match)

    if updated:
        db.session.commit()
        logger.info("livescore_worker: %d fixtures updated (1 fd.org req)", updated)

    return updated


def _update_fixture_from_fdorg(match: dict) -> int:
    """Update a single fixture from a football-data.org match payload."""
    source_id = str(match.get('id', ''))
    if not source_id:
        return 0

    fixture = Fixture.query.filter_by(source_id=source_id, source_primary='football-data').first()
    if not fixture:
        return 0

    fd_status = match.get('status', 'SCHEDULED')
    new_status = STATUS_MAP.get(fd_status, 'scheduled')
    score = match.get('score', {})
    full = score.get('fullTime', {})
    half = score.get('halfTime', {})

    # Use fullTime score if available, fall back to halfTime
    home = full.get('home') if full.get('home') is not None else half.get('home')
    away = full.get('away') if full.get('away') is not None else half.get('away')

    old_status = fixture.status
    fixture.status = new_status
    fixture.home_score = home
    fixture.away_score = away
    fixture.updated_at = datetime.now(timezone.utc)

    # Record status transition for milestone detection
    key = _KEY_LAST_STATUS.format(fixture.id)
    _rset(key, f"{old_status}→{new_status}")

    return 1


def _mark_stale_fixtures_finished() -> None:
    """If fd.org returns no live games, mark DB 'live' fixtures that kicked off >3h ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    stale = Fixture.query.filter(
        Fixture.status == 'live',
        Fixture.scheduled_at < cutoff,
    ).all()
    for f in stale:
        f.status = 'finished'
        f.updated_at = datetime.now(timezone.utc)
        logger.warning("livescore_worker: fixture %d marked finished (stale live)", f.id)
    if stale:
        db.session.commit()


# ── Milestone detection (API-Football, budget-gated) ──────────────────────────

def _process_milestones(active_fixtures: list[Fixture]) -> None:
    """
    For each fixture, check if it crossed a milestone since last tick
    and trigger the appropriate API-Football call if budget allows.
    """
    for fixture in active_fixtures:
        if fixture.status == 'finished':
            _on_full_time(fixture)
        elif fixture.status == 'live':
            # Check if we just came from scheduled (match started)
            _on_possible_kickoff(fixture)


def _on_possible_kickoff(fixture: Fixture) -> None:
    key = _KEY_LAST_STATUS.format(fixture.id)
    transition = _rget(key) or ''
    if 'scheduled→live' in transition:
        logger.info("livescore_worker: fixture %d KICKED OFF", fixture.id)
        _rdel(key)


def _on_full_time(fixture: Fixture) -> None:
    ft_key = _KEY_FT_DONE.format(fixture.id)
    if _rget(ft_key):
        return  # already processed

    logger.info("livescore_worker: fixture %d FULL TIME — fetching player stats", fixture.id)

    # Gate: only proceed if API-Football budget allows
    if not budget_tracker.consume(1):
        logger.warning(
            "livescore_worker: skipping player stats for fixture %d — budget exhausted",
            fixture.id,
        )
        _rset(ft_key, 'budget_skip')
        return

    try:
        from ..workers.player_stats_worker import _process as fetch_player_stats
        added = fetch_player_stats(fixture)
        db.session.commit()
        logger.info("livescore_worker: fixture %d — %d player stat rows added", fixture.id, added)
    except Exception as e:
        logger.error("livescore_worker: player stats fixture %d: %s", fixture.id, e)

    _rset(ft_key, '1')

    # Schedule xG enrichment (Understat takes 2-4h — rely on xg_worker Monday run)
    logger.info(
        "livescore_worker: fixture %d — xG enrichment deferred to xg_worker (Understat delay)",
        fixture.id,
    )


def _on_half_time(fixture: Fixture) -> None:
    ht_key = _KEY_HT_DONE.format(fixture.id)
    if _rget(ht_key):
        return

    logger.info("livescore_worker: fixture %d HALF TIME — fetching team stats", fixture.id)

    if not budget_tracker.consume(1):
        logger.warning(
            "livescore_worker: skipping team stats for fixture %d — budget exhausted",
            fixture.id,
        )
        _rset(ht_key, 'budget_skip')
        return

    try:
        from ..clients.api_football import get_fixture_stats
        from ..models import AdvancedMetrics, Team

        if not fixture.source_id:
            return

        # Try to find the API-Football source_id for this fixture
        # (fixtures seeded from football-data.org may not have apif source_id)
        apif_id = _resolve_apif_fixture_id(fixture)
        if not apif_id:
            logger.debug("livescore_worker: no api-football id for fixture %d", fixture.id)
            _rset(ht_key, 'no_apif_id')
            return

        team_stats = get_fixture_stats(apif_id)
        for block in team_stats:
            team_info = block.get('team', {})
            team = Team.query.filter_by(
                source_id=str(team_info.get('id', '')),
                source_name='api-football',
            ).first()
            if not team:
                continue

            # Extract xG from team stats (type: "Expected Goals")
            xg_val = None
            for stat in block.get('statistics', []):
                if stat.get('type') == 'expected_goals':
                    try:
                        xg_val = float(stat.get('value') or 0)
                    except (ValueError, TypeError):
                        pass

            if xg_val is not None:
                existing = AdvancedMetrics.query.filter_by(
                    fixture_id=fixture.id, team_id=team.id,
                ).first()
                if existing:
                    existing.xg = xg_val
                else:
                    db.session.add(AdvancedMetrics(
                        fixture_id=fixture.id,
                        team_id=team.id,
                        xg=xg_val,
                        source_name='api-football-ht',
                    ))

        db.session.commit()
    except Exception as e:
        logger.error("livescore_worker: team stats fixture %d: %s", fixture.id, e)

    _rset(ht_key, '1')


# ── Scheduling helpers ─────────────────────────────────────────────────────────

def _get_active_fixtures(now: datetime) -> list[Fixture]:
    """
    Return fixtures that are currently live OR scheduled to kick off
    within the next 60 minutes.
    """
    window_start = now
    window_end = now + timedelta(minutes=60)

    live = Fixture.query.filter_by(status='live').all()
    imminent = Fixture.query.filter(
        Fixture.status == 'scheduled',
        Fixture.scheduled_at >= window_start,
        Fixture.scheduled_at <= window_end,
    ).all()

    return live + imminent


def _compute_target_interval(fixtures: list[Fixture], now: datetime) -> int:
    """
    Return the shortest polling interval appropriate for the current set of fixtures.
    Shorter interval wins when multiple games are active in different phases.
    """
    min_interval = _INTERVAL['imminent']  # start pessimistic

    for fixture in fixtures:
        if fixture.status == 'live':
            # We don't have the API-Football phase tag here (fd.org doesn't give it).
            # Estimate phase from elapsed time since scheduled_at.
            phase_interval = _estimate_interval_from_time(fixture, now)
            min_interval = min(min_interval, phase_interval)
        else:
            # Imminent (scheduled, within 60 min)
            if fixture.scheduled_at:
                mins_to_kick = (fixture.scheduled_at - now).total_seconds() / 60
                if mins_to_kick <= 10:
                    min_interval = min(min_interval, _INTERVAL['1H'])  # treat as about to start
                else:
                    min_interval = min(min_interval, _INTERVAL['imminent'])

    return min_interval


def _estimate_interval_from_time(fixture: Fixture, now: datetime) -> int:
    """Estimate polling phase from elapsed match time."""
    if not fixture.scheduled_at:
        return _DEFAULT_INTERVAL

    elapsed_min = (now - fixture.scheduled_at).total_seconds() / 60

    if elapsed_min < 0:
        return _INTERVAL['imminent']
    elif elapsed_min < 45:
        return _INTERVAL['1H']
    elif elapsed_min < 60:
        # Probably half-time
        _on_half_time(fixture)
        return _INTERVAL['HT']
    elif elapsed_min < 95:
        return _INTERVAL['2H']
    elif elapsed_min < 125:
        return _INTERVAL['ET']
    else:
        return _INTERVAL['P']


def _resolve_apif_fixture_id(fixture: Fixture) -> int | None:
    """
    Find the API-Football numeric fixture ID for a fixture that may have been
    seeded from football-data.org (different source_id).

    Strategy: look for another Fixture row with matching teams + date
    that has source_primary='api-football', or use source_id directly
    if it was seeded from api-football.
    """
    if fixture.source_primary == 'api-football' and fixture.source_id:
        try:
            return int(fixture.source_id)
        except (ValueError, TypeError):
            return None

    # Cross-match by home_team + away_team + date (within same day)
    if not fixture.scheduled_at:
        return None

    day_start = fixture.scheduled_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    twin = Fixture.query.filter(
        Fixture.source_primary == 'api-football',
        Fixture.home_team_id == fixture.home_team_id,
        Fixture.away_team_id == fixture.away_team_id,
        Fixture.scheduled_at >= day_start,
        Fixture.scheduled_at < day_end,
    ).first()

    if twin and twin.source_id:
        try:
            return int(twin.source_id)
        except (ValueError, TypeError):
            pass

    return None
