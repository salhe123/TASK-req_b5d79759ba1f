from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required

from app.services.auth_service import AuthService
from app.services.device_service import DeviceService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        trust_device = request.form.get('trust_device', False)

        if not username or not password:
            flash('Username and password are required.', 'danger')
            if request.headers.get('HX-Request'):
                return render_template('auth/partials/login_form.html',
                                       username=username, error='Username and password are required.')
            return render_template('auth/login.html', username=username)

        user, error = AuthService.authenticate(username, password)

        if error:
            flash(error, 'danger')
            if request.headers.get('HX-Request'):
                return render_template('auth/partials/login_form.html',
                                       username=username, error=error)
            return render_template('auth/login.html', username=username)

        login_user(user, remember=bool(remember))
        session['last_reauth_at'] = datetime.utcnow().isoformat()

        # Check trusted device
        device_id = DeviceService.generate_device_identifier(request)
        is_trusted = DeviceService.is_trusted(user.id, device_id)

        if trust_device and not is_trusted:
            device_name = request.headers.get('User-Agent', 'Unknown')[:100]
            device, dev_error = DeviceService.register_device(user.id, device_id, device_name)
            if dev_error:
                flash(dev_error, 'warning')
            is_trusted = device is not None

        if not is_trusted:
            flash(f'Welcome, {user.username}. You are logging in from an unrecognized device.', 'warning')
        else:
            flash(f'Welcome back, {user.username}!', 'success')

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/login.html')


@auth_bp.route('/reauth', methods=['GET', 'POST'])
@login_required
def reauth():
    """Re-authentication for sensitive actions."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not password:
            flash('Password is required.', 'danger')
            return render_template('auth/reauth.html')

        user, error = AuthService.authenticate(current_user.username, password)
        if error:
            flash('Incorrect password. Please try again.', 'danger')
            return render_template('auth/reauth.html')

        session['last_reauth_at'] = datetime.utcnow().isoformat()

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/reauth.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    session.pop('last_reauth_at', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/devices', methods=['GET'])
@login_required
def devices():
    user_devices = DeviceService.list_devices(current_user.id)
    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='auth', entity_type='device',
                         user_id=current_user.id, username=current_user.username,
                         details='Viewed own trusted devices')
    except Exception:
        pass
    return render_template('auth/devices.html', devices=user_devices)


@auth_bp.route('/devices/<int:device_id>/remove', methods=['POST'])
@login_required
def remove_device(device_id):
    success, error = DeviceService.remove_device(current_user.id, device_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Device removed successfully.', 'success')

    if request.headers.get('HX-Request'):
        user_devices = DeviceService.list_devices(current_user.id)
        return render_template('auth/partials/device_list.html', devices=user_devices)

    return redirect(url_for('auth.devices'))
