"""End-to-end tests that verify cross-module outcomes.
Each test runs a full user workflow and then checks DB state across
all affected subsystems (audit, timeline, SLA, eligibility logs)."""
import io
import json
import pytest

from app.extensions import db
from app.models.member import Member
from app.models.workflow import MemberTimeline
from app.models.audit import AuditLog
from app.models.address import EligibilityLog
from app.models.sla import SLAMetric
from app.models.search import SearchLog
from app.models.cleansing import CleansingJob
from app.services.cleansing_service import CleansingService
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.address_service import AddressService, ServiceAreaService


class TestMemberLifecycleE2E:
    """Full lifecycle: create -> JOIN -> UPGRADE -> DEACTIVATE -> REACTIVATE -> CANCEL.
    Verifies member DB state, timeline entries, and audit logs at each step."""

    def test_complete_lifecycle_with_cross_module_checks(self, auth_client, app):
        # Create
        auth_client.post('/members/new', data={
            'first_name': 'E2E', 'last_name': 'Full',
            'email': 'e2e@lifecycle.com', 'membership_type': 'basic',
            'tags': 'e2e', 'notes': 'Lifecycle test',
        })
        m = Member.query.filter_by(email='e2e@lifecycle.com').first()
        assert m is not None and m.status == 'pending' and m.version == 1

        # JOIN
        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'JOIN', 'notes': 'E2E join',
        })
        db.session.refresh(m)
        assert m.status == 'active'
        t = MemberTimeline.query.filter_by(member_id=m.id, action='JOIN').first()
        assert t.from_status == 'pending' and t.to_status == 'active'
        assert AuditLog.query.filter_by(action='join', category='workflow', entity_id=m.id).count() == 1

        # UPGRADE basic -> premium
        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'UPGRADE', 'new_membership_type': 'premium',
        })
        db.session.refresh(m)
        assert m.membership_type == 'premium'
        t = MemberTimeline.query.filter_by(member_id=m.id, action='UPGRADE').first()
        assert t.from_type == 'basic' and t.to_type == 'premium'

        # DEACTIVATE
        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'DEACTIVATE', 'notes': 'Temp deactivation',
        })
        db.session.refresh(m)
        assert m.status == 'inactive'

        # REACTIVATE
        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'REACTIVATE',
        })
        db.session.refresh(m)
        assert m.status == 'active'

        # CANCEL
        auth_client.post(f'/members/{m.id}/workflow/execute', data={
            'action': 'CANCEL', 'notes': 'Final cancel',
        })
        db.session.refresh(m)
        assert m.status == 'cancelled'

        # Verify complete timeline
        timeline = MemberTimeline.query.filter_by(member_id=m.id)\
            .order_by(MemberTimeline.created_at).all()
        actions = [t.action for t in timeline]
        assert actions == ['JOIN', 'UPGRADE', 'DEACTIVATE', 'REACTIVATE', 'CANCEL']

        # Verify audit trail covers all workflow actions
        audit_actions = {log.action for log in
                         AuditLog.query.filter_by(category='workflow', entity_id=m.id).all()}
        assert audit_actions == {'join', 'upgrade', 'deactivate', 'reactivate', 'cancel'}

        # Timeline page renders all entries
        r = auth_client.get(f'/members/{m.id}/timeline')
        for action in ['JOIN', 'UPGRADE', 'DEACTIVATE', 'REACTIVATE', 'CANCEL']:
            assert action.encode() in r.data


class TestDispatchEligibilityE2E:
    """Create member -> add address -> create service area -> check eligibility.
    Verify eligibility log, audit trail, and DB state."""

    def test_full_dispatch_flow_with_db_verification(self, auth_client, app):
        # Setup
        auth_client.post('/members/new', data={
            'first_name': 'Dispatch', 'last_name': 'E2E',
            'email': 'disp@e2e.com', 'membership_type': 'standard',
        })
        m = Member.query.first()
        auth_client.post(f'/members/{m.id}/workflow/execute', data={'action': 'JOIN'})

        # Create service area
        auth_client.post('/dispatch/service-areas/new', data={
            'name': 'E2E Northeast', 'area_type': 'region',
            'region': 'northeast', 'radius_miles': '25', 'is_active': '1',
        })

        # Add address with region match
        auth_client.post(f'/dispatch/members/{m.id}/addresses/new', data={
            'label': 'primary', 'street': '100 E2E Street', 'city': 'Boston',
            'state': 'MA', 'zip_code': '02101', 'region': 'northeast',
            'latitude': '42.36', 'longitude': '-71.06', 'is_primary': '1',
        })
        from app.models.address import Address
        addr = Address.query.filter_by(member_id=m.id).first()
        assert addr is not None and addr.region == 'northeast'

        # Check eligibility — should be eligible via region match
        r = auth_client.post(f'/dispatch/members/{m.id}/eligibility', data={
            'address_id': str(addr.id),
        }, follow_redirects=True)
        assert b'Eligible' in r.data

        # Verify eligibility log in DB
        elog = EligibilityLog.query.filter_by(member_id=m.id).first()
        assert elog is not None
        assert elog.is_eligible is True
        assert 'Region match' in elog.reason
        assert elog.address_id == addr.id
        assert elog.checked_by == 1


class TestSearchAuditE2E:
    """Create members -> search -> verify search log, SLA metric, and audit trail."""

    def test_search_creates_all_side_effects(self, auth_client, app):
        # Create searchable members
        for i in range(3):
            m, _ = MemberService.create({
                'first_name': f'Findable{i}', 'last_name': 'Person',
                'email': f'find{i}@e2e.com', 'organization': 'FindCorp',
            }, created_by=1)
            WorkflowService.execute(m.id, 'JOIN', performed_by=1)

        before_search_logs = db.session.query(SearchLog).count()
        before_sla = SLAMetric.query.count()

        # Perform search
        r = auth_client.get('/search/?q=Findable')
        assert b'3 result' in r.data

        # Search log created
        assert db.session.query(SearchLog).count() == before_search_logs + 1
        slog = db.session.query(SearchLog).order_by(SearchLog.id.desc()).first()
        assert slog.query == 'Findable'
        assert slog.results_count == 3
        assert slog.user_id == 1

        # SLA metric recorded
        assert SLAMetric.query.count() == before_sla + 1
        metric = SLAMetric.query.order_by(SLAMetric.id.desc()).first()
        assert metric.metric_type == 'search_latency'
        assert metric.value_ms >= 0

        # Audit log page shows entries
        r = auth_client.get('/audit/')
        assert r.status_code == 200

        # Search logs page shows the query
        r = auth_client.get('/search/logs')
        assert b'Findable' in r.data


class TestDataCleansingE2E:
    """Create template -> upload CSV -> verify cleaned data matches expectations."""

    def test_full_cleansing_with_result_verification(self, auth_client, app):
        # Create template with all rules
        auth_client.post('/cleansing/templates/new', data={
            'name': 'E2E Cleansing',
            'description': 'Full pipeline test',
            'field_mapping': json.dumps({'Full Name': 'name', 'Contact': 'email'}),
            'missing_value_rules': json.dumps({'email': {'action': 'flag'}}),
            'dedup_fields': json.dumps(['email']),
            'dedup_threshold': '1.0',
            'format_rules': json.dumps({'email': 'lowercase', 'name': 'titlecase'}),
        })

        csv = (
            b'Full Name,Contact\n'
            b'john doe,JOHN@TEST.COM\n'
            b'jane smith,jane@test.com\n'
            b'john duplicate,JOHN@TEST.COM\n'  # duplicate email
            b'no email,\n'  # flagged
        )
        auth_client.post('/cleansing/upload', data={
            'template_id': '1',
            'csv_file': (io.BytesIO(csv), 'e2e_clean.csv'),
        }, content_type='multipart/form-data')

        job = CleansingJob.query.first()
        assert job.status == 'completed'
        assert job.total_rows == 4
        assert job.duplicate_rows == 1
        assert job.flagged_rows == 1
        assert job.clean_rows == 2

        clean, flagged = CleansingService.get_job_results(job)
        assert len(clean) == 2

        # Verify format rules applied correctly
        john = next(r for r in clean if 'john' in r.get('email', ''))
        assert john['email'] == 'john@test.com'  # lowercased
        assert john['name'] == 'John Doe'  # titlecased

        jane = next(r for r in clean if 'jane' in r.get('email', ''))
        assert jane['email'] == 'jane@test.com'
        assert jane['name'] == 'Jane Smith'

        # Verify flagged data
        assert len(flagged) == 1
        assert '_flag_reason' in flagged[0]
        assert 'email' in flagged[0]['_flag_reason'].lower()

        # Job detail page renders correctly
        r = auth_client.get(f'/cleansing/jobs/{job.id}')
        assert b'Cleansing Job' in r.data
        assert b'john@test.com' in r.data


class TestMultiRoleAccessE2E:
    """Test that each role can only access what it should, across the full system."""

    def test_role_boundaries(self, client, app, seed_roles):
        AuthService.create_user('adm', 'adm@e2e.com', 'pass', 'admin')
        AuthService.create_user('mgr', 'mgr@e2e.com', 'pass', 'manager')
        AuthService.create_user('opr', 'opr@e2e.com', 'pass', 'operator')
        AuthService.create_user('vwr', 'vwr@e2e.com', 'pass', 'viewer')

        def login(username):
            client.get('/auth/logout')
            client.post('/auth/login', data={'username': username, 'password': 'pass'})

        def can_access(path):
            r = client.get(path, follow_redirects=True)
            return b'permission' not in r.data.lower() and b'sign in' not in r.data.lower()

        # Admin — can access everything
        login('adm')
        assert can_access('/admin/')
        assert can_access('/members/')
        assert can_access('/audit/')
        assert can_access('/sla/')
        assert can_access('/cleansing/')
        assert can_access('/search/')
        assert can_access('/dispatch/eligibility')

        # Manager — members, search, dispatch; no admin/audit/sla/cleansing
        login('mgr')
        assert can_access('/members/')
        assert can_access('/search/')
        assert can_access('/dispatch/eligibility')
        assert not can_access('/admin/')
        assert not can_access('/audit/')
        assert not can_access('/cleansing/')

        # Operator — members and search; no dispatch-overview/admin
        login('opr')
        assert can_access('/members/')
        assert can_access('/search/')
        assert not can_access('/admin/')
        assert not can_access('/audit/')
        assert not can_access('/dispatch/eligibility')

        # Viewer — search and dashboard only; no members/admin/audit
        login('vwr')
        assert can_access('/search/')
        assert not can_access('/members/')
        assert not can_access('/admin/')
        assert not can_access('/audit/')


class TestAdminDashboardE2E:
    """Verify admin dashboard aggregates cross-module data correctly."""

    def test_dashboard_reflects_all_subsystems(self, auth_client, app):
        from app.services.sla_service import SLAService
        from app.services.audit_service import AuditService

        # Create members
        for i in range(3):
            m, _ = MemberService.create({
                'first_name': f'Dash{i}', 'last_name': 'T', 'email': f'dash{i}@e2e.com',
            }, created_by=1)
            WorkflowService.execute(m.id, 'JOIN', performed_by=1)

        # Record SLA data
        SLAService.record_metric('search_latency', 500.0)
        SLAService.record_metric('search_latency', 3500.0)  # violation

        # Verify dashboard data
        from app.services.admin_service import AdminService
        data = AdminService.get_dashboard_data()

        assert data['total_members'] == 3
        assert data['total_users'] == 1
        assert data['open_violations'] >= 1
        assert data['audit_events_24h'] > 0
        assert len(data['health']) == 4
        assert all(h['status'] in ('ok', 'warning', 'critical') for h in data['health'])

        # Dashboard page renders
        r = auth_client.get('/admin/')
        assert b'Total Members' in r.data
        assert b'System Health' in r.data
