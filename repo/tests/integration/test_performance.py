"""Performance validation tests.
Plan requirement: search must return within 2 seconds for 50,000 records."""
import time
import pytest
from app.extensions import db
from app.models.member import Member
from app.models.search import SearchLog
from app.models.sla import SLAMetric
from app.services.search_service import SearchService
from app.services.member_service import MemberService
from app.models.search import rebuild_fts_index


class TestSearchPerformanceSLA:
    """Validate the concrete plan requirement:
    'search must return results within ≤ 2 seconds for 50,000 records'"""

    @pytest.fixture(autouse=True)
    def seed_50k_members(self, app, admin_user):
        """Bulk insert 50,000 members via raw SQL for speed."""
        conn = db.engine.raw_connection()
        cursor = conn.cursor()
        rows = []
        for i in range(50000):
            rows.append((
                f'First{i}', f'Last{i}', f'member{i}@perf.com',
                None, 'basic', 'active', f'PerfOrg{i % 100}',
                f'Performance test member {i}', 1, False, 1,
            ))

        cursor.executemany(
            """INSERT INTO members
               (first_name, last_name, email, phone, membership_type,
                status, organization, notes, version, is_archived, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        conn.close()

        # Rebuild FTS index for the bulk data
        rebuild_fts_index(app)
        yield
        # Cleanup happens via fixture teardown (drop_all)

    def test_search_50k_within_2_seconds(self, app):
        """Search across 50k records must complete within 2000ms."""
        assert Member.query.count() == 50000

        start = time.time()
        result = SearchService.search('First123', user_id=1)
        elapsed_ms = (time.time() - start) * 1000

        assert result['results'].total >= 1
        assert elapsed_ms <= 2000, f'Search took {elapsed_ms:.0f}ms, exceeds 2000ms SLA'

    def test_search_50k_with_filter_within_2_seconds(self, app):
        """Filtered search across 50k records must also meet SLA."""
        start = time.time()
        result = SearchService.search('PerfOrg50', status='active', user_id=1)
        elapsed_ms = (time.time() - start) * 1000

        assert result['results'].total >= 1
        assert elapsed_ms <= 2000, f'Filtered search took {elapsed_ms:.0f}ms, exceeds 2000ms SLA'

    def test_search_50k_empty_query_with_filter(self, app):
        """Non-FTS filtered listing of 50k records must meet SLA."""
        start = time.time()
        result = SearchService.search('', membership_type='basic', user_id=1)
        elapsed_ms = (time.time() - start) * 1000

        assert result['results'].total == 50000
        assert elapsed_ms <= 2000, f'Filter-only search took {elapsed_ms:.0f}ms'

    def test_search_sla_metric_recorded_for_large_dataset(self, app):
        """SLA metric must be recorded even for large-dataset searches."""
        before = SLAMetric.query.count()
        SearchService.search('First999', user_id=1)
        after = SLAMetric.query.count()
        assert after == before + 1

        metric = SLAMetric.query.order_by(SLAMetric.id.desc()).first()
        assert metric.metric_type == 'search_latency'
        assert metric.value_ms <= 2000
