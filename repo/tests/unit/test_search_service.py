import pytest
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.search_service import SearchService


class TestSearchService:

    def _seed_members(self, app, admin_user):
        data = [
            ('Alice', 'Smith', 'alice@acme.com', 'premium', 'Acme Corp'),
            ('Bob', 'Jones', 'bob@tech.com', 'basic', 'TechCo'),
            ('Charlie', 'Brown', 'charlie@acme.com', 'standard', 'Acme Corp'),
        ]
        for fn, ln, email, mtype, org in data:
            m, _ = MemberService.create({
                'first_name': fn, 'last_name': ln, 'email': email,
                'membership_type': mtype, 'organization': org,
            }, created_by=1)
            WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        MemberService.add_tag(1, 'vip')

    def test_fts_search_by_name(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('Alice', user_id=1)
        assert result['results'].total >= 1

    def test_fts_search_by_org(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('Acme', user_id=1)
        assert result['results'].total >= 2

    def test_search_with_status_filter(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('', status='active')
        assert result['results'].total == 3

    def test_search_with_type_filter(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('', membership_type='premium')
        assert result['results'].total == 1

    def test_search_with_tag_filter(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('', tag_name='vip')
        assert result['results'].total == 1

    def test_search_highlights(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('Alice')
        assert len(result['highlights']) > 0
        has_mark = any('<mark>' in str(v) for h in result['highlights'].values() for v in h.values())
        assert has_mark

    def test_search_no_results(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('zzzznonexistent')
        assert result['results'].total == 0

    def test_search_latency_tracked(self, app, admin_user):
        self._seed_members(app, admin_user)
        result = SearchService.search('Alice', user_id=1)
        assert result['latency_ms'] >= 0

    def test_search_logging(self, app, admin_user):
        self._seed_members(app, admin_user)
        SearchService.search('test_query', user_id=1)
        logs = SearchService.get_search_logs()
        assert any(l.query == 'test_query' for l in logs)

    def test_trending(self, app, admin_user):
        self._seed_members(app, admin_user)
        for _ in range(5):
            SearchService.search('trending_term', user_id=1)
        trending = SearchService.get_trending()
        assert len(trending) > 0
        assert trending[0]['query'] == 'trending_term'

    def test_recommendations(self, app, admin_user):
        self._seed_members(app, admin_user)
        SearchService.search('Alice', user_id=1)
        recs = SearchService.get_recommendations(user_id=1)
        assert isinstance(recs, list)
