"""API-Football daily request budget tracker.

Stores the count in Redis (key: fmx:apifootball:used:YYYYMMDD, TTL 48h).
Falls back to an in-memory counter if Redis is unavailable.
"""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 100 req/day × 2 keys
TOTAL_DAILY_BUDGET = int(os.environ.get('APIFOOTBALL_DAILY_BUDGET', '200'))
# Hard stop: don't make requests above this threshold
HARD_LIMIT = int(os.environ.get('APIFOOTBALL_HARD_LIMIT', '190'))

_fallback_counter: dict[str, int] = {}   # date_str → count (used if Redis down)
_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()
        return _redis_client
    except Exception:
        return None


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime('fmx:apifootball:used:%Y%m%d')


def get_used() -> int:
    """Return number of API-Football requests consumed today."""
    r = _redis()
    if r:
        try:
            val = r.get(_today_key())
            return int(val) if val else 0
        except Exception:
            pass
    key = _today_key()
    return _fallback_counter.get(key, 0)


def get_remaining() -> int:
    """Return estimated remaining budget for today."""
    return max(0, TOTAL_DAILY_BUDGET - get_used())


def consume(n: int = 1) -> bool:
    """
    Record n consumed requests.
    Returns True if the consumption was within budget, False if over the hard limit.
    """
    used = get_used()
    if used >= HARD_LIMIT:
        logger.warning(
            "budget_tracker: API-Football hard limit reached (%d/%d) — skipping request",
            used, TOTAL_DAILY_BUDGET,
        )
        return False

    r = _redis()
    key = _today_key()
    if r:
        try:
            pipe = r.pipeline()
            pipe.incrby(key, n)
            pipe.expire(key, 172800)  # 48h TTL
            new_val = pipe.execute()[0]
            if new_val >= TOTAL_DAILY_BUDGET * 0.8:
                logger.warning(
                    "budget_tracker: API-Football budget at %d/%d (%.0f%%)",
                    new_val, TOTAL_DAILY_BUDGET, new_val / TOTAL_DAILY_BUDGET * 100,
                )
            return True
        except Exception:
            pass

    # fallback in-memory
    _fallback_counter[key] = _fallback_counter.get(key, 0) + n
    return True


def reset_today() -> None:
    """Force-reset today's counter (use in tests or after a key rotation)."""
    r = _redis()
    key = _today_key()
    if r:
        try:
            r.delete(key)
            return
        except Exception:
            pass
    _fallback_counter.pop(key, None)


def status_line() -> str:
    used = get_used()
    return f"API-Football budget: {used}/{TOTAL_DAILY_BUDGET} ({used/TOTAL_DAILY_BUDGET*100:.0f}%)"
