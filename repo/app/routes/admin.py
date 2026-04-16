from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required, sensitive_action_reauth
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@roles_required('admin')
def dashboard():
    data = AdminService.get_dashboard_data()
    return render_template('admin/dashboard.html', data=data)


@admin_bp.route('/users')
@login_required
@roles_required('admin')
def users():
    user_list = AdminService.list_users()
    return render_template('admin/users.html', users=user_list)


@admin_bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def deactivate_user(user_id):
    if user_id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))

    success, error = AdminService.deactivate_user(user_id, performed_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('User account deactivated.', 'success')

    if request.headers.get('HX-Request'):
        user_list = AdminService.list_users()
        return render_template('admin/partials/user_table.html', users=user_list)

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/activate', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def activate_user(user_id):
    success, error = AdminService.activate_user(user_id, performed_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('User account activated.', 'success')

    if request.headers.get('HX-Request'):
        user_list = AdminService.list_users()
        return render_template('admin/partials/user_table.html', users=user_list)

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/freeze', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def freeze_user(user_id):
    if user_id == current_user.id:
        flash('You cannot freeze your own account.', 'danger')
        return redirect(url_for('admin.users'))

    success, error = AdminService.freeze_user(user_id, performed_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('User account frozen (locked).', 'success')

    if request.headers.get('HX-Request'):
        user_list = AdminService.list_users()
        return render_template('admin/partials/user_table.html', users=user_list)

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/unfreeze', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def unfreeze_user(user_id):
    success, error = AdminService.unfreeze_user(user_id, performed_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('User account unfrozen (unlocked).', 'success')

    if request.headers.get('HX-Request'):
        user_list = AdminService.list_users()
        return render_template('admin/partials/user_table.html', users=user_list)

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/change-role', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def change_role(user_id):
    if user_id == current_user.id:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('admin.users'))

    new_role = request.form.get('role', '').strip()
    success, error = AdminService.change_user_role(user_id, new_role, performed_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash(f'User role changed to {new_role}.', 'success')

    if request.headers.get('HX-Request'):
        user_list = AdminService.list_users()
        return render_template('admin/partials/user_table.html', users=user_list)

    return redirect(url_for('admin.users'))


@admin_bp.route('/search-config', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def search_config():
    from app.models.config import SystemConfig
    from app.extensions import db

    SEARCH_KEYS = [
        ('search_trending_limit', 'Trending Searches Limit', '10'),
        ('search_trending_days', 'Trending Window (days)', '7'),
        ('search_recommendations_limit', 'Recommendations Limit', '5'),
        ('search_results_per_page', 'Results Per Page', '20'),
    ]

    if request.method == 'POST':
        for key, label, default in SEARCH_KEYS:
            value = request.form.get(key, default).strip()
            existing = db.session.query(SystemConfig).filter_by(key=key).first()
            if existing:
                existing.value = value
                existing.updated_by = current_user.id
            else:
                db.session.add(SystemConfig(key=key, value=value, updated_by=current_user.id))
        db.session.commit()

        AdminService._audit('update_search_config', None, current_user.id,
                            details='Updated search configuration')
        flash('Search configuration updated.', 'success')
        return redirect(url_for('admin.search_config'))

    config_values = {}
    for key, label, default in SEARCH_KEYS:
        row = db.session.query(SystemConfig).filter_by(key=key).first()
        config_values[key] = {
            'label': label,
            'value': row.value if row else default,
            'default': default,
        }

    return render_template('admin/search_config.html', config=config_values)


@admin_bp.route('/users/<int:user_id>/devices')
@login_required
@roles_required('admin')
def user_devices(user_id):
    from app.models.user import User
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))
    devices = DeviceService.admin_list_devices_for_user(user_id)
    return render_template('admin/user_devices.html', target_user=user, devices=devices)


@admin_bp.route('/devices/<int:device_id>/revoke', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def revoke_device(device_id):
    success, error = DeviceService.admin_revoke_device(device_id, revoked_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('Device revoked.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/devices/revoke-all', methods=['POST'])
@login_required
@roles_required('admin')
@sensitive_action_reauth
def revoke_all_devices(user_id):
    success, error = DeviceService.admin_revoke_all_devices(user_id, revoked_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('All devices revoked for this user.', 'success')
    return redirect(url_for('admin.user_devices', user_id=user_id))
