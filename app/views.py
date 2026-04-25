from collections import defaultdict
from time import time

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app
)
from flask_login import login_user, logout_user, login_required, current_user

from .models import db, User, Partida
from .forms import LoginForm, CadastroForm
from .security import hash_senha, verificar_senha

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
    partidas = Partida.query.order_by(Partida.data_partida.desc()).limit(60).all()
    competicoes = sorted({p.competicao for p in partidas})
    return render_template('index.html', partidas=partidas, competicoes=competicoes)


@bp.route('/partida/<int:partida_id>')
def partida(partida_id):
    p = Partida.query.get_or_404(partida_id)
    return render_template('partida.html', partida=p)
