"""Worker 6 — Download and cache player photos + team crests.

For MVP: downloads to app/static/player_photos/{player_id}.jpg
For production: set CDN_BASE_URL + CDN_UPLOAD_ENDPOINT env vars to push to R2/S3.
"""
import logging
import os
import pathlib
import time

import httpx

from ..models import db, Player
from ..utils.player_utils import generate_svg_fallback

logger = logging.getLogger(__name__)

STATIC_DIR = pathlib.Path(__file__).parent.parent / 'static' / 'player_photos'
CDN_BASE_URL = os.environ.get('CDN_BASE_URL', '')


def run(player_ids: list[int] | None = None, limit: int = 100) -> int:
    """Download photos for players without a local photo URL."""
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    if player_ids:
        players = Player.query.filter(Player.id.in_(player_ids)).all()
    else:
        players = (
            Player.query
            .filter(Player.photo_url_local.is_(None))
            .limit(limit)
            .all()
        )

    processed = 0
    for player in players:
        try:
            processed += _process_player(player)
            time.sleep(0.3)
        except Exception as e:
            logger.error("photo_worker player %d: %s", player.id, e)

    db.session.commit()
    logger.info("player_photo_worker: %d photos processed", processed)
    return processed


def _process_player(player: Player) -> int:
    # Attempt sources in priority order
    sources = [
        player.photo_url_sportsdb_cutout,
        player.photo_url_apifootball,
        player.photo_url_sportsdb_thumb,
    ]

    for url in sources:
        if not url:
            continue
        local_path = _download(url, player.id)
        if local_path:
            player.photo_url_local = _build_local_url(local_path, player.id)
            return 1

    # SVG fallback with initials
    _write_svg_fallback(player)
    return 1


def _download(url: str, player_id: int) -> pathlib.Path | None:
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        ext = _guess_ext(r.headers.get('content-type', ''), url)
        dest = STATIC_DIR / f"{player_id}{ext}"
        dest.write_bytes(r.content)
        return dest
    except Exception as e:
        logger.debug("photo download %s: %s", url, e)
        return None


def _write_svg_fallback(player: Player) -> None:
    initials = ''.join(w[0] for w in (player.name_short or player.name or 'FX').split()[:2])
    svg = generate_svg_fallback(initials)
    dest = STATIC_DIR / f"{player.id}.svg"
    dest.write_text(svg, encoding='utf-8')
    player.photo_url_local = _build_local_url(dest, player.id)


def _build_local_url(path: pathlib.Path, player_id: int) -> str:
    if CDN_BASE_URL:
        return f"{CDN_BASE_URL}/player_photos/{path.name}"
    return f"/static/player_photos/{path.name}"


def _guess_ext(content_type: str, url: str) -> str:
    if 'png' in content_type or url.endswith('.png'):
        return '.png'
    if 'webp' in content_type or url.endswith('.webp'):
        return '.webp'
    return '.jpg'
