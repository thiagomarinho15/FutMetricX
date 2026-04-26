from collections import defaultdict
from time import time

import json
import logging

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, Response, stream_with_context,
    send_from_directory
)
from flask_login import login_user, logout_user, login_required, current_user

from .models import db, User, Partida, Jogador, Relatorio, Noticia, ContextoHistorico, Fixture, MatchStats, TeamForm
from .forms import LoginForm, CadastroForm
from .security import hash_senha, verificar_senha

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

# In-memory rate limit: 5 tentativas / 60s por IP
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 60


def _check_rate_limit(ip: str) -> bool:
    now = time()
    attempts = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) < _RATE_LIMIT


def _record_attempt(ip: str):
    _login_attempts[ip].append(time())


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        ip = request.remote_addr

        if not _check_rate_limit(ip):
            flash('Muitas tentativas. Aguarde um minuto.', 'danger')
            return render_template('login.html', form=form)

        _record_attempt(ip)

        user = User.query.filter_by(email=form.email.data.lower()).first()
        # Same message for "not found" and "wrong password" — prevents enumeration
        if not user or not verificar_senha(user.senha, form.senha.data):
            flash('Email ou senha inválidos.', 'danger')
            return render_template('login.html', form=form)

        if not user.active:
            flash('Conta desativada. Entre em contato com o suporte.', 'warning')
            return render_template('login.html', form=form)

        login_user(user, remember=form.lembrar.data)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.index'))

    return render_template('login.html', form=form)


@bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = CadastroForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'warning')
            return render_template('cadastro.html', form=form)

        user = User(
            nome=form.nome.data,
            email=email,
            senha=hash_senha(form.senha.data),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('main.index'))

    return render_template('cadastro.html', form=form)


@bp.route('/sair')
@login_required
def sair():
    logout_user()
    return redirect(url_for('main.login'))


# ---------------------------------------------------------------------------
# Páginas principais
# ---------------------------------------------------------------------------

@bp.route('/')
def index():
    from datetime import datetime, timezone, timedelta
    from .models import Fixture, Competition, Team

    date_str = request.args.get('date')
    today = datetime.now(timezone.utc).date()
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today
    except ValueError:
        selected_date = today

    day_start = datetime(selected_date.year, selected_date.month, selected_date.day,
                         tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    fixtures = (
        Fixture.query
        .filter(Fixture.scheduled_at >= day_start, Fixture.scheduled_at < day_end)
        .order_by(Fixture.scheduled_at)
        .all()
    )

    # Group by competition name preserving order of first appearance
    groups: dict[str, dict] = {}
    for f in fixtures:
        comp_name = f.competition.name if f.competition else 'Outras'
        if comp_name not in groups:
            groups[comp_name] = {'fixtures': [], 'competition': f.competition}
        groups[comp_name]['fixtures'].append(f)

    # Build date strip: yesterday, today, next 5 days
    dates = [today + timedelta(days=i) for i in range(-1, 6)]

    # Recent results for sidebar (last 5 finished fixtures across all comps)
    recent = (
        Fixture.query
        .filter(Fixture.status == 'finished')
        .order_by(Fixture.scheduled_at.desc())
        .limit(5)
        .all()
    )

    return render_template('index.html',
                           fixture_groups=groups,
                           selected_date=selected_date,
                           today=today,
                           dates=dates,
                           recent=recent)


@bp.route('/jogo/<int:fixture_id>')
def jogo(fixture_id):
    from sqlalchemy import or_
    f = Fixture.query.get_or_404(fixture_id)

    home_stats = (MatchStats.query
                  .filter_by(fixture_id=fixture_id, team_id=f.home_team_id)
                  .all())
    away_stats = (MatchStats.query
                  .filter_by(fixture_id=fixture_id, team_id=f.away_team_id)
                  .all())

    form_home = TeamForm.query.filter_by(
        team_id=f.home_team_id, competition_id=f.competition_id).first()
    form_away = TeamForm.query.filter_by(
        team_id=f.away_team_id, competition_id=f.competition_id).first()

    h2h = (Fixture.query
           .filter(
               Fixture.status == 'finished',
               Fixture.id != fixture_id,
               or_(
                   (Fixture.home_team_id == f.home_team_id) & (Fixture.away_team_id == f.away_team_id),
                   (Fixture.home_team_id == f.away_team_id) & (Fixture.away_team_id == f.home_team_id),
               )
           )
           .order_by(Fixture.scheduled_at.desc())
           .limit(8)
           .all())

    rels = {r.tipo: r for r in Relatorio.query.filter_by(fixture_id=fixture_id).all()}

    # aggregate stats for stat bars
    def _agg(stats_list):
        agg = dict(goals=0, assists=0, shots=0, shots_on_target=0,
                   passes=0, yellow_cards=0, red_cards=0)
        for s in stats_list:
            agg['goals'] += s.goals or 0
            agg['assists'] += s.assists or 0
            agg['shots'] += s.shots or 0
            agg['shots_on_target'] += s.shots_on_target or 0
            agg['passes'] += s.passes or 0
            agg['yellow_cards'] += s.yellow_cards or 0
            agg['red_cards'] += s.red_cards or 0
        return agg

    return render_template('jogo.html',
                           fixture=f,
                           home_stats=home_stats,
                           away_stats=away_stats,
                           home_agg=_agg(home_stats),
                           away_agg=_agg(away_stats),
                           form_home=form_home,
                           form_away=form_away,
                           h2h=h2h,
                           relatorios=rels)


@bp.route('/jogo/<int:fixture_id>/gerar')
@login_required
def gerar_relatorio_fixture(fixture_id):
    from .services.report_generator import gerar_relatorio_stream, montar_contexto_fixture

    fixture_obj = Fixture.query.get_or_404(fixture_id)
    tipo = request.args.get('tipo', 'pre_torcedor')

    _PRO_TIPOS = ('pre_profissional', 'locutor')
    if tipo in _PRO_TIPOS and current_user.tier == 'standard':
        def _denied():
            yield f"data: {json.dumps({'error': 'Modo Profissional requer conta Pro ou superior.'})}\n\n"
        return Response(_denied(), content_type='text/event-stream')

    existing = Relatorio.query.filter_by(fixture_id=fixture_id, tipo=tipo).first()
    if existing:
        def _cached():
            yield f"data: {json.dumps({'texto': existing.conteudo, 'done': True})}\n\n"
        return Response(_cached(), content_type='text/event-stream')

    ctx = montar_contexto_fixture(fixture_obj)

    def _stream():
        chunks = []
        try:
            for chunk in gerar_relatorio_stream(tipo, ctx):
                chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            conteudo = ''.join(chunks)
            rel = Relatorio(tipo=tipo, fixture_id=fixture_id, conteudo=conteudo)
            db.session.add(rel)
            db.session.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error('Erro na geração fixture: %s', exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/partida/<int:partida_id>')
def partida(partida_id):
    p = Partida.query.get_or_404(partida_id)
    rels = {r.tipo: r for r in Relatorio.query.filter_by(partida_id=partida_id).all()}
    jogadores_casa = Jogador.query.filter_by(time_atual=p.time_casa).order_by(Jogador.nome).limit(25).all()
    jogadores_vis  = Jogador.query.filter_by(time_atual=p.time_visitante).order_by(Jogador.nome).limit(25).all()
    return render_template('partida.html', partida=p, relatorios=rels,
                           jogadores_casa=jogadores_casa, jogadores_visitante=jogadores_vis)


@bp.route('/jogador/<int:jogador_id>')
def jogador(jogador_id):
    j = Jogador.query.get_or_404(jogador_id)
    rel = Relatorio.query.filter_by(jogador_id=jogador_id, tipo='perfil_jogador').first()
    return render_template('jogador.html', jogador=j, relatorio=rel)


@bp.route('/jogador/<int:jogador_id>/gerar')
@login_required
def gerar_perfil_jogador(jogador_id):
    from .services.report_generator import gerar_relatorio_stream, montar_contexto_jogador

    j = Jogador.query.get_or_404(jogador_id)

    existing = Relatorio.query.filter_by(jogador_id=jogador_id, tipo='perfil_jogador').first()
    if existing:
        def _cached():
            yield f"data: {json.dumps({'texto': existing.conteudo, 'done': True})}\n\n"
        return Response(_cached(), content_type='text/event-stream')

    ctx = montar_contexto_jogador(j)

    def _stream():
        chunks = []
        try:
            for chunk in gerar_relatorio_stream('perfil_jogador', ctx):
                chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            conteudo = ''.join(chunks)
            rel = Relatorio(tipo='perfil_jogador', jogador_id=jogador_id, conteudo=conteudo)
            db.session.add(rel)
            db.session.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error('Erro no perfil: %s', exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ---------------------------------------------------------------------------
# PWA helpers
# ---------------------------------------------------------------------------

@bp.route('/sw.js')
def service_worker():
    import os
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'js'),
        'sw.js',
        mimetype='application/javascript',
    )


# ---------------------------------------------------------------------------
# Notícias
# ---------------------------------------------------------------------------

@bp.route('/noticias')
def noticias():
    page = request.args.get('page', 1, type=int)
    paginacao = (
        Noticia.query
        .order_by(Noticia.publicada_em.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template('noticias.html', noticias=paginacao)


@bp.route('/noticias/<int:noticia_id>/impacto')
@login_required
def analisar_impacto(noticia_id):
    from .services.report_generator import gerar_relatorio_stream

    n = Noticia.query.get_or_404(noticia_id)

    if n.impacto_processado and n.resumo_impacto:
        def _cached():
            yield f"data: {json.dumps({'texto': n.resumo_impacto, 'done': True})}\n\n"
        return Response(_cached(), content_type='text/event-stream')

    ctx = {'titulo': n.titulo, 'fonte': n.fonte or ''}

    def _stream_impacto():
        chunks = []
        try:
            for chunk in gerar_relatorio_stream('impacto_noticia', ctx):
                chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            conteudo = ''.join(chunks)
            n.resumo_impacto = conteudo
            n.impacto_processado = True
            db.session.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error('Erro no impacto: %s', exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream_impacto()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ---------------------------------------------------------------------------
# Brasileiros no exterior
# ---------------------------------------------------------------------------

@bp.route('/brasileiros')
def brasileiros():
    jogadores = (
        Jogador.query
        .filter(Jogador.nacionalidade.ilike('%Brazil%'))
        .order_by(Jogador.time_atual, Jogador.nome)
        .all()
    )
    times: dict[str, list] = {}
    for j in jogadores:
        times.setdefault(j.time_atual or 'Outros', []).append(j)
    return render_template('brasileiros.html', times=times, total=len(jogadores))


# ---------------------------------------------------------------------------
# Retrospecto histórico (SSE)
# ---------------------------------------------------------------------------

@bp.route('/partida/<int:partida_id>/retrospecto')
@login_required
def retrospecto(partida_id):
    from .services.report_generator import gerar_relatorio_stream

    p = Partida.query.get_or_404(partida_id)
    existing = (
        ContextoHistorico.query
        .filter(
            ((ContextoHistorico.time1 == p.time_casa) & (ContextoHistorico.time2 == p.time_visitante)) |
            ((ContextoHistorico.time1 == p.time_visitante) & (ContextoHistorico.time2 == p.time_casa))
        ).first()
    )
    if existing and existing.narrativa:
        def _cached():
            yield f"data: {json.dumps({'texto': existing.narrativa, 'done': True})}\n\n"
        return Response(_cached(), content_type='text/event-stream')

    ctx = {'time1': p.time_casa, 'time2': p.time_visitante}

    def _stream_retro():
        chunks = []
        try:
            for chunk in gerar_relatorio_stream('retrospecto', ctx):
                chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            narrativa = ''.join(chunks)
            ch = ContextoHistorico(time1=p.time_casa, time2=p.time_visitante, narrativa=narrativa)
            db.session.add(ch)
            db.session.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error('Erro no retrospecto: %s', exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream_retro()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/partida/<int:partida_id>/gerar')
@login_required
def gerar_relatorio(partida_id):
    from .services.report_generator import gerar_relatorio_stream, montar_contexto

    partida_obj = Partida.query.get_or_404(partida_id)
    tipo = request.args.get('tipo', 'pre_torcedor')

    # Tier gate: professional modes require pro+
    _PRO_TIPOS = ('pre_profissional', 'locutor')
    if tipo in _PRO_TIPOS and current_user.tier == 'standard':
        def _denied():
            yield f"data: {json.dumps({'error': 'Modo Profissional requer conta Pro ou superior.'})}\n\n"
        return Response(_denied(), content_type='text/event-stream')

    # Serve cached report if available
    existing = Relatorio.query.filter_by(partida_id=partida_id, tipo=tipo).first()
    if existing:
        def _cached():
            yield f"data: {json.dumps({'texto': existing.conteudo, 'done': True})}\n\n"
        return Response(_cached(), content_type='text/event-stream')

    ctx = montar_contexto(partida_obj)

    def _stream():
        chunks = []
        try:
            for chunk in gerar_relatorio_stream(tipo, ctx):
                chunks.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            conteudo = ''.join(chunks)
            rel = Relatorio(tipo=tipo, partida_id=partida_id, conteudo=conteudo)
            db.session.add(rel)
            db.session.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error('Erro na geração: %s', exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return Response(
        stream_with_context(_stream()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
