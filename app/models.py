from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# ── SSoT Data Layer ────────────────────────────────────────────────────────────


class Competition(db.Model):
    __tablename__ = 'competitions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100))
    season = db.Column(db.String(20), nullable=False)
    source_id = db.Column(db.String(50))
    source_name = db.Column(db.String(50))

    __table_args__ = (
        db.UniqueConstraint('name', 'season', name='uq_competition_season'),
    )

    def __repr__(self):
        return f'<Competition {self.name} {self.season}>'


class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(50))
    country = db.Column(db.String(100))
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'))
    source_id = db.Column(db.String(50))
    source_name = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('source_id', 'source_name', name='uq_team_source'),
    )

    def __repr__(self):
        return f'<Team {self.name}>'


class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    nationality = db.Column(db.String(80))
    position = db.Column(db.String(50))
    age = db.Column(db.Integer)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    source_id = db.Column(db.String(50))
    source_name = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('source_id', 'source_name', name='uq_player_source'),
    )

    def __repr__(self):
        return f'<Player {self.name}>'


class Fixture(db.Model):
    __tablename__ = 'fixtures'
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='scheduled')  # scheduled|live|finished|postponed
    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    source_primary = db.Column(db.String(50))
    source_id = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    competition = db.relationship('Competition', backref='fixtures')
    home_team = db.relationship('Team', foreign_keys=[home_team_id])
    away_team = db.relationship('Team', foreign_keys=[away_team_id])

    __table_args__ = (
        db.UniqueConstraint('source_id', 'source_primary', name='uq_fixture_source'),
    )

    def __repr__(self):
        return f'<Fixture {self.home_team_id}x{self.away_team_id} {self.scheduled_at}>'


class MatchStats(db.Model):
    __tablename__ = 'match_stats'
    id = db.Column(db.Integer, primary_key=True)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'))
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    shots = db.Column(db.Integer)
    shots_on_target = db.Column(db.Integer)
    passes = db.Column(db.Integer)
    pass_accuracy = db.Column(db.Float)
    yellow_cards = db.Column(db.Integer, default=0)
    red_cards = db.Column(db.Integer, default=0)
    minutes_played = db.Column(db.Integer)
    source_name = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('fixture_id', 'player_id', 'source_name', name='uq_match_stats_entry'),
    )

    def __repr__(self):
        return f'<MatchStats fixture={self.fixture_id} player={self.player_id}>'


class AdvancedMetrics(db.Model):
    __tablename__ = 'advanced_metrics'
    id = db.Column(db.Integer, primary_key=True)
    # fixture_id is NULL for season-aggregate rows (Understat season totals)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.id'), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'))
    xg = db.Column(db.Float)
    xa = db.Column(db.Float)
    npxg = db.Column(db.Float)
    xg_chain = db.Column(db.Float)
    xg_buildup = db.Column(db.Float)
    progressive_passes = db.Column(db.Integer)
    pressures = db.Column(db.Integer)
    defensive_actions = db.Column(db.Integer)
    source_name = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<AdvancedMetrics fixture={self.fixture_id} player={self.player_id}>'


class TeamForm(db.Model):
    __tablename__ = 'team_form'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    last_5 = db.Column(db.String(20))   # e.g. "WWDLW"
    last_10 = db.Column(db.String(20))  # e.g. "WWDLWWDLWW"
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_scored = db.Column(db.Integer, default=0)
    goals_conceded = db.Column(db.Integer, default=0)
    xg_avg = db.Column(db.Float)
    xga_avg = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('team_id', 'competition_id', name='uq_team_form'),
    )

    def __repr__(self):
        return f'<TeamForm team={self.team_id} comp={self.competition_id}>'


class DataConflict(db.Model):
    __tablename__ = 'data_conflicts'
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)  # fixture|player|match_stats
    entity_id = db.Column(db.Integer, nullable=False)
    field_name = db.Column(db.String(50), nullable=False)
    value_primary = db.Column(db.String(200))
    value_fallback = db.Column(db.String(200))
    delta = db.Column(db.Float)
    source_primary = db.Column(db.String(50))
    source_fallback = db.Column(db.String(50))
    detected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resolved = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<DataConflict {self.entity_type}#{self.entity_id}.{self.field_name}>'

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    senha = db.Column(db.String(512), nullable=False)
    active = db.Column(db.Boolean, default=True)
    tier = db.Column(db.String(20), default='standard')  # standard | pro | max
    criado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))

    def has_role(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)

    def __repr__(self):
        return f'<User {self.email}>'


class Partida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    statsbomb_id = db.Column(db.Integer, unique=True)
    time_casa = db.Column(db.String(100), nullable=False)
    time_visitante = db.Column(db.String(100), nullable=False)
    competicao = db.Column(db.String(100), nullable=False)
    temporada = db.Column(db.String(20), nullable=False)
    rodada = db.Column(db.Integer)
    data_partida = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='agendada')  # agendada | encerrada
    stats_json = db.Column(db.Text)

    def stats(self):
        import json
        return json.loads(self.stats_json) if self.stats_json else {}

    def __repr__(self):
        return f'<Partida {self.time_casa} x {self.time_visitante}>'


class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    statsbomb_id = db.Column(db.Integer, unique=True)
    nome = db.Column(db.String(120), nullable=False)
    time_atual = db.Column(db.String(100))
    nacionalidade = db.Column(db.String(80))
    posicao = db.Column(db.String(50))
    stats_json = db.Column(db.Text)
    temporada = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Jogador {self.nome}>'


class Relatorio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False)
    # pre_torcedor | pre_profissional | pos | jogador | locutor
    partida_id = db.Column(db.Integer, db.ForeignKey('partida.id'), nullable=True)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.id'), nullable=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=True)
    conteudo = db.Column(db.Text, nullable=False)
    gerado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_tier_minimo = db.Column(db.String(20), default='standard')

    partida = db.relationship('Partida', backref='relatorios')
    fixture = db.relationship('Fixture', backref='relatorios')

    def __repr__(self):
        return f'<Relatorio {self.tipo} partida={self.partida_id}>'


class Noticia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)
    fonte = db.Column(db.String(100))
    publicada_em = db.Column(db.DateTime)
    resumo_impacto = db.Column(db.Text)
    time_relacionado = db.Column(db.String(100))
    jogador_relacionado = db.Column(db.String(120))
    impacto_processado = db.Column(db.Boolean, default=False)
    criada_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Noticia {self.titulo[:40]}>'


class ContextoHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time1 = db.Column(db.String(100), nullable=False)
    time2 = db.Column(db.String(100), nullable=False)
    narrativa = db.Column(db.Text)
    atualizado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ContextoHistorico {self.time1} vs {self.time2}>'
