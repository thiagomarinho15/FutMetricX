from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

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
