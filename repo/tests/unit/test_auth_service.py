import pytest
from datetime import datetime, timedelta
from app.services.auth_service import AuthService
from app.models.user import User
from app.extensions import db


class TestAuthService:

    def test_hash_and_verify_password(self, app):
        hashed = AuthService.hash_password('secret123')
        assert hashed != 'secret123'
        assert AuthService.verify_password('secret123', hashed)
        assert not AuthService.verify_password('wrong', hashed)

    def test_authenticate_success(self, app, admin_user):
        user, err = AuthService.authenticate('admin', 'admin123')
        assert user is not None
        assert err is None
        assert user.username == 'admin'
        assert user.last_login is not None

    def test_authenticate_wrong_password(self, app, admin_user):
        user, err = AuthService.authenticate('admin', 'wrongpass')
        assert user is None
        assert 'Invalid' in err
        assert '4 attempt(s)' in err

    def test_authenticate_unknown_user(self, app, admin_user):
        user, err = AuthService.authenticate('nobody', 'pass')
        assert user is None
        assert 'Invalid' in err

    def test_account_lockout_after_5_failures(self, app, admin_user):
        for _ in range(5):
            AuthService.authenticate('admin', 'wrong')

        user, err = AuthService.authenticate('admin', 'admin123')
        assert user is None
        assert 'locked' in err.lower()

    def test_locked_account_rejects_correct_password(self, app, admin_user):
        for _ in range(5):
            AuthService.authenticate('admin', 'wrong')
        user, err = AuthService.authenticate('admin', 'admin123')
        assert user is None
        assert 'locked' in err.lower()

    def test_lock_expires(self, app, admin_user):
        for _ in range(5):
            AuthService.authenticate('admin', 'wrong')
        # Manually expire the lock
        u = User.query.filter_by(username='admin').first()
        u.locked_until = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

        user, err = AuthService.authenticate('admin', 'admin123')
        assert user is not None
        assert err is None

    def test_deactivated_account(self, app, admin_user):
        u = User.query.filter_by(username='admin').first()
        u.is_active = False
        db.session.commit()

        user, err = AuthService.authenticate('admin', 'admin123')
        assert user is None
        assert 'deactivated' in err.lower()

    def test_session_timeout_check(self, app, admin_user):
        u = User.query.filter_by(username='admin').first()
        u.last_activity = datetime.utcnow() - timedelta(minutes=31)
        db.session.commit()
        assert AuthService.check_session_timeout(u)

    def test_session_not_timed_out(self, app, admin_user):
        u = User.query.filter_by(username='admin').first()
        u.last_activity = datetime.utcnow()
        db.session.commit()
        assert not AuthService.check_session_timeout(u)

    def test_create_user(self, app, seed_roles):
        user = AuthService.create_user('newuser', 'new@test.com', 'pass123', 'operator')
        assert user.id is not None
        assert user.username == 'newuser'
        assert user.role == 'operator'
        assert AuthService.verify_password('pass123', user.password_hash)
