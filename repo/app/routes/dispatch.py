from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.middleware import roles_required
from app.services.address_service import AddressService, SiteAddressService, ServiceAreaService, EligibilityService
from app.services.member_service import MemberService

dispatch_bp = Blueprint('dispatch', __name__, url_prefix='/dispatch')


# --- Address CRUD (nested under member) ---

@dispatch_bp.route('/members/<int:member_id>/addresses')
@login_required
@roles_required('admin', 'manager', 'operator')
def member_addresses(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    addresses = AddressService.list_by_member(member_id)

    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='member', entity_type='address',
                         entity_id=member_id, user_id=current_user.id,
                         username=current_user.username,
                         details=f'Listed addresses for member {member_id}')
    except Exception:
        pass

    if request.headers.get('HX-Request'):
        return render_template('dispatch/partials/address_list.html',
                               member=member, addresses=addresses)

    return render_template('dispatch/addresses.html',
                           member=member, addresses=addresses)


@dispatch_bp.route('/members/<int:member_id>/addresses/new', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def create_address(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    if request.method == 'POST':
        data = _extract_address_form(request.form)
        address, error = AddressService.create(
            member_id, data,
            user_id=current_user.id, username=current_user.username,
        )

        if error:
            flash(error, 'danger')
            return render_template('dispatch/address_form.html',
                                   member=member, data=data)

        flash('Address created successfully.', 'success')
        return redirect(url_for('dispatch.member_addresses', member_id=member_id))

    return render_template('dispatch/address_form.html',
                           member=member, data={})


@dispatch_bp.route('/addresses/<int:address_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def edit_address(address_id):
    address = AddressService.get(address_id)
    if not address:
        flash('Address not found.', 'danger')
        return redirect(url_for('members.index'))

    member = MemberService.get(address.member_id)

    if request.method == 'POST':
        data = _extract_address_form(request.form)
        expected_version = request.form.get('version', type=int)
        updated, error = AddressService.update(
            address_id, data, expected_version=expected_version,
            user_id=current_user.id, username=current_user.username,
        )

        if error:
            flash(error, 'danger')
            address = AddressService.get(address_id) or address
            return render_template('dispatch/address_form.html',
                                   member=member, address=address, data=data, edit=True)

        flash('Address updated successfully.', 'success')
        return redirect(url_for('dispatch.member_addresses', member_id=member.id))

    data = {
        'label': address.label,
        'street': address.street,
        'city': address.city,
        'state': address.state,
        'zip_code': address.zip_code,
        'country': address.country,
        'latitude': address.latitude if address.latitude is not None else '',
        'longitude': address.longitude if address.longitude is not None else '',
        'region': address.region or '',
        'is_primary': address.is_primary,
    }
    return render_template('dispatch/address_form.html',
                           member=member, address=address, data=data, edit=True)


@dispatch_bp.route('/addresses/<int:address_id>/delete', methods=['POST'])
@login_required
@roles_required('admin', 'manager')
def delete_address(address_id):
    address = AddressService.get(address_id)
    if not address:
        flash('Address not found.', 'danger')
        return redirect(url_for('members.index'))

    member_id = address.member_id
    success, error = AddressService.delete(
        address_id,
        user_id=current_user.id, username=current_user.username,
    )
    if error:
        flash(error, 'danger')
    else:
        flash('Address deleted.', 'success')

    if request.headers.get('HX-Request'):
        member = MemberService.get(member_id)
        addresses = AddressService.list_by_member(member_id)
        return render_template('dispatch/partials/address_list.html',
                               member=member, addresses=addresses)

    return redirect(url_for('dispatch.member_addresses', member_id=member_id))


# --- Eligibility ---

@dispatch_bp.route('/eligibility')
@login_required
@roles_required('admin', 'manager')
def eligibility():
    service_areas = ServiceAreaService.list_all()
    recent_logs = EligibilityService.get_logs(limit=20)
    return render_template('dispatch/eligibility.html',
                           service_areas=service_areas, logs=recent_logs)


@dispatch_bp.route('/members/<int:member_id>/eligibility', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager', 'operator')
def check_eligibility(member_id):
    member = MemberService.get(member_id)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.index'))

    addresses = AddressService.list_by_member(member_id)
    result = None

    if request.method == 'POST':
        address_id = request.form.get('address_id', type=int)
        is_eligible, reason, log = EligibilityService.check_eligibility(
            member_id, address_id=address_id, checked_by=current_user.id
        )
        result = {'eligible': is_eligible, 'reason': reason}

        try:
            from app.services.audit_service import AuditService
            AuditService.log(action='eligibility_check', category='eligibility',
                             entity_type='member', entity_id=member_id,
                             user_id=current_user.id, username=current_user.username,
                             details=f'Result: {"eligible" if is_eligible else "not eligible"} — {reason}')
        except Exception:
            pass

        if request.headers.get('HX-Request'):
            return render_template('dispatch/partials/eligibility_result.html',
                                   member=member, result=result)

    logs = EligibilityService.get_logs(member_id=member_id, limit=10)
    return render_template('dispatch/check_eligibility.html',
                           member=member, addresses=addresses,
                           result=result, logs=logs)


# --- Service Areas ---

@dispatch_bp.route('/service-areas')
@login_required
@roles_required('admin', 'manager')
def service_areas():
    areas = ServiceAreaService.list_all()
    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='member', entity_type='service_area',
                         user_id=current_user.id, username=current_user.username,
                         details='Listed service areas')
    except Exception:
        pass
    return render_template('dispatch/service_areas.html', areas=areas)


@dispatch_bp.route('/service-areas/new', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def create_service_area():
    if request.method == 'POST':
        data = _extract_area_form(request.form)
        area, error = ServiceAreaService.create(
            data,
            user_id=current_user.id, username=current_user.username,
        )
        if error:
            flash(error, 'danger')
            return render_template('dispatch/service_area_form.html', data=data)

        flash(f'Service area "{area.name}" created.', 'success')
        return redirect(url_for('dispatch.service_areas'))

    return render_template('dispatch/service_area_form.html', data={})


@dispatch_bp.route('/service-areas/<int:area_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def edit_service_area(area_id):
    area = ServiceAreaService.get(area_id)
    if not area:
        flash('Service area not found.', 'danger')
        return redirect(url_for('dispatch.service_areas'))

    if request.method == 'POST':
        data = _extract_area_form(request.form)
        expected_version = request.form.get('version', type=int)
        updated, error = ServiceAreaService.update(
            area_id, data, expected_version=expected_version,
            user_id=current_user.id, username=current_user.username,
        )
        if error:
            flash(error, 'danger')
            area = ServiceAreaService.get(area_id) or area
            return render_template('dispatch/service_area_form.html',
                                   area=area, data=data, edit=True)

        flash('Service area updated.', 'success')
        return redirect(url_for('dispatch.service_areas'))

    data = {
        'name': area.name,
        'area_type': area.area_type,
        'region': area.region or '',
        'center_latitude': area.center_latitude if area.center_latitude is not None else '',
        'center_longitude': area.center_longitude if area.center_longitude is not None else '',
        'radius_miles': area.radius_miles or 25.0,
        'is_active': area.is_active,
    }
    return render_template('dispatch/service_area_form.html',
                           area=area, data=data, edit=True)


@dispatch_bp.route('/service-areas/<int:area_id>/delete', methods=['POST'])
@login_required
@roles_required('admin')
def delete_service_area(area_id):
    success, error = ServiceAreaService.delete(
        area_id,
        user_id=current_user.id, username=current_user.username,
    )
    if error:
        flash(error, 'danger')
    else:
        flash('Service area deleted.', 'success')
    return redirect(url_for('dispatch.service_areas'))


# --- Site Address Book ---

@dispatch_bp.route('/site-addresses')
@login_required
@roles_required('admin', 'manager')
def site_addresses():
    sites = SiteAddressService.list_all()
    try:
        from app.services.audit_service import AuditService
        AuditService.log(action='read', category='member', entity_type='site_address',
                         user_id=current_user.id, username=current_user.username,
                         details='Listed site addresses')
    except Exception:
        pass
    return render_template('dispatch/site_addresses.html', sites=sites)


@dispatch_bp.route('/site-addresses/new', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager')
def create_site_address():
    if request.method == 'POST':
        data = _extract_address_form(request.form)
        data['name'] = request.form.get('name', '').strip()
        site, error = SiteAddressService.create(
            data, user_id=current_user.id, username=current_user.username,
        )
        if error:
            flash(error, 'danger')
            return render_template('dispatch/site_address_form.html', data=data)
        flash(f'Site address "{site.name}" created.', 'success')
        return redirect(url_for('dispatch.site_addresses'))
    return render_template('dispatch/site_address_form.html', data={})


@dispatch_bp.route('/site-addresses/<int:site_id>/edit', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager')
def edit_site_address(site_id):
    site = SiteAddressService.get(site_id)
    if not site:
        flash('Site address not found.', 'danger')
        return redirect(url_for('dispatch.site_addresses'))

    if request.method == 'POST':
        data = _extract_address_form(request.form)
        data['name'] = request.form.get('name', '').strip()
        expected_version = request.form.get('version', type=int)
        updated, error = SiteAddressService.update(
            site_id, data, expected_version=expected_version,
            user_id=current_user.id, username=current_user.username,
        )
        if error:
            flash(error, 'danger')
            site = SiteAddressService.get(site_id) or site
            return render_template('dispatch/site_address_form.html',
                                   site=site, data=data, edit=True)
        flash('Site address updated.', 'success')
        return redirect(url_for('dispatch.site_addresses'))

    data = {
        'name': site.name,
        'street': site.street,
        'city': site.city,
        'state': site.state,
        'zip_code': site.zip_code,
        'country': site.country,
        'latitude': site.latitude if site.latitude is not None else '',
        'longitude': site.longitude if site.longitude is not None else '',
        'region': site.region or '',
    }
    return render_template('dispatch/site_address_form.html',
                           site=site, data=data, edit=True)


@dispatch_bp.route('/site-addresses/<int:site_id>/delete', methods=['POST'])
@login_required
@roles_required('admin')
def delete_site_address(site_id):
    success, error = SiteAddressService.delete(
        site_id, user_id=current_user.id, username=current_user.username,
    )
    if error:
        flash(error, 'danger')
    else:
        flash('Site address deleted.', 'success')
    return redirect(url_for('dispatch.site_addresses'))


# --- Helpers ---

def _safe_float(value, default=None):
    """Safely convert a string to float, returning default on failure."""
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _extract_address_form(form):
    lat = form.get('latitude', '').strip()
    lng = form.get('longitude', '').strip()
    return {
        'label': form.get('label', 'primary'),
        'street': form.get('street', ''),
        'city': form.get('city', ''),
        'state': form.get('state', ''),
        'zip_code': form.get('zip_code', ''),
        'country': form.get('country', 'US'),
        'latitude': _safe_float(lat),
        'longitude': _safe_float(lng),
        'region': form.get('region', ''),
        'is_primary': form.get('is_primary') == '1',
    }


def _extract_area_form(form):
    lat = form.get('center_latitude', '').strip()
    lng = form.get('center_longitude', '').strip()
    radius = form.get('radius_miles', '').strip()
    return {
        'name': form.get('name', ''),
        'area_type': form.get('area_type', 'region'),
        'region': form.get('region', ''),
        'center_latitude': _safe_float(lat),
        'center_longitude': _safe_float(lng),
        'radius_miles': _safe_float(radius, 25.0),
        'is_active': form.get('is_active') == '1',
    }
