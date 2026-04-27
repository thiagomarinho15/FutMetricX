"""TheSportsDB API client — player bio, photos, team badges."""
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.thesportsdb.com/api/v1/json"
_last_request_at: float = 0.0
_MIN_INTERVAL = 1.0  # free tier: be gentle


def _api_key() -> str:
    return os.environ.get('SPORTSDB_KEY', '3')  # '3' = public test key (low rate limit)


def _get(path: str, params: dict | None = None) -> dict:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()

    url = f"{BASE_URL}/{_api_key()}/{path}"
    try:
        r = httpx.get(url, params=params or {}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("thesportsdb %s: %s", path, e)
        return {}


def search_player(name: str) -> dict:
    """Search player by name. Returns first match with photo URLs and bio."""
    data = _get('searchplayers.php', {'p': name})
    players = data.get('player') or []
    if not players:
        return {}
    p = players[0]
    return {
        'sportsdb_id': p.get('idPlayer'),
        'name_full': p.get('strPlayer'),
        'nationality': p.get('strNationality'),
        'date_of_birth': p.get('dateBorn'),
        'height': p.get('strHeight'),
        'weight': p.get('strWeight'),
        'bio': p.get('strDescriptionEN') or p.get('strDescriptionPT'),
        'thumb': p.get('strThumb'),
        'cutout': p.get('strCutout'),
        'render': p.get('strRender'),
        'foot': p.get('strPosition'),
    }


def search_team(name: str) -> dict:
    """Return team badge URL from TheSportsDB."""
    data = _get('searchteams.php', {'t': name})
    teams = data.get('teams') or []
    if not teams:
        return {}
    t = teams[0]
    return {
        'sportsdb_id': t.get('idTeam'),
        'badge': t.get('strBadge'),
        'badge_alt': t.get('strBadgeAlternate'),
        'logo': t.get('strLogo'),
    }


def get_player_by_id(sportsdb_id: str) -> dict:
    """Fetch player detail by TheSportsDB ID."""
    data = _get('lookupplayer.php', {'id': sportsdb_id})
    players = data.get('players') or []
    return players[0] if players else {}
