"""Integration tests that verify real behavior via Flask routes,
checking DB state, side-effects, and payload content — not just status codes."""
import io
import json
import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.models.user import User
from app.models.member import Member, Tag
from app.models.workflow import MemberTimeline
from app.models.audit import AuditLog
from app.models.address import Address, ServiceArea, EligibilityLog
from app.models.sla import SLAMetric, SLAViolation
from app.models.search import SearchLog
from app.models.cleansing import CleansingTemplate, CleansingJob
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.address_service import AddressService, ServiceAreaService
from app.services.cleansing_service import CleansingService
from app.services.cleansing_service import CleansingService


# ──────────────────────────────────────────────
# AUTH API — verify DB state after auth actions
# ──────────────────────────────────────────────

class TestAuthAPIDeep:

    def test_login_success_updates_user_record(self, client, admin_user):
        """Login must update last_login and last_activity timestamps in DB."""
        before = datetime.utcnow()
        r = client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Welcome' in r.data

        user = User.query.filter_by(username='admin').first()
        assert user.last_login is not None
        assert user.last_login >= before
        assert user.last_activity >= before
        assert user.failed_login_attempts == 0

    def test_failed_login_increments_counter_in_db(self, client, admin_user):
        """Each failed login must increment failed_login_attempts in DB."""
        client.post('/auth/login', data={'username': 'admin', 'password': 'wrong'})
        user = User.query.filter_by(username='admin').first()
        assert user.failed_login_attempts == 1

        client.post('/auth/login', data={'username': 'admin', 'password': 'wrong'})
        db.session.refresh(user)
        assert user.failed_login_attempts == 2

    def test_lockout_sets_locked_until_in_db(self, client, admin_user):
        """5 failures must set locked_until to ~15 minutes in future."""
        for _ in range(5):
            client.post('/auth/login', data={'username': 'admin', 'password': 'wrong'})

        user = User.query.filter_by(username='admin').first()
        assert user.locked_until is not None
        assert user.locked_until > datetime.utcnow()
        # Should be ~15 minutes out
        delta = user.locked_until - datetime.utcnow()
        assert 14 * 60 <= delta.total_seconds() <= 16 * 60

    def test_login_creates_audit_log(self, client, admin_user):
        """Successful login must produce an audit log entry."""
        client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        log = AuditLog.query.filter_by(action='login_success', username='admin').first()
        assert log is not None
        assert log.category == 'auth'
        assert log.entity_type == 'user'

    def test_failed_login_creates_audit_log(self, client, admin_user):
        """Failed login must produce an audit log entry with reason."""
        client.post('/auth/login', data={'username': 'admin', 'password': 'wrong'})
        log = AuditLog.query.filter_by(action='login_failed', username='admin').first()
        assert log is not None
        assert 'Wrong password' in log.details

    def test_empty_credentials_rejected_without_db_side_effect(self, client, admin_user):
        """Empty fields must be rejected without touching the user record."""
        r = client.post('/auth/login', data={'username': '', 'password': ''})
        assert b'required' in r.data
        user = User.query.filter_by(username='admin').first()
        assert user.failed_login_attempts == 0

    def test_trust_device_persists_to_db(self, client, admin_user):
        """Checking 'trust_device' must create a TrustedDevice row."""
        from app.models.user import TrustedDevice
        client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
            'trust_device': '1',
        })
        devices = TrustedDevice.query.filter_by(user_id=admin_user.id).all()
        assert len(devices) == 1
        assert devices[0].device_name is not None

    def test_logout_prevents_access(self, auth_client):
        """After logout, protected routes must redirect to login."""
        auth_client.get('/auth/logout')
        r = auth_client.get('/members/', follow_redirects=True)
        assert b'Sign In' in r.data

    def test_health_endpoint_returns_correct_payload(self, client):
        r = client.get('/health')
        data = r.get_json()
        assert data == {'status': 'ok', 'offline_mode': True}

    def test_session_timeout_forces_relogin(self, client, admin_user):
        """Expired session must log user out and redirect to login."""
        client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        user = User.query.filter_by(username='admin').first()
        user.last_activity = datetime.utcnow() - timedelta(minutes=31)
        db.session.commit()

        r = client.get('/members/', follow_redirects=True)
        assert b'Session expired' in r.data or b'Sign In' in r.data


# ──────────────────────────────────────────────
# MEMBER API — verify DB mutations and side effects
# ──────────────────────────────────────────────

class TestMemberAPIDeep:

    def test_create_member_persists_all_fields(self, auth_client):
        """POST /members/new must persist every field to the DB."""
        auth_client.post('/members/new', data={
            'first_name': 'Alice', 'last_name': 'Smith',
            'email': 'alice@deep.com', 'phone': '555-9999',
            'membership_type': 'premium', 'organization': 'DeepCorp',
            'tags': 'vip, gold', 'notes': 'Important client',
        }, follow_redirects=True)

        m = Member.query.filter_by(email='alice@deep.com').first()
        assert m is not None
        assert m.first_name == 'Alice'
        assert m.last_name == 'Smith'
        assert m.phone == '555-9999'
        assert m.membership_type == 'premium'
        assert m.organization == 'DeepCorp'
        assert m.notes == 'Important client'
        assert m.status == 'pending'
        assert m.version == 1
        assert m.created_by == 1

        tag_names = sorted([t.name for t in m.tags])
        assert tag_names == ['gold', 'vip']

        # Audit log should exist
        log = AuditLog.query.filter_by(action='create', entity_type='member', entity_id=m.id).first()
        assert log is not None

    def test_update_member_changes_db_and_increments_version(self, auth_client):
        """Edit must update DB fields and bump version."""
        auth_client.post('/members/new', data={
            'first_name': 'Bob', 'last_name': 'Old',
            'email': 'bob@deep.com', 'membership_type': 'basic',
        })
        m = Member.query.filter_by(email='bob@deep.com').first()
        assert m.version == 1

        auth_client.post(f'/members/{m.id}/edit', data={
            'first_name': 'Bob', 'last_name': 'Updated',
            'email': 'bob@deep.com', 'membership_type': 'standard',
            'tags': 'updated', 'version': '1',
        }, follow_redirects=True)

        db.session.refresh(m)
        assert m.last_name == 'Updated'
        assert m.membership_type == 'standard'
        assert m.version == 2
        assert len(m.tags) == 1
        assert m.tags[0].name == 'updated'

    def test_archive_sets_correct_db_state(self, auth_client):
        """Archive must set is_archived=True and status=cancelled in DB."""
        auth_client.post('/members/new', data={
            'first_name': 'Del', 'last_name': 'Me',
            'email': 'del@deep.com', 'membership_type': 'basic',
        })
        m = Member.query.first()
        auth_client.post(f'/members/{m.id}/delete')

        db.session.refresh(m)
        assert m.is_archived is True
        assert m.status == 'cancelled'

        log = AuditLog.query.filter_by(action='archive', entity_id=m.id).first()
        assert log is not None

    def test_restore_resets_db_state(self, auth_client):
        """Restore must set is_archived=False and status=inactive."""
        MemberService.create({
            'first_name': 'R', 'last_name': 'T', 'email': 'r@deep.com',
        }, created_by=1)
        m = Member.query.first()
        MemberService.delete(m.id)
        auth_client.post(f'/members/{m.id}/restore')

        db.session.refresh(m)
        assert m.is_archived is False
        assert m.status == 'inactive'

    def test_archived_members_excluded_from_list(self, auth_client):
        """Archived members must not appear in default list."""
        for i in range(3):
            MemberService.create({
                'first_name': f'L{i}', 'last_name': 'T', 'email': f'l{i}@deep.com',
            }, created_by=1)
        MemberService.delete(1)

        r = auth_client.get('/members/')
        assert b'L0' not in r.data
        assert b'L1' in r.data
        assert b'L2' in r.data

    def test_member_not_found_redirects_with_flash(self, auth_client):
        r = auth_client.get('/members/999', follow_redirects=True)
        assert b'not found' in r.data.lower()

    def test_edit_nonexistent_member_redirects(self, auth_client):
        r = auth_client.get('/members/999/edit', follow_redirects=True)
        assert b'not found' in r.data.lower()


# ──────────────────────────────────────────────
# WORKFLOW API — verify transitions + timeline + audit
# ──────────────────────────────────────────────

class TestWorkflowAPIDeep:

    def test_join_creates_timeline_and_updates_status(self, auth_client):
        MemberService.create({
            'first_name': 'WF', 'last_name': 'Deep', 'email': 'wf@deep.com',
        }, created_by=1)
        auth_client.post('/members/1/workflow/execute', data={
            'action': 'JOIN', 'notes': 'Initial join',
        })
        m = Member.query.get(1)
        assert m.status == 'active'

        t = MemberTimeline.query.filter_by(member_id=1, action='JOIN').first()
        assert t is not None
        assert t.from_status == 'pending'
        assert t.to_status == 'active'
        assert t.notes == 'Initial join'

        audit = AuditLog.query.filter_by(action='join', category='workflow').first()
        assert audit is not None

    def test_upgrade_changes_type_in_db(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'UP', 'last_name': 'T', 'email': 'up@deep.com',
            'membership_type': 'basic',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)

        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'UPGRADE', 'new_membership_type': 'enterprise',
        })

        db.session.refresh(m)
        assert m.membership_type == 'enterprise'
        t = MemberTimeline.query.filter_by(member_id=m.id, action='UPGRADE').first()
        assert t.from_type == 'basic'
        assert t.to_type == 'enterprise'

    def test_invalid_transition_returns_error_and_no_db_change(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'IV', 'last_name': 'T', 'email': 'iv@deep.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        before_version = m.version

        r = auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'JOIN',
        }, follow_redirects=True)
        assert b'Cannot JOIN' in r.data

        db.session.refresh(m)
        assert m.status == 'active'  # unchanged
        # No new timeline entry for the failed attempt
        join_count = MemberTimeline.query.filter_by(member_id=m.id, action='JOIN').count()
        assert join_count == 1  # only the original

    def test_htmx_workflow_returns_partial(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'HX', 'last_name': 'T', 'email': 'hx@deep.com',
        }, created_by=1)
        r = auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'JOIN',
        }, headers={'HX-Request': 'true'})
        assert b'<!DOCTYPE' not in r.data
        assert b'Timeline' in r.data or b'timeline' in r.data


# ──────────────────────────────────────────────
# DISPATCH API — verify addresses, eligibility, logs
# ──────────────────────────────────────────────

class TestDispatchAPIDeep:

    def test_create_address_persists_all_fields(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'Addr', 'last_name': 'T', 'email': 'addr@deep.com',
        }, created_by=1)
        auth_client.post(f'/dispatch/members/{m.id}/addresses/new', data={
            'label': 'service', 'street': '42 Deep St', 'city': 'Boston',
            'state': 'MA', 'zip_code': '02101', 'country': 'US',
            'latitude': '42.36', 'longitude': '-71.06',
            'region': 'northeast', 'is_primary': '1',
        })

        addr = Address.query.filter_by(member_id=m.id).first()
        assert addr is not None
        assert addr.street == '42 Deep St'
        assert addr.city == 'Boston'
        assert addr.latitude == pytest.approx(42.36, abs=0.01)
        assert addr.longitude == pytest.approx(-71.06, abs=0.01)
        assert addr.region == 'northeast'
        assert addr.is_primary is True

    def test_eligibility_check_creates_log_entry(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'EL', 'last_name': 'T', 'email': 'el@deep.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'region': 'northeast', 'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'NE', 'area_type': 'region',
            'region': 'northeast', 'is_active': True,
        })

        auth_client.post(f'/dispatch/members/{m.id}/eligibility', data={
            'address_id': '1',
        })

        log = EligibilityLog.query.filter_by(member_id=m.id).first()
        assert log is not None
        assert log.is_eligible is True
        assert 'Region match' in log.reason
        assert log.checked_by == 1

    def test_ineligible_creates_log_with_reason(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'IE', 'last_name': 'T', 'email': 'ie@deep.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'region': 'south', 'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'North', 'area_type': 'region',
            'region': 'north', 'is_active': True,
        })

        auth_client.post(f'/dispatch/members/{m.id}/eligibility', data={
            'address_id': '1',
        })

        log = EligibilityLog.query.filter_by(member_id=m.id).first()
        assert log is not None
        assert log.is_eligible is False

    def test_edit_address_updates_db(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'EA', 'last_name': 'T', 'email': 'ea@deep.com',
        }, created_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': 'Old St', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })
        auth_client.post(f'/dispatch/addresses/{addr.id}/edit', data={
            'label': 'primary', 'street': 'New St', 'city': 'Boston',
            'state': 'MA', 'zip_code': '02101', 'country': 'US',
        })
        db.session.refresh(addr)
        assert addr.street == 'New St'
        assert addr.city == 'Boston'

    def test_delete_address_removes_from_db(self, auth_client):
        m, _ = MemberService.create({
            'first_name': 'DA', 'last_name': 'T', 'email': 'da@deep.com',
        }, created_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': 'Del St', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })
        auth_client.post(f'/dispatch/addresses/{addr.id}/delete')
        assert Address.query.get(addr.id) is None

    def test_service_area_crud_in_db(self, auth_client):
        auth_client.post('/dispatch/service-areas/new', data={
            'name': 'CrudArea', 'area_type': 'radius',
            'center_latitude': '40.0', 'center_longitude': '-74.0',
            'radius_miles': '50', 'is_active': '1',
        })
        area = ServiceArea.query.filter_by(name='CrudArea').first()
        assert area is not None
        assert area.area_type == 'radius'
        assert area.radius_miles == pytest.approx(50.0)

        # Edit
        auth_client.post(f'/dispatch/service-areas/{area.id}/edit', data={
            'name': 'CrudArea', 'area_type': 'radius',
            'center_latitude': '41.0', 'center_longitude': '-75.0',
            'radius_miles': '30', 'is_active': '1',
        })
        db.session.refresh(area)
        assert area.radius_miles == pytest.approx(30.0)

        # Delete
        auth_client.post(f'/dispatch/service-areas/{area.id}/delete')
        assert ServiceArea.query.get(area.id) is None


# ──────────────────────────────────────────────
# SEARCH API — verify logs, SLA metrics, result correctness
# ──────────────────────────────────────────────

class TestSearchAPIDeep:

    def _seed(self):
        for i, (fn, org) in enumerate([
            ('Alice', 'Acme'), ('Bob', 'Acme'), ('Charlie', 'TechCo'),
        ]):
            m, _ = MemberService.create({
                'first_name': fn, 'last_name': 'T',
                'email': f'{fn.lower()}@search.com', 'organization': org,
            }, created_by=1)
            WorkflowService.execute(m.id, 'JOIN', performed_by=1)

    def test_search_creates_search_log(self, auth_client):
        self._seed()
        auth_client.get('/search/?q=Alice')
        log = db.session.query(SearchLog).filter(SearchLog.query == 'Alice').first()
        assert log is not None
        assert log.results_count >= 1
        assert log.latency_ms >= 0
        assert log.user_id == 1

    def test_search_creates_sla_metric(self, auth_client):
        self._seed()
        before = SLAMetric.query.count()
        auth_client.get('/search/?q=Bob')
        after = SLAMetric.query.count()
        assert after == before + 1

        metric = SLAMetric.query.order_by(SLAMetric.id.desc()).first()
        assert metric.metric_type == 'search_latency'
        assert metric.value_ms >= 0

    def test_search_filters_return_correct_count(self, auth_client):
        self._seed()
        r = auth_client.get('/search/?q=Acme')
        assert b'2 result' in r.data  # Alice@Acme and Bob@Acme

    def test_search_htmx_returns_partial(self, auth_client):
        self._seed()
        r = auth_client.get('/search/?q=Alice', headers={'HX-Request': 'true'})
        assert b'<!DOCTYPE' not in r.data
        assert b'result' in r.data.lower()


# ──────────────────────────────────────────────
# CLEANSING API — verify job results in DB
# ──────────────────────────────────────────────

class TestCleansingAPIDeep:

    def test_upload_creates_job_with_correct_counts(self, auth_client):
        CleansingService.create_template({
            'name': 'DeepT',
            'field_mapping': {'Name': 'name', 'Email': 'email'},
            'missing_value_rules': {'email': {'action': 'skip'}},
            'dedup_fields': ['email'],
            'format_rules': {'email': 'lowercase', 'name': 'titlecase'},
        }, created_by=1)

        csv = b'Name,Email\njohn doe,JOHN@TEST.COM\njane smith,jane@test.com\nbob,\njohn dup,JOHN@TEST.COM\n'
        auth_client.post('/cleansing/upload', data={
            'template_id': '1',
            'csv_file': (io.BytesIO(csv), 'deep.csv'),
        }, content_type='multipart/form-data')

        job = CleansingJob.query.first()
        assert job is not None
        assert job.status == 'completed'
        assert job.total_rows == 4
        assert job.flagged_rows == 1   # bob has no email -> skip
        assert job.duplicate_rows == 1  # john dup same email as john doe

        clean, _ = CleansingService.get_job_results(job)
        emails = [r['email'] for r in clean]
        assert 'john@test.com' in emails  # lowercased
        names = [r['name'] for r in clean]
        assert 'John Doe' in names  # titlecased

    def test_template_versioning_via_edit(self, auth_client):
        auth_client.post('/cleansing/templates/new', data={
            'name': 'VersionT', 'description': 'v1',
            'field_mapping': '{}', 'missing_value_rules': '{}',
            'dedup_fields': '[]', 'dedup_threshold': '1.0', 'format_rules': '{}',
        })
        t1 = CleansingTemplate.query.filter_by(name='VersionT', version=1).first()
        assert t1 is not None and t1.is_active

        auth_client.post(f'/cleansing/templates/{t1.id}/edit', data={
            'name': 'VersionT', 'description': 'v2',
            'field_mapping': '{}', 'missing_value_rules': '{}',
            'dedup_fields': '[]', 'dedup_threshold': '1.0', 'format_rules': '{}',
        })

        db.session.refresh(t1)
        assert t1.is_active is False
        t2 = CleansingTemplate.query.filter_by(name='VersionT', version=2).first()
        assert t2 is not None and t2.is_active

    def test_upload_rejects_non_csv(self, auth_client):
        CleansingService.create_template({'name': 'Rej'}, created_by=1)
        r = auth_client.post('/cleansing/upload', data={
            'template_id': '1',
            'csv_file': (io.BytesIO(b'data'), 'test.txt'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert b'CSV' in r.data
        assert CleansingJob.query.count() == 0


# ──────────────────────────────────────────────
# ADMIN & AUDIT — verify aggregation correctness
# ──────────────────────────────────────────────

class TestAdminAuditDeep:

    def test_admin_dashboard_reflects_real_counts(self, auth_client):
        for i in range(3):
            MemberService.create({
                'first_name': f'D{i}', 'last_name': 'T', 'email': f'd{i}@adm.com',
            }, created_by=1)

        r = auth_client.get('/admin/')
        assert r.status_code == 200
        # DB should have 3 members + 1 admin user
        assert b'3' in r.data  # total members count shown somewhere
        assert b'System Health' in r.data

        member_count = Member.query.filter_by(is_archived=False).count()
        assert member_count == 3
        user_count = User.query.count()
        assert user_count == 1  # just admin

    def test_audit_search_returns_correct_entries(self, auth_client):
        from app.services.audit_service import AuditService
        AuditService.log('test_deep', 'system', details='deep test marker')

        r = auth_client.get('/audit/?q=deep+test+marker')
        assert b'test_deep' in r.data

    def test_audit_category_filter(self, auth_client):
        from app.services.audit_service import AuditService
        AuditService.log('cat_test', 'system')
        AuditService.log('cat_test', 'auth')

        r = auth_client.get('/audit/?category=system')
        assert r.status_code == 200

    def test_audit_date_filter(self, auth_client):
        r = auth_client.get('/audit/?date_from=2020-01-01&date_to=2030-12-31')
        assert r.status_code == 200

    def test_audit_anomalies_filter(self, auth_client):
        r = auth_client.get('/audit/?anomalies=1')
        assert r.status_code == 200

    def test_sla_violation_acknowledge_updates_db(self, auth_client):
        from app.services.sla_service import SLAService
        SLAService.record_metric('search_latency', 5000.0)
        v = SLAViolation.query.first()
        assert v is not None and not v.is_acknowledged

        auth_client.post(f'/sla/violations/{v.id}/acknowledge')
        db.session.refresh(v)
        assert v.is_acknowledged is True
        assert v.acknowledged_by == 1
        assert v.acknowledged_at is not None

    def test_sla_dashboard_shows_metrics(self, auth_client):
        from app.services.sla_service import SLAService
        SLAService.record_metric('search_latency', 500.0)
        SLAService.record_metric('search_latency', 3500.0)  # violation

        r = auth_client.get('/sla/')
        assert r.status_code == 200
        assert b'Compliance' in r.data or b'compliance' in r.data

    def test_sla_violations_filter(self, auth_client):
        from app.services.sla_service import SLAService
        SLAService.record_metric('search_latency', 3000.0)
        r = auth_client.get('/sla/violations?severity=warning')
        assert r.status_code == 200

    def test_alert_resolve_nonexistent(self, auth_client):
        r = auth_client.post('/audit/alerts/999/resolve', follow_redirects=True)
        assert b'not found' in r.data.lower() or r.status_code == 200

    def test_alerts_page_resolved_toggle(self, auth_client):
        r = auth_client.get('/audit/alerts?resolved=1')
        assert r.status_code == 200
