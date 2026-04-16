import pytest
from app.services.member_service import MemberService, OptimisticLockError


class TestMemberService:

    def _create_member(self, app, admin_user, **overrides):
        data = {
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'john@test.com', 'membership_type': 'basic',
            'organization': 'Acme Corp', 'notes': 'Test member',
        }
        data.update(overrides)
        m, err = MemberService.create(data, created_by=admin_user.id)
        assert err is None
        return m

    def test_create_member(self, app, admin_user):
        m = self._create_member(app, admin_user)
        assert m.id is not None
        assert m.full_name == 'John Doe'
        assert m.status == 'pending'
        assert m.version == 1

    def test_create_duplicate_email(self, app, admin_user):
        self._create_member(app, admin_user)
        m, err = MemberService.create({
            'first_name': 'Jane', 'last_name': 'D',
            'email': 'john@test.com',
        })
        assert m is None
        assert 'already exists' in err

    def test_update_member(self, app, admin_user):
        m = self._create_member(app, admin_user)
        updated, err = MemberService.update(m.id, {
            'first_name': 'Johnny', 'email': 'john@test.com',
        }, updated_by=1, expected_version=1)
        assert updated.first_name == 'Johnny'
        assert updated.version == 2

    def test_optimistic_lock_conflict(self, app, admin_user):
        m = self._create_member(app, admin_user)
        MemberService.update(m.id, {'first_name': 'V2', 'email': 'john@test.com'},
                             expected_version=1)
        with pytest.raises(OptimisticLockError):
            MemberService.update(m.id, {'first_name': 'V3', 'email': 'john@test.com'},
                                 expected_version=1)

    def test_archive_and_restore(self, app, admin_user):
        m = self._create_member(app, admin_user)
        ok, _ = MemberService.delete(m.id)
        assert ok
        member = MemberService.get(m.id)
        assert member.is_archived
        assert member.status == 'cancelled'

        ok, _ = MemberService.restore(m.id)
        member = MemberService.get(m.id)
        assert not member.is_archived
        assert member.status == 'inactive'

    def test_list_pagination(self, app, admin_user):
        for i in range(15):
            MemberService.create({
                'first_name': f'User{i}', 'last_name': 'T', 'email': f'u{i}@t.com',
            }, created_by=1)
        result = MemberService.list_members(page=1, per_page=10)
        assert len(result.items) == 10
        assert result.total == 15
        assert result.pages == 2

    def test_list_search(self, app, admin_user):
        self._create_member(app, admin_user)
        result = MemberService.list_members(search='John')
        assert result.total == 1
        result = MemberService.list_members(search='zzz')
        assert result.total == 0

    def test_list_filters(self, app, admin_user):
        self._create_member(app, admin_user, membership_type='premium')
        result = MemberService.list_members(membership_type='premium')
        assert result.total == 1
        result = MemberService.list_members(membership_type='basic')
        assert result.total == 0

    def test_tags(self, app, admin_user):
        m = self._create_member(app, admin_user)
        MemberService.add_tag(m.id, 'vip')
        MemberService.add_tag(m.id, 'priority')
        member = MemberService.get(m.id)
        assert len(member.tags) == 2

        MemberService.remove_tag(m.id, 'priority')
        member = MemberService.get(m.id)
        assert len(member.tags) == 1

    def test_validation_errors(self, app, admin_user):
        m, err = MemberService.create({'first_name': '', 'last_name': 'X', 'email': 'x@x.com'})
        assert err == 'First name is required.'
        m, err = MemberService.create({'first_name': 'X', 'last_name': 'X', 'email': 'bad'})
        assert err == 'Invalid email address.'
        m, err = MemberService.create({
            'first_name': 'X', 'last_name': 'X',
            'email': 'x@x.com', 'membership_type': 'invalid',
        })
        assert 'Invalid membership type' in err
