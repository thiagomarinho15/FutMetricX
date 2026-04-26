import logging
import os

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"

SPORT_KEYS: dict[str, str] = {
    'Premier League': 'soccer_epl',
    'Brasileirão': 'soccer_brazil_campeonato',
    'Champions League': 'soccer_uefa_champs_league',
    'La Liga': 'soccer_spain_la_liga',
    'Bundesliga': 'soccer_germany_bundesliga',
    'Serie A': 'soccer_italy_serie_a',
    'Ligue 1': 'soccer_france_ligue_one',
}


def _keys() -> list[str]:
    keys = []
    for i in (1, 2):
        k = os.environ.get(f'ODDS_API_KEY_{i}', '')
        if k:
            keys.append(k)
    k = os.environ.get('ODDS_API_KEY', '')
    if k and k not in keys:
        keys.append(k)
    return keys


def _get(path: str, extra_params: dict | None = None) -> list | dict:
    keys = _keys()
    if not keys:
        logger.warning("odds-api: no API key configured")
        return []
    last_exc = None
    for key in keys:
        try:
            params = {'apiKey': key, **(extra_params or {})}
            r = httpx.get(f"{BASE_URL}/{path}", params=params, timeout=15)
            if r.status_code == 429:
                logger.warning("odds-api: key ...%s rate-limited, trying next", key[-6:])
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
    logger.error("odds-api %s failed: %s", path, last_exc)
    return []


def get_scores(sport_key: str, days_from: int = 1) -> list[dict]:
    data = _get(f"sports/{sport_key}/scores", {'daysFrom': days_from})
    return data if isinstance(data, list) else []


def get_odds(sport_key: str, markets: str = 'h2h') -> list[dict]:
    data = _get(f"sports/{sport_key}/odds", {'markets': markets, 'regions': 'eu'})
    return data if isinstance(data, list) else []
