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

    def _pregame_job():
        with app.app_context():
            from datetime import datetime, timezone, timedelta
            from ..models import db, Partida, Relatorio
            from .report_generator import gerar_relatorio_stream, montar_contexto

            now = datetime.now(timezone.utc)
            amanha = now + timedelta(hours=24)
            partidas = Partida.query.filter(
                Partida.status == 'agendada',
                Partida.data_partida >= now,
                Partida.data_partida <= amanha,
            ).all()

            for p in partidas:
                if Relatorio.query.filter_by(partida_id=p.id, tipo='pre_torcedor').first():
                    continue
                try:
                    conteudo = ''.join(gerar_relatorio_stream('pre_torcedor', montar_contexto(p)))
                    rel = Relatorio(tipo='pre_torcedor', partida_id=p.id, conteudo=conteudo)
                    db.session.add(rel)
                    db.session.commit()
                    logger.info('Relatório D-1 gerado: partida %d', p.id)
                except Exception as exc:
                    logger.error('Erro D-1 partida %d: %s', p.id, exc)

    _scheduler.add_job(_pregame_job, 'cron', hour=0, minute=0, id='pregame_reports', replace_existing=True)
    _scheduler.start()
    logger.info('APScheduler iniciado (news 30min, pré-jogo D-1 00:00 UTC)')
