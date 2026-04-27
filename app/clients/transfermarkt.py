"""Transfermarkt market value scraper — respectful, with User-Agent."""
import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.transfermarkt.com"
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}
_last_request_at: float = 0.0
_MIN_INTERVAL = 4.0  # be respectful — no official API


def _fetch(url: str) -> BeautifulSoup | None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=30, follow_redirects=True)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser')
    except Exception as e:
        logger.error("transfermarkt fetch %s: %s", url, e)
        return None


def get_market_value(transfermarkt_id: str) -> dict:
    """Return current market value dict for a player by Transfermarkt ID."""
    url = f"{BASE_URL}/player/profil/spieler/{transfermarkt_id}"
    soup = _fetch(url)
    if not soup:
        return {}

    value_eur = None
    try:
        el = soup.find('a', class_='data-header__market-value-wrapper')
        if el:
            raw = el.get_text(strip=True)
            value_eur = _parse_value(raw)
    except Exception as e:
        logger.warning("transfermarkt parse value: %s", e)

    return {'transfermarkt_id': transfermarkt_id, 'value_eur': value_eur}


def search_player_id(name: str, team: str | None = None) -> str | None:
    """Search Transfermarkt for a player and return their ID. Unreliable — use as first pass."""
    query = name.replace(' ', '+')
    url = f"{BASE_URL}/schnellsuche/ergebnis/schnellsuche?query={query}&Spieler_page=0"
    soup = _fetch(url)
    if not soup:
        return None
    try:
        rows = soup.select('table.items tbody tr')
        for row in rows:
            link = row.select_one('td.hauptlink a')
            if not link:
                continue
            href = link.get('href', '')
            m = re.search(r'/spieler/(\d+)', href)
            if not m:
                continue
            if team:
                club_cell = row.select_one('td.zentriert a')
                if club_cell and team.lower() not in club_cell.get_text().lower():
                    continue
            return m.group(1)
    except Exception as e:
        logger.warning("transfermarkt search %r: %s", name, e)
    return None


def _parse_value(raw: str) -> int | None:
    raw = raw.strip().upper().replace(',', '').replace('\xa0', '')
    raw = re.sub(r'[€$£]', '', raw)
    try:
        if 'M' in raw:
            return int(float(raw.replace('M', '')) * 1_000_000)
        if 'K' in raw:
            return int(float(raw.replace('K', '')) * 1_000)
        return int(float(raw))
    except (ValueError, TypeError):
        return None
