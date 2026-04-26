import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db, User, Role
from app.security import hash_senha
from app.services.data_fetcher import popular_partidas_iniciais, importar_jogadores_iniciais

app = create_app()

with app.app_context():
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        admin_role = Role(name='admin', description='Administrador do sistema')
        db.session.add(admin_role)

    for tier in ('standard', 'pro', 'max'):
        if not Role.query.filter_by(name=tier).first():
            db.session.add(Role(name=tier, description=f'Tier {tier}'))

    db.session.flush()

    admin_email = os.environ['ADMIN_EMAIL']
    if not User.query.filter_by(email=admin_email).first():
        admin_user = User(
            nome='Admin',
            email=admin_email,
            senha=hash_senha(os.environ['ADMIN_PASSWORD']),
            tier='max',
        )
        admin_user.roles.append(admin_role)
        db.session.add(admin_user)

    db.session.commit()
    print('Seed de usuários/roles concluído.')

    print('Importando partidas do StatsBomb Open Data...')
    popular_partidas_iniciais()
    print('Importando jogadores (lineups)...')
    importar_jogadores_iniciais()
    print('Seed concluído.')
