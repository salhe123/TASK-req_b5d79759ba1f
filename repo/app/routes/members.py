from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required, sensitive_action_reauth
from app.services.member_service import MemberService, OptimisticLockError

members_bp = Blueprint('members', __name__, url_prefix='/members')


@members_bp.route('/')
@login_required
@roles_required('admin', 'manager', 'operator')
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip() or None
    membership_type = request.args.get('membership_type', '').strip() or None
    tag = request.args.get('tag', '').strip() or None
    include_archived = request.args.get('archived', '0') == '1'

    result = MemberService.list_members(
        page=page, search=search or None, status=status,
        membership_type=membership_type, tag_name=tag,
        include_archived=include_archived,
    )
    tags = MemberService.get_all_tags()

    # Audit log for read/list
    try:
        from app.services.audit_service import AuditService
        AuditService.log(
            action='list',
            category='member',
            entity_type='member',
            user_id=current_user.id,
            username=current_user.username,
            details=f'page={page}, search="{search}"' if search else f'page={page}',
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Audit log failed for member list')

    if request.headers.get('HX-Request'):
        return render_template('members/partials/member_list.html',
                               members=result, tags=tags,
                               search=search, status=status,
                               membership_type=membership_type, tag=tag,
                               archived=include_archived)

    return render_template('members/index.html',
                           members=result, tags=tags,
                           search=search, status=status,
                           membership_type=membership_type, tag=tag,
                           archived=include_archived)


@members_bp.route('/new', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def create():
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name', ''),
            'last_name': request.form.get('last_name', ''),
            'email': request.form.get('email', ''),
            'phone': request.form.get('phone', ''),
            'membership_type': request.form.get('membership_type', 'basic'),
            'organization': request.form.get('organization', ''),
            'notes': request.form.get('notes', ''),
        }

        # Parse tags for atomic creation
        tag_str = request.form.get('tags', '').strip()
        tag_names = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else None

        member, error = MemberService.create(
            data, created_by=current_user.id, tag_names=tag_names,
        )

        if error:
            flash(error, 'danger')
            if request.headers.get('HX-Request'):
                return render_template('members/partials/member_form.html',
                                       data=data, error=error)
            return render_template('members/create.html', data=data)

        flash(f'Member {member.full_name} created successfully.', 'success')
        return redirect(url_for('members.detail', member_id=member.id))

    return render_template('members/create.html', data={})


@members_bp.route('/<int:member_id>')
@login_required
@roles_required('admin', 'manager', 'operator')
def detail(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    # Audit log for read/view
    try:
        from app.services.audit_service import AuditService
        AuditService.log(
            action='view',
            category='member',
            entity_type='member',
            entity_id=member_id,
            user_id=current_user.id,
            username=current_user.username,
            details=f'Viewed {member.full_name}',
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Audit log failed for member view %s', member_id)

    return render_template('members/detail.html', member=member)


@members_bp.route('/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def edit(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name', ''),
            'last_name': request.form.get('last_name', ''),
            'email': request.form.get('email', ''),
            'phone': request.form.get('phone', ''),
            'membership_type': request.form.get('membership_type', member.membership_type),
            'organization': request.form.get('organization', ''),
            'notes': request.form.get('notes', ''),
        }
        expected_version = request.form.get('version', type=int)

        # Parse tags for atomic update
        tag_str = request.form.get('tags', '').strip()
        tag_names = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else []

        try:
            updated, error = MemberService.update(
                member_id, data,
                updated_by=current_user.id,
                expected_version=expected_version,
                tag_names=tag_names,
            )
        except OptimisticLockError as e:
            flash(str(e), 'danger')
            member = MemberService.get(member_id)
            return render_template('members/edit.html', member=member, data=data)

        if error:
            flash(error, 'danger')
            if request.headers.get('HX-Request'):
                return render_template('members/partials/member_form.html',
                                       member=member, data=data, error=error, edit=True)
            return render_template('members/edit.html', member=member, data=data)

        flash(f'Member {updated.full_name} updated successfully.', 'success')
        return redirect(url_for('members.detail', member_id=member_id))

    data = {
        'first_name': member.first_name,
        'last_name': member.last_name,
        'email': member.email,
        'phone': member.phone or '',
        'membership_type': member.membership_type,
        'organization': member.organization or '',
        'notes': member.notes or '',
        'tags': ', '.join(t.name for t in member.tags),
    }
    return render_template('members/edit.html', member=member, data=data)


@members_bp.route('/<int:member_id>/delete', methods=['POST'])
@login_required
@roles_required('admin', 'manager')
@sensitive_action_reauth
def delete(member_id):
    success, error = MemberService.delete(member_id, deleted_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('Member archived successfully.', 'success')

    if request.headers.get('HX-Request'):
        return redirect(url_for('members.index'))

    return redirect(url_for('members.index'))


@members_bp.route('/<int:member_id>/restore', methods=['POST'])
@login_required
@roles_required('admin', 'manager')
@sensitive_action_reauth
def restore(member_id):
    success, error = MemberService.restore(member_id, restored_by=current_user.id)
    if error:
        flash(error, 'danger')
    else:
        flash('Member restored successfully.', 'success')

    return redirect(url_for('members.detail', member_id=member_id))


@members_bp.route('/validate-field', methods=['POST'])
@login_required
def validate_field():
    """HTMX inline field validation — returns error fragment or empty 200."""
    field = request.form.get('field', '')
    value = request.form.get('value', '').strip()
    error = None

    if field == 'email':
        if not value:
            error = 'Email is required.'
        elif '@' not in value:
            error = 'Invalid email address.'
        else:
            from sqlalchemy import select
            from app.extensions import db
            from app.models.member import Member
            member_id = request.form.get('member_id', type=int)
            q = select(Member).where(Member.email == value.lower())
            if member_id:
                q = q.where(Member.id != member_id)
            existing = db.session.execute(q).scalar_one_or_none()
            if existing:
                error = 'A member with this email already exists.'
    elif field == 'first_name':
        if not value:
            error = 'First name is required.'
    elif field == 'last_name':
        if not value:
            error = 'Last name is required.'

    if error:
        return f'<span class="field-error" style="color: #dc3545; font-size: 0.85rem;">{error}</span>'
    return '<span class="field-ok" style="color: #28a745; font-size: 0.85rem;"></span>'


@members_bp.route('/<int:member_id>/tags', methods=['POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def add_tag(member_id):
    tag_name = request.form.get('tag_name', '').strip()
    if not tag_name:
        flash('Tag name is required.', 'danger')
    else:
        success, error = MemberService.add_tag(member_id, tag_name)
        if error:
            flash(error, 'danger')

    if request.headers.get('HX-Request'):
        member = MemberService.get(member_id)
        return render_template('members/partials/tag_list.html', member=member)

    return redirect(url_for('members.detail', member_id=member_id))


@members_bp.route('/<int:member_id>/tags/<tag_name>/remove', methods=['POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def remove_tag(member_id, tag_name):
    MemberService.remove_tag(member_id, tag_name)

    if request.headers.get('HX-Request'):
        member = MemberService.get(member_id)
        return render_template('members/partials/tag_list.html', member=member)

    return redirect(url_for('members.detail', member_id=member_id))
