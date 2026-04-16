import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OFFLINE_MODE = True
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    ACCOUNT_LOCK_DURATION_MINUTES = 15
    MAX_TRUSTED_DEVICES = 5
    DEFAULT_SERVICE_RADIUS_MILES = 25
    SEARCH_SLA_SECONDS = 2
    ANOMALY_READ_THRESHOLD = 50
    ANOMALY_READ_WINDOW_MINUTES = 10
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    # Separate key paths — DB-level (SQLCipher hex) vs field-level (Fernet)
    DB_ENCRYPTION_KEY_PATH = os.environ.get(
        'DB_ENCRYPTION_KEY_PATH',
        os.path.join(basedir, 'instance', 'db_encryption.key'),
    )
    FIELD_ENCRYPTION_KEY_PATH = os.environ.get(
        'FIELD_ENCRYPTION_KEY_PATH',
        os.path.join(basedir, 'instance', 'field_encryption.key'),
    )
    SQLCIPHER_ENABLED = os.environ.get('SQLCIPHER_ENABLED', '').lower() in ('1', 'true', 'yes')


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "dev.db")}'


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLCIPHER_ENABLED = True
    # Production uses the sqlcipher3 DBAPI driver via creator function
    # (configured in app/__init__.py _setup_db_encryption).
    # The URI is set to plain sqlite path; the creator overrides the connection.
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "prod.db")}'


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
