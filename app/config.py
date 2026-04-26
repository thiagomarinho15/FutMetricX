import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ['SECRET_KEY']

    DB_HOST = os.getenv('DB_HOST', 'db')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.environ['DB_NAME']
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    SECURITY_PASSWORD_HASH = 'argon2'
    SECURITY_PASSWORD_SALT = os.environ['SECRET_KEY']
    SECURITY_REGISTERABLE = False
    SECURITY_SEND_REGISTER_EMAIL = False

    FLASK_ADMIN_SWATCH = 'cerulean'

    # Data sources (clients read env vars directly for key rotation)
    FOOTBALL_DATA_API_KEY_1 = os.getenv('FOOTBALL_DATA_API_KEY_1', '')
    FOOTBALL_DATA_API_KEY_2 = os.getenv('FOOTBALL_DATA_API_KEY_2', '')
    API_FOOTBALL_KEY_1 = os.getenv('API_FOOTBALL_KEY_1', '')
    API_FOOTBALL_KEY_2 = os.getenv('API_FOOTBALL_KEY_2', '')
    ODDS_API_KEY_1 = os.getenv('ODDS_API_KEY_1', '')
    ODDS_API_KEY_2 = os.getenv('ODDS_API_KEY_2', '')
