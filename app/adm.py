from flask import redirect, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from .models import db, User, Role


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


def init_admin(app):
    admin = Admin(
        app,
        name='FutMetricX Admin',
        index_view=SecureAdminIndex(),
        template_mode='bootstrap4',
    )
    admin.add_view(UserAdmin(User, db.session, name='Usuários'))
    admin.add_view(RoleAdmin(Role, db.session, name='Roles'))
    return admin
