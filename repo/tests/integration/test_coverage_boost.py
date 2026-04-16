"""Tests to boost coverage for audit export, dispatch eligibility views,
cleansing edge cases, middleware HTMX 401/403, and search date filters."""
import io
import json
import pytest
from datetime import datetime, timedelta

from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.address_service import AddressService, ServiceAreaService, SiteAddressService
from app.services.cleansing_service import CleansingService
from app.services.audit_service import AuditService
from app.models.audit import AuditLog


class TestAuditExport:
    def test_export_csv(self, auth_client, app, db):
        AuditService.log(action='test', category='system', details='export test')
        r = auth_client.get('/audit/export')
        assert r.status_code == 200
        assert r.content_type.startswith('text/csv')
        assert b'Category' in r.data
        assert b'test' in r.data

    def test_export_with_date_filter(self, auth_client, app, db):
        AuditService.log(action='dated', category='system', details='date test')
        today = datetime.utcnow().strftime('%Y-%m-%d')
        r = auth_client.get(f'/audit/export?date_from={today}&date_to={today}')
        assert r.status_code == 200

    def test_audit_alerts_page(self, auth_client, app, db):
        r = auth_client.get('/audit/alerts')
        assert r.status_code == 200

    def test_audit_alerts_resolved(self, auth_client, app, db):
        r = auth_client.get('/audit/alerts?resolved=1')
        assert r.status_code == 200

    def test_audit_index_with_filters(self, auth_client, app, db):
        AuditService.log(action='filtered', category='auth', details='filter test')
        r = auth_client.get('/audit/?category=auth&action=filtered')
        assert r.status_code == 200

    def test_audit_htmx_returns_partial(self, auth_client, app, db):
        r = auth_client.get('/audit/', headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data


class TestDispatchEligibilityViews:
    def test_eligibility_overview(self, auth_client, app, db):
        r = auth_client.get('/dispatch/eligibility')
        assert r.status_code == 200

    def test_eligibility_check_page(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'Elig', 'last_name': 'Test', 'email': 'elig@t.com'},
            created_by=1,
        )
        r = auth_client.get(f'/dispatch/members/{m.id}/eligibility')
        assert r.status_code == 200

    def test_eligibility_check_post(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'EP', 'last_name': 'Test', 'email': 'ep@t.com'},
            created_by=1,
        )
        AddressService.create(m.id, {
            'street': '1 Main', 'city': 'Boston', 'state': 'MA',
            'zip_code': '02101', 'region': 'northeast',
        })
        ServiceAreaService.create({
            'name': 'NE', 'area_type': 'region', 'region': 'northeast',
        })
        r = auth_client.post(f'/dispatch/members/{m.id}/eligibility',
                             data={}, follow_redirects=True)
        assert r.status_code == 200

    def test_eligibility_htmx_post(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'HX', 'last_name': 'Elig', 'email': 'hxe@t.com'},
            created_by=1,
        )
        r = auth_client.post(f'/dispatch/members/{m.id}/eligibility',
                             data={}, headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_service_area_list(self, auth_client, app, db):
        r = auth_client.get('/dispatch/service-areas')
        assert r.status_code == 200

    def test_service_area_create_page(self, auth_client):
        r = auth_client.get('/dispatch/service-areas/new')
        assert r.status_code == 200

    def test_service_area_create_post(self, auth_client, app, db):
        r = auth_client.post('/dispatch/service-areas/new', data={
            'name': 'TestArea', 'area_type': 'region', 'region': 'west',
            'is_active': '1',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_service_area_edit(self, auth_client, app, db):
        area, _ = ServiceAreaService.create({
            'name': 'EditArea', 'area_type': 'region', 'region': 'south',
        })
        r = auth_client.get(f'/dispatch/service-areas/{area.id}/edit')
        assert r.status_code == 200

    def test_service_area_delete(self, auth_client, app, db):
        area, _ = ServiceAreaService.create({
            'name': 'DelArea', 'area_type': 'region', 'region': 'east',
        })
        r = auth_client.post(f'/dispatch/service-areas/{area.id}/delete',
                             follow_redirects=True)
        assert r.status_code == 200

    def test_address_create_page(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'Addr', 'last_name': 'T', 'email': 'addr@t.com'},
            created_by=1,
        )
        r = auth_client.get(f'/dispatch/members/{m.id}/addresses/new')
        assert r.status_code == 200

    def test_address_edit_page(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'AE', 'last_name': 'T', 'email': 'ae@t.com'},
            created_by=1,
        )
        addr, _ = AddressService.create(m.id, {
            'street': '5 Oak', 'city': 'NYC', 'state': 'NY', 'zip_code': '10001',
        })
        r = auth_client.get(f'/dispatch/addresses/{addr.id}/edit')
        assert r.status_code == 200


class TestMiddleware401403:
    def test_wrong_role_htmx_returns_403(self, client, app, db, seed_roles):
        AuthService.create_user('viewer99', 'v99@t.com', 'pass', 'viewer')
        client.post('/auth/login', data={'username': 'viewer99', 'password': 'pass'})
        r = client.get('/members/', headers={'HX-Request': 'true'})
        assert r.status_code == 403

    def test_wrong_role_non_htmx_redirects(self, client, app, db, seed_roles):
        AuthService.create_user('viewer98', 'v98@t.com', 'pass', 'viewer')
        client.post('/auth/login', data={'username': 'viewer98', 'password': 'pass'})
        r = client.get('/members/')
        assert r.status_code == 302


class TestSearchDateFilters:
    def test_search_with_date_from(self, auth_client, app, db):
        MemberService.create(
            {'first_name': 'Date', 'last_name': 'Test', 'email': 'date@t.com'},
            created_by=1,
        )
        r = auth_client.get('/search/?date_from=2020-01-01')
        assert r.status_code == 200

    def test_search_with_date_range(self, auth_client, app, db):
        r = auth_client.get('/search/?date_from=2020-01-01&date_to=2030-12-31')
        assert r.status_code == 200

    def test_search_logs_page(self, auth_client, app, db):
        r = auth_client.get('/search/logs')
        assert r.status_code == 200


class TestCleansingEdgeCases:
    def test_upload_no_file(self, auth_client, app, db):
        CleansingService.create_template({'name': 'NoFile'}, created_by=1)
        r = auth_client.post('/cleansing/upload', data={
            'template_id': '1',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_upload_no_template(self, auth_client, app, db):
        r = auth_client.post('/cleansing/upload', data={
            'csv_file': (io.BytesIO(b'a\n1'), 'test.csv'),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_view_nonexistent_job(self, auth_client):
        r = auth_client.get('/cleansing/jobs/999', follow_redirects=True)
        assert r.status_code == 200

    def test_view_nonexistent_template(self, auth_client):
        r = auth_client.get('/cleansing/templates/999', follow_redirects=True)
        assert r.status_code == 200
