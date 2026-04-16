"""Integration tests for reauth flow and device trust login behavior."""
import pytest
from app.services.auth_service import AuthService


class TestReauthFlow:

    def test_reauth_page_renders(self, auth_client):
        r = auth_client.get('/auth/reauth')
        assert r.status_code == 200
        assert b'Re-authenticate' in r.data

    def test_reauth_with_correct_password(self, auth_client):
        r = auth_client.post('/auth/reauth', data={'password': 'admin123'},
                             follow_redirects=True)
        assert r.status_code == 200

    def test_reauth_with_wrong_password(self, auth_client):
        r = auth_client.post('/auth/reauth', data={'password': 'wrong'})
        assert b'Incorrect' in r.data or b'incorrect' in r.data

    def test_reauth_empty_password(self, auth_client):
        r = auth_client.post('/auth/reauth', data={'password': ''})
        assert b'required' in r.data.lower()

    def test_reauth_redirects_to_next(self, auth_client):
        r = auth_client.post('/auth/reauth?next=/admin/users',
                             data={'password': 'admin123'})
        assert r.status_code == 302
        assert '/admin/users' in r.headers['Location']


class TestDeviceListView:

    def test_device_list_renders(self, auth_client):
        r = auth_client.get('/auth/devices')
        assert r.status_code == 200

    def test_device_remove(self, app, auth_client, db):
        from app.services.device_service import DeviceService
        device, _ = DeviceService.register_device(1, 'test_dev_id', 'Test Dev')
        r = auth_client.post(f'/auth/devices/{device.id}/remove', follow_redirects=True)
        assert r.status_code == 200


class TestLoginDeviceTrust:

    def test_untrusted_device_warning(self, client, admin_user):
        r = client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Welcome' in r.data

    def test_logout_clears_session(self, auth_client):
        r = auth_client.post('/auth/logout', follow_redirects=True)
        assert r.status_code == 200
        assert b'logged out' in r.data.lower()
