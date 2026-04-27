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

    # ── Player Data Layer workers ──────────────────────────────────────────────

    def _player_season_stats():
        with app.app_context():
            from ..workers.player_season_stats_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_season_stats_worker: %d upserted', n)
            except Exception as e:
                logger.error('player_season_stats_worker: %s', e)

    # every Monday 05:00 UTC — after xg_worker (02:00) and FBref (Sun night)
    _scheduler.add_job(_player_season_stats, 'cron', day_of_week='mon', hour=5, minute=0,
                       id='player_season_stats_worker', replace_existing=True)

    def _player_market_value():
        with app.app_context():
            from ..workers.player_market_value_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_market_value_worker: %d values recorded', n)
            except Exception as e:
                logger.error('player_market_value_worker: %s', e)

    # every Monday 06:00 UTC
    _scheduler.add_job(_player_market_value, 'cron', day_of_week='mon', hour=6, minute=0,
                       id='player_market_value_worker', replace_existing=True)

    def _player_fbref():
        with app.app_context():
            from ..workers.player_fbref_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_fbref_worker: %d updated', n)
            except Exception as e:
                logger.error('player_fbref_worker: %s', e)

    # every Sunday 23:00 UTC — FBref data is usually fresh by end of matchweek
    _scheduler.add_job(_player_fbref, 'cron', day_of_week='sun', hour=23, minute=0,
                       id='player_fbref_worker', replace_existing=True)

    def _player_photos():
        with app.app_context():
            from ..workers.player_photo_worker import run
            try:
                n = run(limit=50)
                if n:
                    logger.info('player_photo_worker: %d photos processed', n)
            except Exception as e:
                logger.error('player_photo_worker: %s', e)

    # every Sunday 22:00 UTC — backfill photos for new players
    _scheduler.add_job(_player_photos, 'cron', day_of_week='sun', hour=22, minute=0,
                       id='player_photo_worker', replace_existing=True)

    def _player_bio():
        with app.app_context():
            from ..workers.player_bio_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_bio_worker: %d bios generated', n)
            except Exception as e:
                logger.error('player_bio_worker: %s', e)

    # 1st of each month at 07:00 UTC
    _scheduler.add_job(_player_bio, 'cron', day=1, hour=7, minute=0,
                       id='player_bio_worker', replace_existing=True)

    def _player_percentiles():
        with app.app_context():
            from ..workers.player_percentiles_worker import run
            try:
                n = run()
                if n:
                    logger.info('player_percentiles_worker: %d rows updated', n)
            except Exception as e:
                logger.error('player_percentiles_worker: %s', e)

    # every Tuesday 03:00 UTC — after Monday's season stats and market value are fresh
    _scheduler.add_job(_player_percentiles, 'cron', day_of_week='tue', hour=3, minute=0,
                       id='player_percentiles_worker', replace_existing=True)

    _scheduler.start()
    logger.info(
        'APScheduler iniciado: news(30min), pregame(00:00), '
        'fixtures(03:00), livescore(1min), player_stats(6h), '
        'xg(seg 02:00), conflicts(1h), team_form(04:00) | '
        'player_season_stats(seg 05:00), market_value(seg 06:00), '
        'fbref(dom 23:00), photos(dom 22:00), bio(dia1 07:00), '
        'percentiles(ter 03:00)'
    )
