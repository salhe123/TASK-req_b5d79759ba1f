from datetime import datetime, timedelta
from functools import wraps

from flask import redirect, url_for, flash, request, session
from flask_login import current_user, logout_user

from app.services.auth_service import AuthService


def roles_required(*roles):
    """Decorator that restricts access to users with specified roles.
    Returns 401/403 for HTMX/API requests; redirects for full-page navigation."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_htmx = request.headers.get('HX-Request')

            if not current_user.is_authenticated:
                if is_htmx:
                    from flask import make_response
                    return make_response('Authentication required', 401)
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            if current_user.role not in roles:
                if is_htmx:
                    from flask import make_response
                    return make_response('Forbidden', 403)
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('main.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def sensitive_action_reauth(f):
    """Decorator that requires re-authentication for sensitive actions.

    Uses an independent inactivity clock: `_pre_refresh_activity` is
    captured in `before_request` BEFORE `last_activity` is refreshed,
    so the decorator sees the true inactivity gap.  A successful reauth
    sets `last_reauth_at` in the session to grant a 5-minute grace window."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        from flask import current_app
        timeout = current_app.config.get('SESSION_TIMEOUT_MINUTES', 30)
        needs_reauth = False

        # Read the pre-refresh activity timestamp captured before before_request
        # refreshed last_activity — this is the TRUE inactivity gap
        pre_refresh = session.get('_pre_refresh_activity')
        if pre_refresh:
            try:
                pre_dt = datetime.fromisoformat(pre_refresh)
                inactivity = datetime.utcnow() - pre_dt
                if inactivity > timedelta(minutes=timeout):
                    needs_reauth = True
            except (ValueError, TypeError):
                needs_reauth = True
        else:
            # No prior activity recorded at all
            needs_reauth = True

        # Allow bypass if user recently re-authenticated
        last_auth = session.get('last_reauth_at')
        if needs_reauth and last_auth:
            try:
                last_auth_dt = datetime.fromisoformat(last_auth)
                since_reauth = datetime.utcnow() - last_auth_dt
                if since_reauth < timedelta(minutes=5):
                    needs_reauth = False
            except (ValueError, TypeError):
                pass

        if needs_reauth:
            flash('This action requires re-authentication due to inactivity. Please enter your credentials.', 'warning')
            return redirect(url_for('auth.reauth', next=request.url))

        return f(*args, **kwargs)
    return decorated_function


def login_required_with_timeout(f):
    """Decorator that checks login and session timeout."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        if AuthService.check_session_timeout(current_user):
            logout_user()
            flash('Session expired due to inactivity. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))

        AuthService.refresh_activity(current_user)
        return f(*args, **kwargs)
    return decorated_function


def setup_session_check(app):
    """Register a before_request handler to check session timeout globally."""
    @app.before_request
    def check_session_timeout():
        # Skip for static files and auth routes
        if request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint in ('auth.login', 'auth.logout', 'auth.reauth', 'main.health')
        ):
            return

        if current_user.is_authenticated:
            if AuthService.check_session_timeout(current_user):
                logout_user()
                flash('Session expired due to inactivity. Please log in again.', 'warning')
                return redirect(url_for('auth.login'))

            # Capture the CURRENT last_activity BEFORE refreshing it.
            # This is the true inactivity measurement for @sensitive_action_reauth.
            if current_user.last_activity:
                session['_pre_refresh_activity'] = current_user.last_activity.isoformat()

            AuthService.refresh_activity(current_user)
