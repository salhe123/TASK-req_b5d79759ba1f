import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import Role
from app.services.auth_service import AuthService


@pytest.fixture(scope='function')
def app():
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    return _db


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def seed_roles(app, db):
    """Seed default roles."""
    for name in ['admin', 'manager', 'operator', 'viewer']:
        db.session.add(Role(name=name, description=f'{name} role'))
    db.session.commit()


@pytest.fixture(scope='function')
def admin_user(app, db, seed_roles):
    """Create and return an admin user."""
    user = AuthService.create_user('admin', 'admin@test.com', 'admin123', 'admin')
    return user


@pytest.fixture(scope='function')
def auth_client(client, admin_user):
    """Client logged in as admin."""
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
    return client
