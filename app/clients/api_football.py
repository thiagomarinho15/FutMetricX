import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"

LEAGUE_IDS: dict[str, int] = {
    'Premier League': 39,
    'Champions League': 2,
    'Brasileirão': 71,
    'La Liga': 140,
    'Bundesliga': 78,
    'Serie A': 135,
    'Ligue 1': 61,
}

_last_request_at: float = 0.0
_MIN_INTERVAL = 0.5


def _keys() -> list[str]:
    keys = []
    for i in (1, 2):
        k = os.environ.get(f'API_FOOTBALL_KEY_{i}', '')
        if k:
            keys.append(k)
    k = os.environ.get('API_FOOTBALL_KEY', '')
    if k and k not in keys:
        keys.append(k)
    return keys


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _get(endpoint: str, params: dict | None = None) -> dict:
    _throttle()
    keys = _keys()
    if not keys:
        logger.warning("api-football: no API key configured")
        return {}
    last_exc = None
    for key in keys:
        try:
            r = httpx.get(
                f"{BASE_URL}/{endpoint}",
                headers={'x-apisports-key': key},
                params=params or {},
                timeout=20,
            )
            if r.status_code == 429:
                logger.warning("api-football: key ...%s rate-limited, trying next", key[-6:])
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
    logger.error("api-football %s failed: %s", endpoint, last_exc)
    return {}


def get_fixtures(league_id: int, season: int, date: str | None = None) -> list[dict]:
    params: dict = {'league': league_id, 'season': season}
    if date:
        params['date'] = date
    return _get('fixtures', params).get('response', [])


def get_live_fixtures(league_id: int) -> list[dict]:
    return _get('fixtures', {'league': league_id, 'live': 'all'}).get('response', [])


def get_fixture_stats(fixture_id: int) -> list[dict]:
    return _get('fixtures/statistics', {'fixture': fixture_id}).get('response', [])


def get_fixture_players(fixture_id: int) -> list[dict]:
    return _get('fixtures/players', {'fixture': fixture_id}).get('response', [])


def get_fixture_lineups(fixture_id: int) -> list[dict]:
    return _get('fixtures/lineups', {'fixture': fixture_id}).get('response', [])


def get_squad(team_id: int, season: int) -> list[dict]:
    """Return full squad list for a team in a given season."""
    return _get('players/squads', {'team': team_id, 'season': season}).get('response', [])


def get_player_season_stats(player_id: int, season: int, league_id: int) -> dict:
    """Return the first response block for a player's season aggregated stats."""
    resp = _get('players', {'id': player_id, 'season': season, 'league': league_id}).get('response', [])
    return resp[0] if resp else {}


def get_player_info(player_id: int, season: int) -> dict:
    """Return player identity + stats from the most recent available season."""
    resp = _get('players', {'id': player_id, 'season': season}).get('response', [])
    return resp[0] if resp else {}
