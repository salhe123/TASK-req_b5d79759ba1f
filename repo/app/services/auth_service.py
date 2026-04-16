from datetime import datetime, timedelta

import bcrypt
from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.user import User


class AuthService:

    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password, password_hash):
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def is_account_locked(user):
        if user.locked_until and user.locked_until > datetime.utcnow():
            return True
        if user.locked_until and user.locked_until <= datetime.utcnow():
            # Lock expired — reset
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()
        return False

    @staticmethod
    def authenticate(username, password):
        """Authenticate user. Returns (user, error_message) tuple."""
        user = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            AuthService._audit('login_failed', username=username, details='Unknown username')
            return None, 'Invalid username or password.'

        if not user.is_active:
            AuthService._audit('login_failed', user=user, details='Account deactivated')
            return None, 'Account is deactivated. Contact an administrator.'

        if AuthService.is_account_locked(user):
            remaining = (user.locked_until - datetime.utcnow()).seconds // 60 + 1
            AuthService._audit('login_blocked', user=user, details='Account locked')
            return None, f'Account is locked. Try again in {remaining} minute(s).'

        if not AuthService.verify_password(password, user.password_hash):
            return AuthService._handle_failed_login(user)

        # Successful login — reset counters
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        user.last_activity = datetime.utcnow()
        db.session.commit()

        AuthService._audit('login_success', user=user)
        return user, None

    @staticmethod
    def _handle_failed_login(user):
        max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
        lock_duration = current_app.config.get('ACCOUNT_LOCK_DURATION_MINUTES', 15)

        user.failed_login_attempts += 1

        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.utcnow() + timedelta(minutes=lock_duration)
            db.session.commit()
            AuthService._audit('account_locked', user=user,
                               details=f'Locked after {max_attempts} failed attempts')
            return None, f'Account locked due to {max_attempts} failed attempts. Try again in {lock_duration} minutes.'

        remaining = max_attempts - user.failed_login_attempts
        db.session.commit()
        AuthService._audit('login_failed', user=user,
                           details=f'Wrong password, {remaining} attempts remaining')
        return None, f'Invalid username or password. {remaining} attempt(s) remaining.'

    @staticmethod
    def check_session_timeout(user):
        """Returns True if session has timed out."""
        timeout_minutes = current_app.config.get('SESSION_TIMEOUT_MINUTES', 30)
        if user.last_activity:
            elapsed = datetime.utcnow() - user.last_activity
            if elapsed > timedelta(minutes=timeout_minutes):
                return True
        return False

    @staticmethod
    def refresh_activity(user):
        user.last_activity = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def create_user(username, email, password, role='operator'):
        password_hash = AuthService.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def _audit(action, user=None, username=None, details=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action,
                category='auth',
                entity_type='user',
                entity_id=user.id if user else None,
                user_id=user.id if user else None,
                username=user.username if user else username,
                details=details,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'Audit log failed for auth action=%s user=%s',
                action, username or (user.username if user else 'unknown'),
            )
