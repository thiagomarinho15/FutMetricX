"""Worker 4 — Weekly Transfermarkt market value scrape.

Runs every Monday. Fetches current market value for players that have
a transfermarkt_id mapped, inserts a dated snapshot into PlayerMarketValue.
"""
import logging
from datetime import date, datetime, timezone

from ..models import db, Player, PlayerMarketValue
from ..clients.transfermarkt import get_market_value, search_player_id

logger = logging.getLogger(__name__)


def run(player_ids: list[int] | None = None) -> int:
    """Scrape market values. If player_ids given, process only those."""
    if player_ids:
        players = Player.query.filter(Player.id.in_(player_ids)).all()
    else:
        # Only process players that already have a Transfermarkt ID
        players = Player.query.filter(Player.external_id_transfermarkt.isnot(None)).all()

    today = date.today()
    updated = 0
    for player in players:
        try:
            updated += _process(player, today)
        except Exception as e:
            logger.error("market_value_worker player %d: %s", player.id, e)

    db.session.commit()
    logger.info("player_market_value_worker: %d values recorded", updated)
    return updated


def discover_transfermarkt_ids(limit: int = 50) -> int:
    """Auto-discover Transfermarkt IDs for players without one.

    Uses name search — results should be manually verified for top players.
    """
    players = Player.query.filter(Player.external_id_transfermarkt.is_(None)).limit(limit).all()
    found = 0
    for player in players:
        try:
            tm_id = search_player_id(player.name_full or player.name)
            if tm_id:
                player.external_id_transfermarkt = tm_id
                from ..models import PlayerIdMapping
                existing = PlayerIdMapping.query.filter_by(
                    source='transfermarkt', external_id=tm_id,
                ).first()
                if not existing:
                    db.session.add(PlayerIdMapping(
                        player_id=player.id,
                        source='transfermarkt',
                        external_id=tm_id,
                        confidence='auto',
                    ))
                found += 1
        except Exception as e:
            logger.warning("discover_tm_id %s: %s", player.name, e)

    db.session.commit()
    logger.info("discover_transfermarkt_ids: %d mapped", found)
    return found


def _process(player: Player, today: date) -> int:
    tm_id = player.external_id_transfermarkt
    if not tm_id:
        return 0

    # Skip if we already have today's value
    if PlayerMarketValue.query.filter_by(player_id=player.id, value_date=today).first():
        return 0

    result = get_market_value(tm_id)
    value_eur = result.get('value_eur')
    if value_eur is None:
        return 0

    db.session.add(PlayerMarketValue(
        player_id=player.id,
        value_eur=value_eur,
        value_date=today,
        team_id=player.team_id,
        source='transfermarkt',
    ))
    return 1
