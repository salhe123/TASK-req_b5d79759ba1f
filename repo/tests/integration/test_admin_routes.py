"""Integration tests for admin user management, device oversight, and search config."""
import pytest
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService
from app.services.admin_service import AdminService
from app.models.user import User


def _login(client, username, password):
    client.post('/auth/login', data={'username': username, 'password': password})


class TestAdminUserManagement:

    def test_users_list_page(self, auth_client):
        r = auth_client.get('/admin/users')
        assert r.status_code == 200
        assert b'admin' in r.data

    def test_deactivate_user(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('target1', 't1@test.com', 'pass', 'operator')
        r = auth_client.post(f'/admin/users/{target.id}/deactivate', follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(target)
        assert target.is_active is False

    def test_activate_user(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('target2', 't2@test.com', 'pass', 'operator')
        AdminService.deactivate_user(target.id, performed_by=1)
        r = auth_client.post(f'/admin/users/{target.id}/activate', follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(target)
        assert target.is_active is True

    def test_freeze_user(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('target3', 't3@test.com', 'pass', 'operator')
        r = auth_client.post(f'/admin/users/{target.id}/freeze', follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(target)
        assert target.locked_until is not None
        assert target.locked_until.year > 2050

    def test_unfreeze_user(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('target4', 't4@test.com', 'pass', 'operator')
        AdminService.freeze_user(target.id, performed_by=1)
        r = auth_client.post(f'/admin/users/{target.id}/unfreeze', follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(target)
        assert target.locked_until is None

    def test_change_role(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('target5', 't5@test.com', 'pass', 'operator')
        r = auth_client.post(f'/admin/users/{target.id}/change-role',
                             data={'role': 'manager'}, follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(target)
        assert target.role == 'manager'

    def test_cannot_deactivate_self(self, auth_client):
        r = auth_client.post('/admin/users/1/deactivate', follow_redirects=True)
        assert b'cannot deactivate your own' in r.data.lower()

    def test_cannot_change_own_role(self, auth_client):
        r = auth_client.post('/admin/users/1/change-role',
                             data={'role': 'viewer'}, follow_redirects=True)
        assert b'cannot change your own' in r.data.lower()

    def test_htmx_returns_partial(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('htmx1', 'htmx1@t.com', 'pass', 'viewer')
        r = auth_client.post(f'/admin/users/{target.id}/activate',
                             headers={'HX-Request': 'true'}, follow_redirects=True)
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data


class TestAdminDeviceOversight:

    def test_view_user_devices(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('devuser', 'dev@t.com', 'pass', 'operator')
        DeviceService.register_device(target.id, 'abc123', 'Test Device')
        r = auth_client.get(f'/admin/users/{target.id}/devices')
        assert r.status_code == 200
        assert b'Test Device' in r.data

    def test_revoke_device(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('devuser2', 'dev2@t.com', 'pass', 'operator')
        device, _ = DeviceService.register_device(target.id, 'xyz789', 'My Phone')
        r = auth_client.post(f'/admin/devices/{device.id}/revoke', follow_redirects=True)
        assert r.status_code == 200
        assert DeviceService.get_device(target.id, 'xyz789') is None

    def test_revoke_all_devices(self, app, auth_client, db, seed_roles):
        target = AuthService.create_user('devuser3', 'dev3@t.com', 'pass', 'operator')
        DeviceService.register_device(target.id, 'd1', 'Device 1')
        DeviceService.register_device(target.id, 'd2', 'Device 2')
        r = auth_client.post(f'/admin/users/{target.id}/devices/revoke-all',
                             follow_redirects=True)
        assert r.status_code == 200
        assert len(DeviceService.list_devices(target.id)) == 0


class TestAdminSearchConfig:

    def test_get_search_config(self, auth_client):
        r = auth_client.get('/admin/search-config')
        assert r.status_code == 200
        assert b'Trending' in r.data

    def test_post_search_config(self, app, auth_client, db):
        r = auth_client.post('/admin/search-config', data={
            'search_trending_limit': '15',
            'search_trending_days': '14',
            'search_recommendations_limit': '8',
            'search_results_per_page': '25',
        }, follow_redirects=True)
        assert r.status_code == 200
        from app.models.config import SystemConfig
        row = db.session.query(SystemConfig).filter_by(key='search_trending_limit').first()
        assert row is not None
        assert row.value == '15'
