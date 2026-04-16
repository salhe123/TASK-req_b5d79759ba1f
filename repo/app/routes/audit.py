import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from app.middleware import roles_required, sensitive_action_reauth
from app.services.audit_service import AuditService

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')


@audit_bp.route('/')
@login_required
@roles_required('admin')
def index():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip() or None
    action = request.args.get('action', '').strip() or None
    entity_type = request.args.get('entity_type', '').strip() or None
    anomalies_only = request.args.get('anomalies', '0') == '1'
    page = request.args.get('page', 1, type=int)

    date_from = None
    date_to = None
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    logs = AuditService.search_logs(
        query=query or None, category=category, action=action,
        entity_type=entity_type, anomalies_only=anomalies_only,
        date_from=date_from, date_to=date_to,
        page=page,
    )

    stats = AuditService.get_stats()

    if request.headers.get('HX-Request'):
        return render_template('audit/partials/log_table.html', logs=logs,
                               query=query, category=category, action=action,
                               entity_type=entity_type, anomalies=anomalies_only)

    return render_template('audit/index.html', logs=logs, stats=stats,
                           query=query, category=category, action=action,
                           entity_type=entity_type, anomalies=anomalies_only,
                           date_from=date_from_str, date_to=date_to_str)


@audit_bp.route('/alerts')
@login_required
@roles_required('admin')
def alerts():
    show_resolved = request.args.get('resolved', '0') == '1'
    alert_list = AuditService.get_alerts(
        resolved=None if show_resolved else False
    )
    return render_template('audit/alerts.html', alerts=alert_list,
                           show_resolved=show_resolved)


@audit_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
@roles_required('admin')
def resolve_alert(alert_id):
    success, error = AuditService.resolve_alert(alert_id, resolved_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('Alert resolved.', 'success')

    if request.headers.get('HX-Request'):
        alert_list = AuditService.get_alerts(resolved=False)
        return render_template('audit/partials/alert_list.html', alerts=alert_list)

    return redirect(url_for('audit.alerts'))


@audit_bp.route('/export')
@login_required
@roles_required('admin')
@sensitive_action_reauth
def export():
    """Export audit logs as CSV."""
    category = request.args.get('category', '').strip() or None
    date_from = None
    date_to = None
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    logs = AuditService.search_logs(
        category=category, date_from=date_from, date_to=date_to,
        page=1, per_page=10000,
    )

    # Log the export action itself
    AuditService.log(
        action='export',
        category='system',
        entity_type='audit_log',
        user_id=current_user.id,
        username=current_user.username,
        details=f'Exported {logs.total} audit log entries',
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'Category', 'Action', 'Entity Type', 'Entity ID',
                     'User ID', 'Username', 'Details', 'IP Address', 'Is Anomaly'])
    for log in logs.items:
        writer.writerow([
            log.created_at.strftime('%m/%d/%Y %I:%M %p'),
            log.category,
            log.action,
            log.entity_type or '',
            log.entity_id or '',
            log.user_id or '',
            log.username or '',
            log.details or '',
            log.ip_address or '',
            'Yes' if log.is_anomaly else 'No',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=audit_export.csv'},
    )
