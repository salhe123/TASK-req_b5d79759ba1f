import pytest
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService, InvalidTransitionError


class TestWorkflowService:

    def _create_active_member(self, app, admin_user, mtype='basic'):
        m, _ = MemberService.create({
            'first_name': 'W', 'last_name': 'Test',
            'email': f'w{mtype}@t.com', 'membership_type': mtype,
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        return m

    def test_join(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'J', 'last_name': 'T', 'email': 'j@t.com',
        }, created_by=1)
        assert m.status == 'pending'
        m, t = WorkflowService.execute(m.id, 'JOIN', performed_by=1, notes='Welcome')
        assert m.status == 'active'
        assert t.from_status == 'pending'
        assert t.to_status == 'active'
        assert t.notes == 'Welcome'

    def test_invalid_join_on_active(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        with pytest.raises(InvalidTransitionError, match='Cannot JOIN'):
            WorkflowService.execute(m.id, 'JOIN')

    def test_upgrade_default(self, app, admin_user):
        m = self._create_active_member(app, admin_user, 'basic')
        m, t = WorkflowService.execute(m.id, 'UPGRADE')
        assert m.membership_type == 'standard'
        assert t.from_type == 'basic'

    def test_upgrade_specific_tier(self, app, admin_user):
        m = self._create_active_member(app, admin_user, 'basic')
        m, _ = WorkflowService.execute(m.id, 'UPGRADE', new_membership_type='enterprise')
        assert m.membership_type == 'enterprise'

    def test_upgrade_past_top_fails(self, app, admin_user):
        m = self._create_active_member(app, admin_user, 'basic')
        WorkflowService.execute(m.id, 'UPGRADE', new_membership_type='enterprise')
        with pytest.raises(InvalidTransitionError):
            WorkflowService.execute(m.id, 'UPGRADE')

    def test_downgrade(self, app, admin_user):
        m = self._create_active_member(app, admin_user, 'basic')
        WorkflowService.execute(m.id, 'UPGRADE', new_membership_type='premium')
        m, _ = WorkflowService.execute(m.id, 'DOWNGRADE', new_membership_type='standard')
        assert m.membership_type == 'standard'

    def test_downgrade_to_higher_fails(self, app, admin_user):
        m = self._create_active_member(app, admin_user, 'basic')
        WorkflowService.execute(m.id, 'UPGRADE', new_membership_type='standard')
        with pytest.raises(InvalidTransitionError):
            WorkflowService.execute(m.id, 'DOWNGRADE', new_membership_type='premium')

    def test_deactivate_and_reactivate(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        m, _ = WorkflowService.execute(m.id, 'DEACTIVATE')
        assert m.status == 'inactive'
        m, _ = WorkflowService.execute(m.id, 'REACTIVATE')
        assert m.status == 'active'

    def test_cancel(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        m, _ = WorkflowService.execute(m.id, 'CANCEL')
        assert m.status == 'cancelled'
        actions = WorkflowService.get_available_actions(m)
        assert len(actions) == 0

    def test_renew(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        m, _ = WorkflowService.execute(m.id, 'RENEW')
        assert m.status == 'active'

    def test_timeline(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        WorkflowService.execute(m.id, 'UPGRADE')
        WorkflowService.execute(m.id, 'DEACTIVATE')
        timeline = WorkflowService.get_timeline(m.id)
        assert len(timeline) == 3  # JOIN, UPGRADE, DEACTIVATE

    def test_archived_member_blocked(self, app, admin_user):
        m = self._create_active_member(app, admin_user)
        MemberService.delete(m.id)
        with pytest.raises(InvalidTransitionError):
            WorkflowService.execute(m.id, 'RENEW')

    def test_available_actions(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'A', 'last_name': 'T', 'email': 'avail@t.com',
        }, created_by=1)
        actions = WorkflowService.get_available_actions(m)
        assert 'JOIN' in actions
        assert 'CANCEL' in actions
        assert 'RENEW' not in actions
