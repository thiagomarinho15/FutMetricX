import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone='UTC')

    # ── existing jobs ──────────────────────────────────────────────────────────

    def _fetch_news():
        with app.app_context():
            from .news_fetcher import buscar_noticias
            n = buscar_noticias()
            if n:
                logger.info('news_fetcher: %d novas notícias', n)

    _scheduler.add_job(_fetch_news, 'interval', minutes=30,
                       id='fetch_news', replace_existing=True)

    def _pregame_reports():
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
                    logger.info('pregame D-1: partida %d gerada', p.id)
                except Exception as exc:
                    logger.error('pregame D-1 partida %d: %s', p.id, exc)

    _scheduler.add_job(_pregame_reports, 'cron', hour=0, minute=0,
                       id='pregame_reports', replace_existing=True)

    # ── SSoT ingestion workers ─────────────────────────────────────────────────

    def _fixtures():
        with app.app_context():
            from ..workers.fixtures_worker import run
            try:
                n = run()
                logger.info('fixtures_worker: %d upserted', n)
            except Exception as e:
                logger.error('fixtures_worker: %s', e)

    # runs at 03:00 UTC daily — fixtures rarely change more than once a day
    _scheduler.add_job(_fixtures, 'cron', hour=3, minute=0,
                       id='fixtures_worker', replace_existing=True)

    def _livescore():
        with app.app_context():
            from ..workers.livescore_worker import run
            try:
                run()
            except Exception as e:
                logger.error('livescore_worker: %s', e)

    # every minute — APScheduler handles skipping if previous run is still active
    _scheduler.add_job(_livescore, 'interval', minutes=1,
                       id='livescore_worker', replace_existing=True)

    def _player_stats():
        with app.app_context():
            from ..workers.player_stats_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_stats_worker: %d records added', n)
            except Exception as e:
                logger.error('player_stats_worker: %s', e)

    # every 6 hours — catches stats for recently finished matches
    _scheduler.add_job(_player_stats, 'interval', hours=6,
                       id='player_stats_worker', replace_existing=True)

    def _xg():
        with app.app_context():
            from ..workers.xg_worker import run
            try:
                n = run()
                logger.info('xg_worker: %d records upserted', n)
            except Exception as e:
                logger.error('xg_worker: %s', e)

    # weekly Monday 02:00 UTC — Understat updates after each round
    _scheduler.add_job(_xg, 'cron', day_of_week='mon', hour=2, minute=0,
                       id='xg_worker', replace_existing=True)

    def _conflicts():
        with app.app_context():
            from ..workers.conflict_resolver import run
            try:
                n = run()
                if n:
                    logger.info('conflict_resolver: %d resolved', n)
            except Exception as e:
                logger.error('conflict_resolver: %s', e)

    _scheduler.add_job(_conflicts, 'interval', hours=1,
                       id='conflict_resolver', replace_existing=True)

    def _team_form():
        with app.app_context():
            from ..workers.team_form_worker import run
            try:
                n = run()
                if n:
                    logger.info('team_form_worker: %d updated', n)
            except Exception as e:
                logger.error('team_form_worker: %s', e)

    # daily at 04:00 UTC — after fixtures_worker (03:00) and player_stats settle
    _scheduler.add_job(_team_form, 'cron', hour=4, minute=0,
                       id='team_form_worker', replace_existing=True)

    _scheduler.start()
    logger.info(
        'APScheduler iniciado: news(30min), pregame(00:00), '
        'fixtures(03:00), livescore(1min), player_stats(6h), '
        'xg(seg 02:00), conflicts(1h), team_form(04:00)'
    )
