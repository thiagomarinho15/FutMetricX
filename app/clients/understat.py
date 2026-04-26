import json
import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://understat.com"

# Understat league slug → FutMetricX competition name
LEAGUES: dict[str, str] = {
    'Premier League': 'EPL',
    'La Liga': 'La_liga',
    'Bundesliga': 'Bundesliga',
    'Serie A': 'Serie_A',
    'Ligue 1': 'Ligue_1',
}

_REQUEST_INTERVAL = 6  # seconds between requests — respectful rate limit


def _fetch(url: str) -> str | None:
    time.sleep(_REQUEST_INTERVAL)
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True,
                      headers={'User-Agent': 'Mozilla/5.0 (compatible; FutMetricX/1.0)'})
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.error("understat fetch %s: %s", url, e)
        return None


def _extract(html: str, var_name: str):
    """Extract JSON embedded as: var varName = JSON.parse('...')"""
    pattern = re.compile(
        rf"var\s+{re.escape(var_name)}\s*=\s*JSON\.parse\('(.+?)'\)",
        re.DOTALL,
    )
    m = pattern.search(html)
    if not m:
        return None
    try:
        raw = m.group(1).encode('utf-8').decode('unicode_escape')
        return json.loads(raw)
    except Exception as e:
        logger.error("understat _extract(%s): %s", var_name, e)
        return None


def get_league_players(league: str, season: int) -> list[dict]:
    slug = LEAGUES.get(league)
    if not slug:
        logger.warning("understat: league %r not supported", league)
        return []
    html = _fetch(f"{BASE_URL}/league/{slug}/{season}")
    if not html:
        return []
    data = _extract(html, 'playersData')
    return data if isinstance(data, list) else []


def get_league_fixtures(league: str, season: int) -> list[dict]:
    slug = LEAGUES.get(league)
    if not slug:
        return []
    html = _fetch(f"{BASE_URL}/league/{slug}/{season}")
    if not html:
        return []
    data = _extract(html, 'datesData')
    return data if isinstance(data, list) else []


def get_match_shots(match_id: int) -> dict:
    html = _fetch(f"{BASE_URL}/match/{match_id}")
    if not html:
        return {}
    data = _extract(html, 'shotsData')
    return data if isinstance(data, dict) else {}
