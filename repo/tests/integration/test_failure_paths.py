"""Failure and edge-path tests verifying strict error contracts,
invalid input handling, and boundary conditions with DB state checks."""
import io
import json
import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.models.user import User, TrustedDevice
from app.models.member import Member
from app.models.workflow import MemberTimeline
from app.models.address import Address
from app.models.audit import AuditLog, AnomalyAlert
from app.models.sla import SLAViolation
from app.services.auth_service import AuthService
from app.services.member_service import MemberService, OptimisticLockError
from app.services.workflow_service import WorkflowService, InvalidTransitionError
from app.services.address_service import AddressService, ServiceAreaService, EligibilityService
from app.services.device_service import DeviceService
from app.services.cleansing_service import CleansingService
from app.services.sla_service import SLAService
from app.services.audit_service import AuditService
from app.models.search import rebuild_fts_index


# ──────────────────────────────────────────────
# AUTH FAILURE PATHS
# ──────────────────────────────────────────────

class TestAuthFailurePaths:

    def test_login_after_lockout_with_correct_password_still_rejected(self, client, admin_user):
        for _ in range(5):
            client.post('/auth/login', data={'username': 'admin', 'password': 'wrong'})
        r = client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, follow_redirects=True)
        assert b'locked' in r.data.lower()
        user = User.query.first()
        assert user.locked_until > datetime.utcnow()

    def test_lockout_creates_audit_log(self, app, admin_user):
        for _ in range(5):
            AuthService.authenticate('admin', 'wrong')
        log = AuditLog.query.filter_by(action='account_locked').first()
        assert log is not None
        assert 'failed attempts' in log.details

    def test_deactivated_user_cannot_login_via_route(self, client, admin_user):
        user = User.query.first()
        user.is_active = False
        db.session.commit()
        r = client.post('/auth/login', data={
            'username': 'admin', 'password': 'admin123',
        }, follow_redirects=True)
        assert b'deactivated' in r.data.lower()

    def test_device_limit_enforced(self, app, admin_user):
        for i in range(5):
            DeviceService.register_device(admin_user.id, f'dev-{i}', f'Device {i}')
        dev, err = DeviceService.register_device(admin_user.id, 'dev-extra', 'Extra')
        assert dev is None
        assert 'Maximum' in err
        assert TrustedDevice.query.count() == 5

    def test_remove_nonexistent_device(self, app, admin_user):
        ok, err = DeviceService.remove_device(admin_user.id, 999)
        assert not ok
        assert 'not found' in err.lower()

    def test_device_identifier_generation(self, app):
        with app.test_request_context(headers={
            'User-Agent': 'TestBrowser/1.0', 'Accept-Language': 'en-US',
        }):
            from flask import request
            did = DeviceService.generate_device_identifier(request)
            assert isinstance(did, str)
            assert len(did) == 64


# ──────────────────────────────────────────────
# MEMBER FAILURE PATHS
# ──────────────────────────────────────────────

class TestMemberFailurePaths:

    def test_create_with_invalid_type_shows_error(self, auth_client):
        r = auth_client.post('/members/new', data={
            'first_name': 'Bad', 'last_name': 'Type',
            'email': 'bad@type.com', 'membership_type': 'nonexistent',
        }, follow_redirects=True)
        assert Member.query.count() == 0  # nothing persisted

    def test_create_with_missing_email(self, auth_client):
        r = auth_client.post('/members/new', data={
            'first_name': 'No', 'last_name': 'Email', 'email': '',
        }, follow_redirects=True)
        assert Member.query.count() == 0

    def test_create_with_invalid_email(self, auth_client):
        r = auth_client.post('/members/new', data={
            'first_name': 'Bad', 'last_name': 'Email', 'email': 'not-an-email',
        }, follow_redirects=True)
        assert Member.query.count() == 0

    def test_optimistic_lock_conflict_via_route(self, auth_client):
        MemberService.create({
            'first_name': 'Lock', 'last_name': 'T', 'email': 'lock@test.com',
        }, created_by=1)
        # Update via service to bump version
        MemberService.update(1, {'first_name': 'V2', 'email': 'lock@test.com'}, expected_version=1)

        # Route uses stale version=1
        r = auth_client.post('/members/1/edit', data={
            'first_name': 'V3', 'email': 'lock@test.com', 'version': '1',
        }, follow_redirects=True)
        assert b'modified by another user' in r.data.lower() or b'refresh' in r.data.lower()

        m = Member.query.get(1)
        assert m.first_name == 'V2'  # unchanged by the conflicting route call

    def test_update_archived_member_rejected(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'Arc', 'last_name': 'T', 'email': 'arc@test.com',
        }, created_by=1)
        MemberService.delete(m.id)
        updated, err = MemberService.update(m.id, {'first_name': 'X', 'email': 'arc@test.com'})
        assert updated is None
        assert 'archived' in err.lower()

    def test_delete_nonexistent_member(self, app, admin_user):
        ok, err = MemberService.delete(999)
        assert not ok
        assert 'not found' in err.lower()

    def test_restore_nonexistent_member(self, app, admin_user):
        ok, err = MemberService.restore(999)
        assert not ok
        assert 'not found' in err.lower()

    def test_add_tag_to_nonexistent_member(self, app, admin_user):
        ok, err = MemberService.add_tag(999, 'tag')
        assert not ok


# ──────────────────────────────────────────────
# WORKFLOW FAILURE PATHS
# ──────────────────────────────────────────────

class TestWorkflowFailurePaths:

    def test_unknown_action(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'W', 'last_name': 'T', 'email': 'w@fail.com',
        }, created_by=1)
        with pytest.raises(InvalidTransitionError, match='Unknown action'):
            WorkflowService.execute(m.id, 'NONEXISTENT')

    def test_nonexistent_member(self, app, admin_user):
        with pytest.raises(InvalidTransitionError, match='not found'):
            WorkflowService.execute(999, 'JOIN')

    def test_archived_member(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'A', 'last_name': 'T', 'email': 'a@fail.com',
        }, created_by=1)
        MemberService.delete(m.id)
        with pytest.raises(InvalidTransitionError, match='archived'):
            WorkflowService.execute(m.id, 'JOIN')

    def test_upgrade_with_invalid_type(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'U', 'last_name': 'T', 'email': 'u@fail.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        with pytest.raises(InvalidTransitionError, match='Invalid membership type'):
            WorkflowService.execute(m.id, 'UPGRADE', new_membership_type='imaginary')

    def test_downgrade_at_lowest_tier(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'D', 'last_name': 'T', 'email': 'd@fail.com',
            'membership_type': 'basic',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        with pytest.raises(InvalidTransitionError, match='lowest'):
            WorkflowService.execute(m.id, 'DOWNGRADE')

    def test_failed_transition_no_timeline_entry(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'F', 'last_name': 'T', 'email': 'f@fail.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        before = MemberTimeline.query.filter_by(member_id=m.id).count()
        try:
            WorkflowService.execute(m.id, 'JOIN')
        except InvalidTransitionError:
            pass
        after = MemberTimeline.query.filter_by(member_id=m.id).count()
        assert after == before  # no new timeline entry


# ──────────────────────────────────────────────
# ELIGIBILITY FAILURE PATHS
# ──────────────────────────────────────────────

class TestEligibilityFailurePaths:

    def test_member_not_found(self, app, admin_user):
        eligible, reason, _ = EligibilityService.check_eligibility(999)
        assert not eligible
        assert 'not found' in reason.lower()

    def test_no_address_for_member(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'NA', 'last_name': 'T', 'email': 'na@fail.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        eligible, reason, log = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible
        assert 'No address' in reason
        assert log.is_eligible is False

    def test_no_active_service_areas(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'NS', 'last_name': 'T', 'email': 'ns@fail.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'is_primary': True,
        })
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible
        assert 'No active service areas' in reason

    def test_address_validation_latitude_out_of_range(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'LR', 'last_name': 'T', 'email': 'lr@fail.com',
        }, created_by=1)
        _, err = AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'latitude': -100,
        })
        assert 'Latitude' in err
        assert Address.query.count() == 0

    def test_address_validation_missing_fields(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'MF', 'last_name': 'T', 'email': 'mf@fail.com',
        }, created_by=1)
        for field, expected in [
            ('street', 'Street'), ('city', 'City'), ('state', 'State'), ('zip_code', 'ZIP'),
        ]:
            data = {'street': '1', 'city': 'X', 'state': 'Y', 'zip_code': '00000'}
            data[field] = ''
            _, err = AddressService.create(m.id, data)
            assert expected in err

    def test_service_area_duplicate_name(self, app, admin_user):
        ServiceAreaService.create({
            'name': 'Dup', 'area_type': 'region', 'region': 'x',
        })
        _, err = ServiceAreaService.create({
            'name': 'Dup', 'area_type': 'region', 'region': 'y',
        })
        assert 'already exists' in err

    def test_radius_check_missing_coordinates(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'MC', 'last_name': 'T', 'email': 'mc@fail.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        AddressService.create(m.id, {
            'street': '1 St', 'city': 'X', 'state': 'Y',
            'zip_code': '00000', 'is_primary': True,
            # no lat/lng
        })
        ServiceAreaService.create({
            'name': 'Radius No Coords', 'area_type': 'radius',
            'center_latitude': 40.0, 'center_longitude': -74.0,
            'radius_miles': 25, 'is_active': True,
        })
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible


# ──────────────────────────────────────────────
# CLEANSING FAILURE PATHS
# ──────────────────────────────────────────────

class TestCleansingFailurePaths:

    def test_create_job_with_nonexistent_template(self, app, admin_user):
        job, err = CleansingService.create_job(999, 'a,b\n1,2', 'x.csv')
        assert job is None
        assert 'not found' in err.lower()

    def test_execute_already_completed_job(self, app, admin_user):
        t, _ = CleansingService.create_template({'name': 'EC'}, created_by=1)
        job, _ = CleansingService.create_job(t.id, 'a\n1', 'x.csv')
        CleansingService.execute_job(job.id)
        _, err = CleansingService.execute_job(job.id)
        assert 'already completed' in err.lower()

    def test_execute_nonexistent_job(self, app, admin_user):
        _, err = CleansingService.execute_job(999)
        assert 'not found' in err.lower()

    def test_empty_csv(self, app, admin_user):
        t, _ = CleansingService.create_template({'name': 'Empty'}, created_by=1)
        job, _ = CleansingService.create_job(t.id, 'a,b\n', 'empty.csv')
        job, _ = CleansingService.execute_job(job.id)
        assert job.status == 'completed'
        assert job.total_rows == 0
        assert job.clean_rows == 0

    def test_update_nonexistent_template(self, app, admin_user):
        _, err = CleansingService.update_template(999, {})
        assert 'not found' in err.lower()

    def test_deactivate_nonexistent_template(self, app, admin_user):
        ok, err = CleansingService.delete_template(999)
        assert not ok


# ──────────────────────────────────────────────
# ANOMALY DETECTION EDGE CASES
# ──────────────────────────────────────────────

class TestAnomalyEdgeCases:

    def test_anomaly_triggered_at_threshold(self, app, admin_user):
        app.config['ANOMALY_READ_THRESHOLD'] = 3
        for _ in range(4):
            AuditService.log('read', 'member', user_id=1, username='admin')

        alerts = AuditService.get_alerts(resolved=False)
        assert len(alerts) == 1
        assert alerts[0].severity == 'warning'
        assert 'admin' in alerts[0].description

        # Flagged in audit log
        flagged = AuditLog.query.filter_by(is_anomaly=True).count()
        assert flagged >= 3

    def test_duplicate_anomaly_not_created(self, app, admin_user):
        """Within the same window, only one alert should be created."""
        app.config['ANOMALY_READ_THRESHOLD'] = 3
        for _ in range(10):
            AuditService.log('read', 'member', user_id=1, username='admin')

        alerts = AuditService.get_alerts(resolved=False)
        assert len(alerts) == 1  # only one, not multiple

    def test_resolve_nonexistent_alert(self, app, admin_user):
        ok, err = AuditService.resolve_alert(999)
        assert not ok
        assert 'not found' in err.lower()


# ──────────────────────────────────────────────
# SLA EDGE CASES
# ──────────────────────────────────────────────

class TestSLAEdgeCases:

    def test_critical_severity_at_2x_threshold(self, app, admin_user):
        SLAService.record_metric('search_latency', 4001.0)  # > 2000*2
        v = SLAViolation.query.first()
        assert v.severity == 'critical'

    def test_warning_severity_under_2x(self, app, admin_user):
        SLAService.record_metric('search_latency', 3000.0)  # > 2000 but < 4000
        v = SLAViolation.query.first()
        assert v.severity == 'warning'

    def test_no_violation_at_threshold(self, app, admin_user):
        SLAService.record_metric('search_latency', 2000.0)  # exactly at threshold
        assert SLAViolation.query.count() == 0

    def test_acknowledge_nonexistent_violation(self, app, admin_user):
        ok, err = SLAService.acknowledge_violation(999)
        assert not ok

    def test_dashboard_stats_with_no_data(self, app, admin_user):
        stats = SLAService.get_dashboard_stats()
        assert stats['violation_count'] == 0
        assert stats['unacknowledged'] == 0
        assert len(stats['summary']) == 0

    def test_fts_rebuild_and_search(self, app, admin_user):
        """Verify FTS index rebuild works correctly."""
        MemberService.create({
            'first_name': 'Rebuild', 'last_name': 'FTS', 'email': 'rebuild@fts.com',
        }, created_by=1)
        rebuild_fts_index(app)
        from app.services.search_service import SearchService
        result = SearchService.search('Rebuild')
        assert result['results'].total == 1
