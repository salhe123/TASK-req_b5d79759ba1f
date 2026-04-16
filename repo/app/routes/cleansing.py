import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required
from app.services.cleansing_service import CleansingService

cleansing_bp = Blueprint('cleansing', __name__, url_prefix='/cleansing')


@cleansing_bp.route('/')
@login_required
@roles_required('admin')
def index():
    templates = CleansingService.list_templates()
    jobs = CleansingService.list_jobs(limit=20)
    try:
        from app.services.audit_service import AuditService
        from flask_login import current_user
        AuditService.log(action='read', category='system', entity_type='cleansing',
                         user_id=current_user.id, username=current_user.username,
                         details='Viewed cleansing dashboard')
    except Exception:
        pass
    return render_template('cleansing/index.html',
                           templates=templates, jobs=jobs)


# --- Templates ---

@cleansing_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def create_template():
    if request.method == 'POST':
        data = _extract_template_form(request.form)
        template, error = CleansingService.create_template(data, created_by=current_user.id)
        if error:
            flash(error, 'danger')
            return render_template('cleansing/template_form.html', data=request.form)

        flash(f'Template "{template.name}" v{template.version} created.', 'success')
        return redirect(url_for('cleansing.view_template', template_id=template.id))

    return render_template('cleansing/template_form.html', data={})


@cleansing_bp.route('/templates/<int:template_id>')
@login_required
@roles_required('admin')
def view_template(template_id):
    template = CleansingService.get_template(template_id)
    if not template:
        flash('Template not found.', 'danger')
        return redirect(url_for('cleansing.index'))

    versions = CleansingService.get_template_versions(template.name)
    jobs = template.jobs.limit(10).all()
    return render_template('cleansing/template_detail.html',
                           template=template, versions=versions, jobs=jobs)


@cleansing_bp.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def edit_template(template_id):
    template = CleansingService.get_template(template_id)
    if not template:
        flash('Template not found.', 'danger')
        return redirect(url_for('cleansing.index'))

    if request.method == 'POST':
        data = _extract_template_form(request.form)
        new_template, error = CleansingService.update_template(template_id, data)
        if error:
            flash(error, 'danger')
            return render_template('cleansing/template_form.html',
                                   template=template, data=request.form, edit=True)

        flash(f'Template updated to v{new_template.version}.', 'success')
        return redirect(url_for('cleansing.view_template', template_id=new_template.id))

    data = {
        'name': template.name,
        'description': template.description or '',
        'field_mapping': template.field_mapping or '{}',
        'missing_value_rules': template.missing_value_rules or '{}',
        'dedup_fields': template.dedup_fields or '[]',
        'dedup_threshold': template.dedup_threshold,
        'format_rules': template.format_rules or '{}',
    }
    return render_template('cleansing/template_form.html',
                           template=template, data=data, edit=True)


@cleansing_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
@roles_required('admin')
def delete_template(template_id):
    ok, error = CleansingService.delete_template(template_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Template deactivated.', 'success')
    return redirect(url_for('cleansing.index'))


# --- Jobs ---

@cleansing_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def upload():
    templates = CleansingService.list_templates()

    if request.method == 'POST':
        template_id = request.form.get('template_id', type=int)
        file = request.files.get('csv_file')

        if not template_id:
            flash('Please select a template.', 'danger')
            return render_template('cleansing/upload.html', templates=templates)

        if not file or not file.filename:
            flash('Please select a CSV file.', 'danger')
            return render_template('cleansing/upload.html', templates=templates)

        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV files are supported.', 'danger')
            return render_template('cleansing/upload.html', templates=templates)

        csv_content = file.read().decode('utf-8', errors='replace')
        job, error = CleansingService.create_job(
            template_id, csv_content, file.filename,
            created_by=current_user.id,
        )
        if error:
            flash(error, 'danger')
            return render_template('cleansing/upload.html', templates=templates)

        # Execute immediately
        job, error = CleansingService.execute_job(job.id)
        if error:
            flash(error, 'danger')
        elif job.status == 'failed':
            flash(f'Job failed: {job.error_message}', 'danger')
        else:
            flash(f'Cleansing complete: {job.clean_rows} clean, '
                  f'{job.flagged_rows} flagged, {job.duplicate_rows} duplicates.', 'success')

        return redirect(url_for('cleansing.view_job', job_id=job.id))

    return render_template('cleansing/upload.html', templates=templates)


@cleansing_bp.route('/jobs/<int:job_id>')
@login_required
@roles_required('admin')
def view_job(job_id):
    job = CleansingService.get_job(job_id)
    if not job:
        flash('Job not found.', 'danger')
        return redirect(url_for('cleansing.index'))

    clean_data, flagged_data = CleansingService.get_job_results(job)

    # Build sensitive fields list from template config + system defaults
    default_sensitive = {'ssn', 'social_security', 'tax_id', 'credit_card',
                         'card_number', 'account_number', 'bank_account',
                         'password', 'secret'}
    template_sensitive = set()
    if job.template and job.template.sensitive_fields:
        try:
            template_sensitive = set(json.loads(job.template.sensitive_fields))
        except (json.JSONDecodeError, TypeError):
            pass
    sensitive_keys = default_sensitive | template_sensitive

    return render_template('cleansing/job_detail.html',
                           job=job, clean_data=clean_data,
                           flagged_data=flagged_data,
                           sensitive_keys=sensitive_keys)


def _safe_float(value, default=1.0):
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _extract_template_form(form):
    """Extract template config from form data."""
    field_mapping = form.get('field_mapping', '{}').strip()
    missing_value_rules = form.get('missing_value_rules', '{}').strip()
    dedup_fields = form.get('dedup_fields', '[]').strip()
    format_rules = form.get('format_rules', '{}').strip()

    # Parse and re-serialize to validate JSON
    try:
        field_mapping = json.loads(field_mapping)
    except json.JSONDecodeError:
        field_mapping = {}
    try:
        missing_value_rules = json.loads(missing_value_rules)
    except json.JSONDecodeError:
        missing_value_rules = {}
    try:
        dedup_fields = json.loads(dedup_fields)
    except json.JSONDecodeError:
        dedup_fields = []
    try:
        format_rules = json.loads(format_rules)
    except json.JSONDecodeError:
        format_rules = {}

    return {
        'name': form.get('name', '').strip(),
        'description': form.get('description', '').strip(),
        'field_mapping': field_mapping,
        'missing_value_rules': missing_value_rules,
        'dedup_fields': dedup_fields,
        'dedup_threshold': _safe_float(form.get('dedup_threshold', '1.0'), 1.0),
        'format_rules': format_rules,
    }
