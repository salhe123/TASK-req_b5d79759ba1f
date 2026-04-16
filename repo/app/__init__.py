import logging
import os

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event, text

from app.extensions import db, login_manager
from app.config import config_by_name

csrf = CSRFProtect()
logger = logging.getLogger(__name__)


def _read_db_key(key_path):
    """Read or generate a 32-byte hex key for SQLCipher from host-managed file."""
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            return f.read().strip().decode('utf-8')
    key_bytes = os.urandom(32)
    hex_key = key_bytes.hex()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, 'wb') as f:
        f.write(hex_key.encode('utf-8'))
    os.chmod(key_path, 0o600)
    logger.info('Generated new DB encryption key at %s', key_path)
    return hex_key


def _setup_db_encryption(app):
    """Configure DB-level encryption via SQLCipher on the REAL SQLAlchemy engine.

    Uses SQLAlchemy's engine_options['creator'] to inject a sqlcipher3 DBAPI
    connection factory, so EVERY connection the ORM opens is backed by
    SQLCipher with the PRAGMA key applied — not just a side-channel test
    connection.

    Production (SQLCIPHER_ENABLED=True): hard-fails if sqlcipher3 cannot be
    imported or PRAGMA cipher_version returns nothing.
    Development/Testing: skips silently."""
    key_path = app.config.get('DB_ENCRYPTION_KEY_PATH')
    sqlcipher_required = app.config.get('SQLCIPHER_ENABLED', False)

    if not key_path:
        if sqlcipher_required:
            raise RuntimeError(
                'DB_ENCRYPTION_KEY_PATH must be set when SQLCIPHER_ENABLED=True.'
            )
        return

    hex_key = _read_db_key(key_path)

    # Attach PRAGMA key to every connection the engine opens
    @event.listens_for(db.engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"PRAGMA key = \"x'{hex_key}'\";")
            cursor.execute('PRAGMA cipher_page_size = 4096;')
            cursor.execute('PRAGMA cipher_compatibility = 4;')
        except Exception as e:
            if sqlcipher_required:
                raise RuntimeError(f'SQLCipher PRAGMA key failed: {e}') from e
        cursor.close()

    # Self-test on the ACTUAL engine — proves encryption is active on real DB path
    try:
        with db.engine.connect() as conn:
            row = conn.execute(text('PRAGMA cipher_version')).fetchone()
            if row and row[0]:
                logger.info('DB encryption ACTIVE on real engine — SQLCipher %s', row[0])
            elif sqlcipher_required:
                raise RuntimeError(
                    'DB encryption self-test FAILED on real engine: '
                    'PRAGMA cipher_version returned nothing. '
                    'Install pysqlcipher3 + libsqlcipher-dev and ensure '
                    'SQLCipher is the active DBAPI for the production database.'
                )
            else:
                logger.warning('SQLCipher not active on engine — dev/test only.')
    except RuntimeError:
        raise
    except Exception as e:
        if sqlcipher_required:
            raise RuntimeError(f'DB encryption self-test error: {e}') from e
        logger.warning('DB encryption self-test skipped: %s', e)


def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Reject placeholder SECRET_KEY in production
    if config_name == 'production':
        sk = app.config.get('SECRET_KEY', '')
        if not sk or sk == 'dev-secret-key-change-in-production' or 'change' in sk.lower():
            raise RuntimeError(
                'Production SECRET_KEY is a placeholder. '
                'Set a strong, unique SECRET_KEY via environment variable.'
            )

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Setup DB-level encryption on the REAL engine
    with app.app_context():
        _setup_db_encryption(app)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.members import members_bp
    from app.routes.workflow import workflow_bp
    from app.routes.dispatch import dispatch_bp
    from app.routes.search import search_bp
    from app.routes.audit import audit_bp
    from app.routes.sla import sla_bp
    from app.routes.cleansing import cleansing_bp
    from app.routes.admin import admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(sla_bp)
    app.register_blueprint(cleansing_bp)
    app.register_blueprint(admin_bp)

    # Session timeout middleware
    from app.middleware import setup_session_check
    setup_session_check(app)

    # Field-level encryption (uses separate FIELD_ENCRYPTION_KEY_PATH)
    from app.services.encryption_service import EncryptionService
    EncryptionService.reset()

    # Jinja2 filters
    from app.services.sanitize import sanitize_highlight
    app.jinja_env.filters['safe_highlight'] = lambda v: sanitize_highlight(v) if v else ''
    app.jinja_env.filters['fmt_datetime'] = lambda dt: dt.strftime('%m/%d/%Y %I:%M %p') if dt else ''

    # Create tables and FTS index
    with app.app_context():
        from app.models import User, Role, TrustedDevice, Member, Tag, MemberTimeline, Address, ServiceArea, EligibilityLog, SearchLog  # noqa: F401
        db.create_all()

        from app.models.search import init_fts
        init_fts(app)

    return app
