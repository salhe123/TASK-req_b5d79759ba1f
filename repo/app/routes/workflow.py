from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required, sensitive_action_reauth
from app.services.workflow_service import WorkflowService, InvalidTransitionError
from app.services.member_service import MemberService

workflow_bp = Blueprint('workflow', __name__, url_prefix='/members')


@workflow_bp.route('/<int:member_id>/workflow')
@login_required
@roles_required('admin', 'manager', 'operator')
def index(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    available_actions = WorkflowService.get_available_actions(member)
    timeline = WorkflowService.get_timeline(member_id)
    upgrade_options = WorkflowService.get_type_options_for_upgrade(member)
    downgrade_options = WorkflowService.get_type_options_for_downgrade(member)

    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='workflow', entity_type='member',
                         entity_id=member_id, user_id=current_user.id,
                         username=current_user.username,
                         details=f'Viewed workflow for {member.full_name}')
    except Exception:
        pass

    return render_template('members/workflow.html',
                           member=member,
                           available_actions=available_actions,
                           timeline=timeline,
                           upgrade_options=upgrade_options,
                           downgrade_options=downgrade_options)


@workflow_bp.route('/<int:member_id>/workflow/execute', methods=['POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
@sensitive_action_reauth
def execute(member_id):
    action = request.form.get('action', '').strip().upper()
    notes = request.form.get('notes', '').strip() or None
    new_type = request.form.get('new_membership_type', '').strip() or None

    try:
        member, timeline_entry = WorkflowService.execute(
            member_id, action,
            performed_by=current_user.id,
            notes=notes,
            new_membership_type=new_type,
        )
        flash(f'{action} completed successfully. Status: {member.status}.', 'success')
    except InvalidTransitionError as e:
        flash(str(e), 'danger')

    if request.headers.get('HX-Request'):
        member = MemberService.get(member_id)
        available_actions = WorkflowService.get_available_actions(member)
        timeline = WorkflowService.get_timeline(member_id)
        upgrade_options = WorkflowService.get_type_options_for_upgrade(member)
        downgrade_options = WorkflowService.get_type_options_for_downgrade(member)
        return render_template('members/partials/workflow_panel.html',
                               member=member,
                               available_actions=available_actions,
                               timeline=timeline,
                               upgrade_options=upgrade_options,
                               downgrade_options=downgrade_options)

    return redirect(url_for('workflow.index', member_id=member_id))


@workflow_bp.route('/<int:member_id>/timeline')
@login_required
@roles_required('admin', 'manager', 'operator')
def timeline(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    entries = WorkflowService.get_timeline(member_id, limit=100)

    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='workflow', entity_type='member',
                         entity_id=member_id, user_id=current_user.id,
                         username=current_user.username,
                         details=f'Viewed timeline for {member.full_name}')
    except Exception:
        pass

    if request.headers.get('HX-Request'):
        return render_template('members/partials/timeline.html',
                               member=member, timeline=entries)

    return render_template('members/timeline.html',
                           member=member, timeline=entries)
