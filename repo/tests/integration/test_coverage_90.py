"""Final push to 90%+ coverage — targets middleware, cleansing, dispatch, admin gaps."""
import io
import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.address_service import AddressService, ServiceAreaService, SiteAddressService
from app.services.cleansing_service import CleansingService


class TestCleansingRouteCoverage:
    """Cover cleansing route lines 24-25, 40-41, 70-78, 103, 139-147, 174-218."""

    def test_template_form_get_edit(self, auth_client, app, db):
        t, _ = CleansingService.create_template({'name': 'FormEdit'}, created_by=1)
        r = auth_client.get(f'/cleansing/templates/{t.id}/edit')
        assert r.status_code == 200
        assert b'FormEdit' in r.data

    def test_template_create_invalid_json(self, auth_client, app):
        r = auth_client.post('/cleansing/templates/new', data={
            'name': 'BadJSON',
            'field_mapping': '{bad',
            'missing_value_rules': '{bad',
            'dedup_fields': '[bad',
            'dedup_threshold': '1.0',
            'format_rules': '{bad',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_upload_non_csv_file(self, auth_client, app, db):
        CleansingService.create_template({'name': 'NonCSV'}, created_by=1)
        r = auth_client.post('/cleansing/upload', data={
            'template_id': '1',
            'csv_file': (io.BytesIO(b'data'), 'test.txt'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        assert b'CSV' in r.data

    def test_upload_failed_job(self, auth_client, app, db):
        """Template with broken rules to trigger job failure."""
        t, _ = CleansingService.create_template({
            'name': 'FailJob',
            'field_mapping': {'nonexist': 'x'},
        }, created_by=1)
        csv = b'col1\nval1\n'
        r = auth_client.post('/cleansing/upload', data={
            'template_id': str(t.id),
            'csv_file': (io.BytesIO(csv), 'fail.csv'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200

    def test_edit_nonexistent_template(self, auth_client):
        r = auth_client.get('/cleansing/templates/999/edit', follow_redirects=True)
        assert r.status_code == 200

    def test_delete_nonexistent_template_route(self, auth_client):
        r = auth_client.post('/cleansing/templates/999/delete', follow_redirects=True)
        assert r.status_code == 200


class TestDispatchRouteCoverage:
    """Cover dispatch lines 47-48, 75-76, 89-91, 119-120, 128, 159-160, etc."""

    def test_create_address_member_not_found(self, auth_client):
        r = auth_client.get('/dispatch/members/999/addresses/new', follow_redirects=True)
        assert r.status_code == 200

    def test_create_address_post_error(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'CE', 'last_name': 'T', 'email': 'ce@t.com'}, created_by=1)
        r = auth_client.post(f'/dispatch/members/{m.id}/addresses/new', data={
            'street': '', 'city': '', 'state': '', 'zip_code': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'required' in r.data.lower()

    def test_edit_address_not_found(self, auth_client):
        r = auth_client.get('/dispatch/addresses/999/edit', follow_redirects=True)
        assert r.status_code == 200

    def test_edit_address_post_error(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'EE', 'last_name': 'T', 'email': 'ee@t.com'}, created_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': '1 A', 'city': 'B', 'state': 'C', 'zip_code': '00000'})
        r = auth_client.post(f'/dispatch/addresses/{addr.id}/edit', data={
            'street': '', 'city': '', 'state': '', 'zip_code': '',
            'label': 'primary', 'version': str(addr.version),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_delete_address_not_found(self, auth_client):
        r = auth_client.post('/dispatch/addresses/999/delete', follow_redirects=True)
        assert r.status_code == 200

    def test_member_addresses_not_found(self, auth_client):
        r = auth_client.get('/dispatch/members/999/addresses', follow_redirects=True)
        assert r.status_code == 200

    def test_eligibility_check_member_not_found(self, auth_client):
        r = auth_client.get('/dispatch/members/999/eligibility', follow_redirects=True)
        assert r.status_code == 200

    def test_service_area_create_error(self, auth_client, app, db):
        r = auth_client.post('/dispatch/service-areas/new', data={
            'name': '', 'area_type': 'region', 'region': '',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_service_area_edit_not_found(self, auth_client):
        r = auth_client.get('/dispatch/service-areas/999/edit', follow_redirects=True)
        assert r.status_code == 200

    def test_service_area_edit_post_error(self, auth_client, app, db):
        area, _ = ServiceAreaService.create({
            'name': 'ErrEdit', 'area_type': 'region', 'region': 'x'})
        r = auth_client.post(f'/dispatch/service-areas/{area.id}/edit', data={
            'name': '', 'area_type': 'badtype', 'region': '',
            'version': str(area.version),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_service_area_delete_not_found(self, auth_client):
        r = auth_client.post('/dispatch/service-areas/999/delete', follow_redirects=True)
        assert r.status_code == 200

    def test_site_address_edit_not_found(self, auth_client):
        r = auth_client.get('/dispatch/site-addresses/999/edit', follow_redirects=True)
        assert r.status_code == 200

    def test_site_address_delete_not_found(self, auth_client):
        r = auth_client.post('/dispatch/site-addresses/999/delete', follow_redirects=True)
        assert r.status_code == 200

    def test_site_address_edit_post_error(self, auth_client, app, db):
        site, _ = SiteAddressService.create({
            'name': 'SEE', 'street': '1 A', 'city': 'B',
            'state': 'C', 'zip_code': '00000'})
        r = auth_client.post(f'/dispatch/site-addresses/{site.id}/edit', data={
            'name': 'SEE', 'street': '', 'city': '', 'state': '', 'zip_code': '',
            'version': str(site.version),
        }, follow_redirects=True)
        assert r.status_code == 200


class TestAdminRouteCoverage:
    """Cover admin lines 39, 44-45, 74-75, 79, 84-85, etc."""

    def test_deactivate_nonexistent_user(self, auth_client):
        r = auth_client.post('/admin/users/999/deactivate', follow_redirects=True)
        assert r.status_code == 200

    def test_activate_nonexistent_user(self, auth_client):
        r = auth_client.post('/admin/users/999/activate', follow_redirects=True)
        assert r.status_code == 200

    def test_freeze_self(self, auth_client):
        r = auth_client.post('/admin/users/1/freeze', follow_redirects=True)
        assert b'cannot freeze your own' in r.data.lower()

    def test_freeze_nonexistent(self, auth_client):
        r = auth_client.post('/admin/users/999/freeze', follow_redirects=True)
        assert r.status_code == 200

    def test_unfreeze_nonexistent(self, auth_client):
        r = auth_client.post('/admin/users/999/unfreeze', follow_redirects=True)
        assert r.status_code == 200

    def test_change_role_nonexistent(self, auth_client):
        r = auth_client.post('/admin/users/999/change-role',
                             data={'role': 'admin'}, follow_redirects=True)
        assert r.status_code == 200

    def test_change_role_invalid(self, auth_client, app, db, seed_roles):
        u = AuthService.create_user('badrl', 'badrl@t.com', 'pass', 'operator')
        r = auth_client.post(f'/admin/users/{u.id}/change-role',
                             data={'role': 'superadmin'}, follow_redirects=True)
        assert r.status_code == 200

    def test_user_devices_not_found(self, auth_client):
        r = auth_client.get('/admin/users/999/devices', follow_redirects=True)
        assert r.status_code == 200

    def test_revoke_device_not_found(self, auth_client):
        r = auth_client.post('/admin/devices/999/revoke', follow_redirects=True)
        assert r.status_code == 200


class TestWorkflowRouteCoverage:
    """Cover workflow lines 17-18, 31-32, 84-85, 95-99."""

    def test_workflow_member_not_found(self, auth_client):
        r = auth_client.get('/members/999/workflow', follow_redirects=True)
        assert r.status_code == 200

    def test_timeline_member_not_found(self, auth_client):
        r = auth_client.get('/members/999/timeline', follow_redirects=True)
        assert r.status_code == 200

    def test_workflow_execute_htmx(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'WH', 'last_name': 'T', 'email': 'wh@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/workflow/execute',
                             data={'action': 'JOIN'},
                             headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_timeline_htmx(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'TH', 'last_name': 'T', 'email': 'tlh@t.com'}, created_by=1)
        r = auth_client.get(f'/members/{m.id}/timeline',
                            headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_workflow_execute_redirect(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'WR', 'last_name': 'T', 'email': 'wr@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/workflow/execute',
                             data={'action': 'JOIN'})
        assert r.status_code == 302
