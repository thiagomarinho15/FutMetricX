"""Admin-only endpoints to trigger data workers manually.

POST /admin/workers/<name>  — starts the worker in a background thread
GET  /admin/workers/status  — lists recent worker runs
"""
import threading
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, redirect, url_for
from flask_login import current_user

from .models import db, WorkerLog

logger = logging.getLogger(__name__)

workers_bp = Blueprint('workers', __name__, url_prefix='/admin/workers')

_ALLOWED_WORKERS = {
    'squad-refresh',
    'fixtures',
    'xg',
    'player-seed',
    'team-dedup',
    'player-season-stats',
    'player-percentiles',
    'news',
}


def _require_admin():
    if not current_user.is_authenticated or not current_user.has_role('admin'):
        return jsonify({'error': 'Acesso negado'}), 403
    return None


@workers_bp.route('/status')
def status():
    guard = _require_admin()
    if guard:
        return guard
    logs = WorkerLog.query.order_by(WorkerLog.started_at.desc()).limit(50).all()
    return jsonify([
        {
            'id': l.id,
            'worker': l.worker_name,
            'status': l.status,
            'started_at': l.started_at.isoformat() if l.started_at else None,
            'finished_at': l.finished_at.isoformat() if l.finished_at else None,
            'rows_affected': l.rows_affected,
            'error': l.error_msg,
        }
        for l in logs
    ])


@workers_bp.route('/<worker_name>', methods=['POST'])
def trigger(worker_name: str):
    guard = _require_admin()
    if guard:
        return guard

    if worker_name not in _ALLOWED_WORKERS:
        return jsonify({'error': f'Worker desconhecido: {worker_name}'}), 400

    league = request.form.get('league') or request.json.get('league') if request.is_json else request.form.get('league')

    log = WorkerLog(worker_name=worker_name, status='running', started_at=datetime.now(timezone.utc))
    db.session.add(log)
    db.session.commit()
    log_id = log.id

    from flask import current_app
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            _log = WorkerLog.query.get(log_id)
            try:
                rows = _dispatch(worker_name, league)
                _log.status = 'done'
                _log.rows_affected = rows
            except Exception as e:
                logger.error("worker %s failed: %s", worker_name, e)
                _log.status = 'error'
                _log.error_msg = str(e)[:500]
            finally:
                _log.finished_at = datetime.now(timezone.utc)
                db.session.commit()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({'job_id': log_id, 'worker': worker_name, 'status': 'running'})


def _dispatch(worker_name: str, league: str | None) -> int:
    if worker_name == 'squad-refresh':
        from .workers.squad_refresh_worker import run
        return run(league)
    if worker_name == 'fixtures':
        from .workers.fixtures_worker import run
        return run()
    if worker_name == 'xg':
        from .workers.xg_worker import run
        return run(league)
    if worker_name == 'player-seed':
        from .workers.player_seed_worker import run
        return run(league)
    if worker_name == 'team-dedup':
        from .workers.team_dedup_worker import run
        return run()
    if worker_name == 'player-season-stats':
        from .workers.player_season_stats_worker import run
        return run(league)
    if worker_name == 'player-percentiles':
        from .workers.player_percentiles_worker import run
        return run()
    if worker_name == 'news':
        from .services.news_fetcher import buscar_noticias
        return buscar_noticias()
    return 0
