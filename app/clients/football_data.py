import logging
import os

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"

COMPETITION_IDS: dict[str, int] = {
    'Premier League': 2021,
    'Champions League': 2001,
    'Brasileirão': 2013,
    'La Liga': 2014,
    'Bundesliga': 2002,
    'Serie A': 2019,
    'Ligue 1': 2015,
}

STATUS_MAP: dict[str, str] = {
    'SCHEDULED': 'scheduled',
    'TIMED': 'scheduled',
    'IN_PLAY': 'live',
    'PAUSED': 'live',
    'FINISHED': 'finished',
    'POSTPONED': 'postponed',
    'CANCELLED': 'cancelled',
    'SUSPENDED': 'cancelled',
}


def _keys() -> list[str]:
    keys = []
    for i in (1, 2):
        k = os.environ.get(f'FOOTBALL_DATA_API_KEY_{i}', '')
        if k:
            keys.append(k)
    # legacy single-key fallback
    k = os.environ.get('FOOTBALL_DATA_API_KEY', '')
    if k and k not in keys:
        keys.append(k)
    return keys


def _get(path: str, params: dict | None = None) -> dict | list:
    keys = _keys()
    if not keys:
        logger.warning("football-data: no API key configured")
        return {}
    last_exc = None
    for key in keys:
        try:
            r = httpx.get(
                f"{BASE_URL}/{path}",
                headers={'X-Auth-Token': key},
                params=params or {},
                timeout=15,
            )
            if r.status_code == 429:
                logger.warning("football-data: key ...%s rate-limited, trying next", key[-6:])
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code != 429:
                break
        except Exception as e:
            last_exc = e
            break
    logger.error("football-data %s failed: %s", path, last_exc)
    return {}


def get_fixtures(competition_id: int, season: int | None = None,
                 status: str | None = None) -> list[dict]:
    params: dict = {}
    if season:
        params['season'] = season
    if status:
        params['status'] = status
    data = _get(f"competitions/{competition_id}/matches", params)
    return data.get('matches', []) if isinstance(data, dict) else []


def get_standings(competition_id: int) -> dict:
    data = _get(f"competitions/{competition_id}/standings")
    return data if isinstance(data, dict) else {}


def get_live_matches() -> list[dict]:
    """Return ALL currently live matches across every tracked competition in ONE request."""
    data = _get("matches", {"status": "IN_PLAY"})
    return data.get("matches", []) if isinstance(data, dict) else []


def get_matches_today() -> list[dict]:
    """Return all matches scheduled for today (any status) in ONE request."""
    from datetime import date
    today = date.today().isoformat()
    data = _get("matches", {"dateFrom": today, "dateTo": today})
    return data.get("matches", []) if isinstance(data, dict) else []
