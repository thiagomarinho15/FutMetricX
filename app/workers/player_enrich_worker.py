"""Worker — Enrich Player records with nationality, DOB, height via TheSportsDB.

Runs after squad_refresh_worker. Makes one TheSportsDB call per player that
is missing nationality. TheSportsDB is free with no daily quota, but we
respect 1s between requests. Processes in batches to avoid running forever.
"""
import logging
import time
from datetime import date, datetime, timezone

from ..models import db, Player
from ..clients import thesportsdb

logger = logging.getLogger(__name__)

BATCH_SIZE = 100  # max players per run to keep execution time reasonable


def run(batch_size: int = BATCH_SIZE) -> int:
    """Enrich players missing nationality using TheSportsDB.

    Returns number of players updated.
    """
    players = (
        Player.query
        .filter(
            Player.source_name == 'api-football',
            Player.is_active.is_(True),
            Player.nationality.is_(None),
        )
        .limit(batch_size)
        .all()
    )

    updated = 0
    for player in players:
        try:
            if _enrich(player):
                updated += 1
        except Exception as e:
            logger.warning("player_enrich %s: %s", player.name, e)

    db.session.commit()
    logger.info("player_enrich_worker: %d players enriched", updated)
    return updated


def _enrich(player: Player) -> bool:
    time.sleep(1.0)
    info = thesportsdb.search_player(player.name_full or player.name)
    if not info:
        return False

    changed = False

    if not player.nationality and info.get('nationality'):
        player.nationality = info['nationality']
        changed = True

    if not player.date_of_birth and info.get('date_of_birth'):
        try:
            player.date_of_birth = date.fromisoformat(info['date_of_birth'])
            changed = True
        except (ValueError, TypeError):
            pass

    if not player.bio_text and info.get('bio'):
        player.bio_text = info['bio'][:2000]
        changed = True

    if not player.photo_url_sportsdb_cutout and info.get('cutout'):
        player.photo_url_sportsdb_cutout = info['cutout']
        changed = True

    if not player.photo_url_sportsdb_thumb and info.get('thumb'):
        player.photo_url_sportsdb_thumb = info['thumb']
        changed = True

    if not player.external_id_sportsdb and info.get('sportsdb_id'):
        player.external_id_sportsdb = str(info['sportsdb_id'])
        changed = True

    if changed:
        player.updated_at = datetime.now(timezone.utc)

    return changed
