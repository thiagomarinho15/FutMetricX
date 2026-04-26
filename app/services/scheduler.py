import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone='UTC')

    def _fetch_job():
        with app.app_context():
            from .news_fetcher import buscar_noticias
            n = buscar_noticias()
            if n:
                logger.info('Scheduler: %d novas notícias', n)

    _scheduler.add_job(_fetch_job, 'interval', minutes=30, id='fetch_news', replace_existing=True)
    _scheduler.start()
    logger.info('APScheduler iniciado (fetch a cada 30min)')
