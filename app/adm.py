from flask import redirect, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from .models import db, User, Role, Partida, Jogador, Relatorio, Noticia, ContextoHistorico


class AdminAccessMixin:
    def is_accessible(self):
        return current_user.is_authenticated and current_user.has_role('admin')

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('main.login'))


class SecureAdminIndex(AdminAccessMixin, AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')


class UserAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'nome', 'email', 'tier', 'active', 'criado_em', 'roles')
    column_searchable_list = ('email', 'nome')
    column_filters = ('tier', 'active')
    form_excluded_columns = ('senha',)
    can_delete = False


class RoleAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'name', 'description')


class PartidaAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'competicao', 'temporada', 'rodada', 'time_casa', 'time_visitante', 'data_partida', 'status')
    column_searchable_list = ('time_casa', 'time_visitante', 'competicao')
    column_filters = ('competicao', 'temporada', 'status')
    column_default_sort = ('data_partida', True)
    can_create = False


class JogadorAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'nome', 'time_atual', 'posicao', 'nacionalidade', 'temporada', 'ativo')
    column_searchable_list = ('nome', 'time_atual')
    column_filters = ('ativo', 'posicao', 'temporada')


class RelatorioAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'tipo', 'partida_id', 'user_tier_minimo', 'gerado_em')
    column_filters = ('tipo', 'user_tier_minimo')
    can_create = False
    can_edit = False


class NoticiaAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'titulo', 'fonte', 'publicada_em', 'impacto_processado')
    column_searchable_list = ('titulo', 'fonte')
    column_filters = ('fonte', 'impacto_processado')
    column_default_sort = ('publicada_em', True)
    can_create = False


class ContextoHistoricoAdmin(AdminAccessMixin, ModelView):
    column_list = ('id', 'time1', 'time2', 'atualizado_em')
    column_searchable_list = ('time1', 'time2')


def init_admin(app):
    admin = Admin(
        app,
        name='FutMetricX Admin',
        index_view=SecureAdminIndex(),
        template_mode='bootstrap4',
    )
    admin.add_view(UserAdmin(User, db.session, name='Usuários'))
    admin.add_view(RoleAdmin(Role, db.session, name='Roles'))
    admin.add_view(PartidaAdmin(Partida, db.session, name='Partidas'))
    admin.add_view(JogadorAdmin(Jogador, db.session, name='Jogadores'))
    admin.add_view(RelatorioAdmin(Relatorio, db.session, name='Relatórios'))
    admin.add_view(NoticiaAdmin(Noticia, db.session, name='Notícias'))
    admin.add_view(ContextoHistoricoAdmin(ContextoHistorico, db.session, name='Histórico'))
    return admin
