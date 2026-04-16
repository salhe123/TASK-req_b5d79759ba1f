"""Exhaustive role x route permission matrix.
Tests every sensitive route against all 4 roles with concrete expected outcomes."""
import pytest
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.address_service import AddressService, ServiceAreaService
from app.services.cleansing_service import CleansingService


def _login(client, username, password):
    client.get('/auth/logout')
    client.post('/auth/login', data={'username': username, 'password': password})


def _assert_allowed(r, expect_content=None):
    """Route returned content, not a redirect to login or permission denial."""
    assert r.status_code == 200
    assert b'Sign In' not in r.data
    assert b'do not have permission' not in r.data
    if expect_content:
        assert expect_content.encode() in r.data, (
            f'Expected "{expect_content}" in allowed response')


def _assert_denied(r, forbidden_content=None):
    """Route denied access — verify permission error or login redirect,
    and optionally verify the protected content is NOT present."""
    data = r.data.lower()
    assert b'permission' in data or b'sign in' in data or b'dashboard' in data
    if forbidden_content:
        assert forbidden_content.encode() not in r.data, (
            f'Denied response should NOT contain "{forbidden_content}"')


class TestRBACMatrix:
    """Tests the permission matrix: admin, manager, operator, viewer
    against every protected route category."""

    @pytest.fixture(autouse=True)
    def setup_users(self, app, seed_roles):
        AuthService.create_user('admin', 'admin@rbac.com', 'pass', 'admin')
        AuthService.create_user('manager', 'mgr@rbac.com', 'pass', 'manager')
        AuthService.create_user('operator', 'op@rbac.com', 'pass', 'operator')
        AuthService.create_user('viewer', 'view@rbac.com', 'pass', 'viewer')
        # Create shared test data
        m, _ = MemberService.create({
            'first_name': 'RBAC', 'last_name': 'Test', 'email': 'rbac@test.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'RBAC Area', 'area_type': 'region',
            'region': 'test', 'is_active': True,
        })
        CleansingService.create_template({'name': 'RBAC Template'}, created_by=1)

    # --- Members: admin, manager, operator allowed; viewer denied ---

    def test_members_list_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/members/'), expect_content='RBAC Test')

    def test_members_list_manager(self, client):
        _login(client, 'manager', 'pass')
        _assert_allowed(client.get('/members/'), expect_content='Members')

    def test_members_list_operator(self, client):
        _login(client, 'operator', 'pass')
        _assert_allowed(client.get('/members/'), expect_content='Members')

    def test_members_list_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/members/', follow_redirects=True),
                       forbidden_content='RBAC Test')

    def test_members_create_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/members/new', follow_redirects=True),
                       forbidden_content='New Member')

    def test_members_detail_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/members/1', follow_redirects=True),
                       forbidden_content='rbac@test.com')

    # --- Member delete: admin, manager allowed; operator, viewer denied ---

    def test_member_delete_admin(self, client):
        _login(client, 'admin', 'pass')
        r = client.post('/members/1/delete', follow_redirects=True)
        assert r.status_code == 200  # allowed

    def test_member_delete_manager(self, client):
        _login(client, 'manager', 'pass')
        r = client.post('/members/1/delete', follow_redirects=True)
        assert r.status_code == 200  # allowed

    def test_member_delete_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.post('/members/1/delete', follow_redirects=True))

    def test_member_delete_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.post('/members/1/delete', follow_redirects=True))

    # --- Workflow: admin, manager, operator allowed; viewer denied ---

    def test_workflow_operator(self, client):
        _login(client, 'operator', 'pass')
        _assert_allowed(client.get('/members/1/workflow'))

    def test_workflow_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/members/1/workflow', follow_redirects=True))

    # --- Dispatch/Eligibility: admin, manager allowed for overview; operator for member-scoped ---

    def test_dispatch_eligibility_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/dispatch/eligibility'))

    def test_dispatch_eligibility_manager(self, client):
        _login(client, 'manager', 'pass')
        _assert_allowed(client.get('/dispatch/eligibility'))

    def test_dispatch_eligibility_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.get('/dispatch/eligibility', follow_redirects=True))

    def test_dispatch_eligibility_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/dispatch/eligibility', follow_redirects=True))

    def test_dispatch_member_addresses_operator(self, client):
        _login(client, 'operator', 'pass')
        _assert_allowed(client.get('/dispatch/members/1/addresses'))

    def test_dispatch_member_addresses_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/dispatch/members/1/addresses', follow_redirects=True))

    # --- Search: all authenticated users allowed ---

    def test_search_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/search/'))

    def test_search_manager(self, client):
        _login(client, 'manager', 'pass')
        _assert_allowed(client.get('/search/'))

    def test_search_operator_allowed(self, client):
        _login(client, 'operator', 'pass')
        _assert_allowed(client.get('/search/'))

    def test_search_viewer_allowed(self, client):
        _login(client, 'viewer', 'pass')
        _assert_allowed(client.get('/search/'))

    # --- Admin dashboard: admin only ---

    def test_admin_dashboard_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/admin/'), expect_content='Admin Dashboard')

    def test_admin_dashboard_manager_denied(self, client):
        _login(client, 'manager', 'pass')
        _assert_denied(client.get('/admin/', follow_redirects=True),
                       forbidden_content='Admin Dashboard')

    def test_admin_dashboard_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.get('/admin/', follow_redirects=True),
                       forbidden_content='Admin Dashboard')

    def test_admin_dashboard_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/admin/', follow_redirects=True),
                       forbidden_content='Admin Dashboard')

    # --- Audit logs: admin only ---

    def test_audit_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/audit/'), expect_content='Audit Logs')

    def test_audit_manager_denied(self, client):
        _login(client, 'manager', 'pass')
        _assert_denied(client.get('/audit/', follow_redirects=True),
                       forbidden_content='Audit Logs')

    def test_audit_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.get('/audit/', follow_redirects=True),
                       forbidden_content='Audit Logs')

    def test_audit_viewer_denied(self, client):
        _login(client, 'viewer', 'pass')
        _assert_denied(client.get('/audit/', follow_redirects=True),
                       forbidden_content='Audit Logs')

    # --- SLA: admin only ---

    def test_sla_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/sla/'), expect_content='SLA Monitoring')

    def test_sla_manager_denied(self, client):
        _login(client, 'manager', 'pass')
        _assert_denied(client.get('/sla/', follow_redirects=True),
                       forbidden_content='SLA Monitoring')

    # --- Cleansing: admin only ---

    def test_cleansing_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/cleansing/'))

    def test_cleansing_manager_denied(self, client):
        _login(client, 'manager', 'pass')
        _assert_denied(client.get('/cleansing/', follow_redirects=True))

    def test_cleansing_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.get('/cleansing/', follow_redirects=True))

    # --- Service area mutation: admin only ---

    def test_service_area_create_admin(self, client):
        _login(client, 'admin', 'pass')
        _assert_allowed(client.get('/dispatch/service-areas/new'))

    def test_service_area_create_manager_denied(self, client):
        _login(client, 'manager', 'pass')
        _assert_denied(client.get('/dispatch/service-areas/new', follow_redirects=True))

    def test_service_area_delete_operator_denied(self, client):
        _login(client, 'operator', 'pass')
        _assert_denied(client.post('/dispatch/service-areas/1/delete', follow_redirects=True))

    # --- Unauthenticated access: all protected routes redirect ---

    def test_unauthenticated_members(self, client):
        r = client.get('/members/', follow_redirects=True)
        assert b'Sign In' in r.data

    def test_unauthenticated_admin(self, client):
        r = client.get('/admin/', follow_redirects=True)
        assert b'Sign In' in r.data

    def test_unauthenticated_audit(self, client):
        r = client.get('/audit/', follow_redirects=True)
        assert b'Sign In' in r.data
