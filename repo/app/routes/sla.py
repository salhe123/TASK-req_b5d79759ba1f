from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required
from app.services.sla_service import SLAService

sla_bp = Blueprint('sla', __name__, url_prefix='/sla')


@sla_bp.route('/')
@login_required
@roles_required('admin')
def dashboard():
    stats = SLAService.get_dashboard_stats()
    violations = SLAService.get_violations(acknowledged=False, limit=20)
    return render_template('sla/dashboard.html', stats=stats, violations=violations)


@sla_bp.route('/violations')
@login_required
@roles_required('admin')
def violations():
    metric_type = request.args.get('metric_type', '').strip() or None
    severity = request.args.get('severity', '').strip() or None
    show_acked = request.args.get('acknowledged', '0') == '1'

    items = SLAService.get_violations(
        metric_type=metric_type,
        severity=severity,
        acknowledged=None if show_acked else False,
        limit=100,
    )
    return render_template('sla/violations.html', violations=items,
                           metric_type=metric_type, severity=severity,
                           show_acked=show_acked)


@sla_bp.route('/violations/<int:violation_id>/acknowledge', methods=['POST'])
@login_required
@roles_required('admin')
def acknowledge(violation_id):
    ok, error = SLAService.acknowledge_violation(violation_id, user_id=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('Violation acknowledged.', 'success')

    if request.headers.get('HX-Request'):
        violations = SLAService.get_violations(acknowledged=False, limit=20)
        return render_template('sla/partials/violation_list.html', violations=violations)

    return redirect(url_for('sla.violations'))
