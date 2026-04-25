from flask import Flask, request
from flask_login import LoginManager
from flask_migrate import Migrate

from .config import Config
from .models import db, User
from .adm import init_admin
from .services.team_logos import team_logo, team_initial, team_color

login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    init_admin(app)

    app.jinja_env.globals.update(
        team_logo=team_logo,
        team_initial=team_initial,
        team_color=team_color,
    )

    from .views import bp
    app.register_blueprint(bp)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://upload.wikimedia.org;"
        )
        return response

    return app


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
