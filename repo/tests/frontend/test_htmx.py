"""Frontend component tests validating HTMX partial rendering,
response structure, content semantics, and swap behavior.
Since this is a server-rendered HTMX app (no JS framework), we validate
at the HTTP response level — the same boundary HTMX itself operates at."""
import pytest
from app.extensions import db
from app.models.member import Member
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.address_service import AddressService, ServiceAreaService
from app.services.sla_service import SLAService
from app.services.device_service import DeviceService


class TestHTMXLoginPartial:

    def test_htmx_login_error_returns_form_partial_with_error(self, client, admin_user, app):
        """HTMX login failure must return a form partial (not full page)
        containing the error message and a username input pre-filled."""
        r = client.post('/auth/login', data={
            'username': 'admin', 'password': 'wrong',
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()

        # Must be a partial — no DOCTYPE, no <html>, no <nav>
        assert '<!DOCTYPE' not in html
        assert '<html' not in html
        assert '<nav' not in html

        # Must contain the form with error feedback
        assert '<form' in html
        assert 'Invalid' in html
        assert 'name="username"' in html
        assert 'name="password"' in html
        # Pre-filled username
        assert 'value="admin"' in html

    def test_htmx_login_empty_fields_returns_error(self, client, admin_user, app):
        r = client.post('/auth/login', data={
            'username': '', 'password': '',
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()
        assert '<!DOCTYPE' not in html
        assert 'required' in html.lower()


class TestHTMXMemberList:

    def test_htmx_member_list_returns_table_partial(self, auth_client, app):
        """HTMX member list must return a table partial with member rows."""
        for i in range(3):
            MemberService.create({
                'first_name': f'HX{i}', 'last_name': 'Test',
                'email': f'hx{i}@test.com', 'membership_type': 'basic',
            }, created_by=1)

        r = auth_client.get('/members/', headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert '<table' in html
        assert '<tbody' in html
        # All 3 members present
        assert 'HX0' in html
        assert 'HX1' in html
        assert 'HX2' in html
        # Pagination info
        assert '3 of 3' in html or 'Showing 3' in html

    def test_htmx_member_search_filters_results(self, auth_client, app):
        """HTMX search must return only matching members."""
        MemberService.create({'first_name': 'Alpha', 'last_name': 'B', 'email': 'alpha@t.com'}, created_by=1)
        MemberService.create({'first_name': 'Beta', 'last_name': 'C', 'email': 'beta@t.com'}, created_by=1)

        r = auth_client.get('/members/?search=Alpha', headers={'HX-Request': 'true'})
        html = r.data.decode()
        assert 'Alpha' in html
        assert 'Beta' not in html

    def test_htmx_member_list_empty_state(self, auth_client, app):
        """Empty member list must show 'No members found' message."""
        r = auth_client.get('/members/', headers={'HX-Request': 'true'})
        html = r.data.decode()
        assert 'No members found' in html


class TestHTMXWorkflow:

    def test_htmx_workflow_execute_returns_panel_with_updated_state(self, auth_client, app):
        """After HTMX workflow execute, response must include updated status
        and the timeline showing the action just performed."""
        m, _ = MemberService.create({
            'first_name': 'WF', 'last_name': 'HX', 'email': 'wfhx@t.com',
        }, created_by=1)

        r = auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'JOIN', 'notes': 'HTMX test',
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        # Updated status shown
        assert 'Active' in html or 'active' in html
        # Timeline contains the JOIN entry
        assert 'JOIN' in html
        # Notes should appear in timeline
        assert 'HTMX test' in html

    def test_htmx_workflow_error_returns_partial(self, auth_client, app):
        """Invalid transition via HTMX must return error in partial, not redirect."""
        m, _ = MemberService.create({
            'first_name': 'IV', 'last_name': 'HX', 'email': 'ivhx@t.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)

        r = auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'JOIN',
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()
        assert '<!DOCTYPE' not in html
        # Error should be in flash or rendered in the panel
        # The member status should still be 'active'
        db.session.refresh(m)
        assert m.status == 'active'


class TestHTMXTags:

    def test_htmx_add_tag_returns_updated_tag_list(self, auth_client, app):
        m, _ = MemberService.create({
            'first_name': 'Tag', 'last_name': 'HX', 'email': 'taghx@t.com',
        }, created_by=1)

        r = auth_client.post(f'/members/{m.id}/tags', data={
            'tag_name': 'new-tag',
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert 'new-tag' in html
        # Verify in DB
        member = MemberService.get(m.id)
        assert any(t.name == 'new-tag' for t in member.tags)

    def test_htmx_remove_tag_returns_list_without_tag(self, auth_client, app):
        m, _ = MemberService.create({
            'first_name': 'RT', 'last_name': 'HX', 'email': 'rthx@t.com',
        }, created_by=1)
        MemberService.add_tag(m.id, 'to-remove')
        MemberService.add_tag(m.id, 'to-keep')

        r = auth_client.post(f'/members/{m.id}/tags/to-remove/remove',
                             headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert 'to-remove' not in html
        assert 'to-keep' in html
        # Verify in DB
        member = MemberService.get(m.id)
        tag_names = [t.name for t in member.tags]
        assert 'to-remove' not in tag_names
        assert 'to-keep' in tag_names


class TestHTMXEligibility:

    def test_htmx_eligibility_returns_result_partial(self, auth_client, app):
        """Eligibility check via HTMX must return a result partial with
        the verdict and reason, not a full page."""
        m, _ = MemberService.create({
            'first_name': 'EL', 'last_name': 'HX', 'email': 'elhx@t.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'region': 'hx-region', 'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'HX Area', 'area_type': 'region',
            'region': 'hx-region', 'is_active': True,
        })

        r = auth_client.post(f'/dispatch/members/{m.id}/eligibility', data={
            'address_id': str(addr.id),
        }, headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert '<html' not in html
        assert 'Eligible' in html
        assert 'alert-success' in html  # the result div uses alert-success class


class TestHTMXSearch:

    def test_htmx_search_returns_results_partial_with_structure(self, auth_client, app):
        for i in range(3):
            m, _ = MemberService.create({
                'first_name': f'Find{i}', 'last_name': 'HX',
                'email': f'find{i}@hx.com', 'organization': 'HXCorp',
            }, created_by=1)
            WorkflowService.execute(m.id, 'JOIN', performed_by=1)

        r = auth_client.get('/search/?q=Find', headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        # Must contain result count
        assert '3 result' in html
        # Must contain latency indicator
        assert 'ms)' in html
        # Must contain result cards with member links
        assert 'search-result-card' in html
        assert 'Find0' in html
        assert 'Find1' in html
        assert 'Find2' in html

    def test_htmx_search_no_results_shows_message(self, auth_client, app):
        r = auth_client.get('/search/?q=zzzznothing', headers={'HX-Request': 'true'})
        html = r.data.decode()
        assert 'No members found' in html


class TestHTMXAudit:

    def test_htmx_audit_returns_table_partial(self, auth_client, app):
        from app.services.audit_service import AuditService
        AuditService.log('htmx_test', 'system', username='admin')

        r = auth_client.get('/audit/?q=htmx_test', headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert 'htmx_test' in html
        assert '<table' in html


class TestHTMXDeviceAndSLA:

    def test_htmx_device_remove_returns_updated_list(self, auth_client, app):
        DeviceService.register_device(1, 'dev-htmx-1', 'HTMX Device 1')
        DeviceService.register_device(1, 'dev-htmx-2', 'HTMX Device 2')
        devices = DeviceService.list_devices(1)

        r = auth_client.post(f'/auth/devices/{devices[0].id}/remove',
                             headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        # Only one device should remain
        remaining = DeviceService.list_devices(1)
        assert len(remaining) == 1

    def test_htmx_sla_acknowledge_returns_updated_violation_list(self, auth_client, app):
        SLAService.record_metric('search_latency', 5000.0)
        SLAService.record_metric('search_latency', 3000.0)
        from app.models.sla import SLAViolation
        violations = SLAViolation.query.all()
        assert len(violations) >= 2

        r = auth_client.post(f'/sla/violations/{violations[0].id}/acknowledge',
                             headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert '<table' in html
        # Acknowledged violation should not have acknowledge button
        # The remaining unacknowledged one should still have it
        db.session.refresh(violations[0])
        assert violations[0].is_acknowledged is True

    def test_htmx_address_delete_returns_updated_list(self, auth_client, app):
        m, _ = MemberService.create({
            'first_name': 'AD', 'last_name': 'HX', 'email': 'adhx@t.com',
        }, created_by=1)
        addr1, _ = AddressService.create(m.id, {
            'street': '1 Keep', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })
        addr2, _ = AddressService.create(m.id, {
            'street': '2 Delete', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })

        r = auth_client.post(f'/dispatch/addresses/{addr2.id}/delete',
                             headers={'HX-Request': 'true'})
        html = r.data.decode()

        assert '<!DOCTYPE' not in html
        assert '1 Keep' in html
        assert '2 Delete' not in html
        # Verify DB
        from app.models.address import Address
        assert Address.query.get(addr2.id) is None
        assert Address.query.get(addr1.id) is not None
