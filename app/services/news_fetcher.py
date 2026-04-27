import logging
import time
from datetime import datetime, timezone

import feedparser
from sqlalchemy.exc import IntegrityError

from ..models import db, Noticia

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    ('GE Globo',     'https://ge.globo.com/rss/feed.xml'),
    ('UOL Esportes', 'https://rss.uol.com.br/feed/esportes.xml'),
    ('ESPN Soccer',  'https://www.espn.com/espn/rss/soccer/news'),
    ('BBC Football', 'https://feeds.bbci.co.uk/sport/football/rss.xml'),
]


def buscar_noticias() -> int:
    """Fetch all RSS feeds and store new items. Returns count of new items."""
    total = 0
    for fonte, url in RSS_FEEDS:
        try:
            total += _processar_feed(fonte, url)
        except Exception as exc:
            db.session.rollback()
            logger.warning('Feed %s falhou: %s', fonte, exc)
    if total:
        logger.info('%d novas notícias importadas', total)
    return total


def _processar_feed(fonte: str, url: str) -> int:
    feed = feedparser.parse(url)
    added = 0
    for entry in feed.entries[:25]:
        link = (entry.get('link') or '').strip()[:500]
        if not link:
            continue

        # Use no_autoflush so checking for existing URLs doesn't trigger premature flushes
        with db.session.no_autoflush:
            exists = Noticia.query.filter_by(url=link).first()
        if exists:
            continue

        titulo = (entry.get('title') or 'Sem título')[:500]
        publicada_em = _parse_pub_date(entry)

        try:
            db.session.add(Noticia(
                titulo=titulo,
                url=link,
                fonte=fonte,
                publicada_em=publicada_em,
            ))
            db.session.commit()
            added += 1
        except IntegrityError:
            db.session.rollback()
        except Exception as exc:
            db.session.rollback()
            logger.warning('news item %s error: %s', link[:60], exc)

    return added


def _parse_pub_date(entry) -> datetime | None:
    parsed = entry.get('published_parsed') or entry.get('updated_parsed')
    if parsed:
        try:
            return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
        except Exception:
            pass
    return None
