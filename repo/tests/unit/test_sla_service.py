import pytest
from app.services.sla_service import SLAService


class TestSLAService:

    def test_record_metric(self, app, admin_user):
        metric = SLAService.record_metric('search_latency', 500.0, endpoint='/search')
        assert metric.id is not None
        assert metric.value_ms == 500.0

    def test_violation_on_breach(self, app, admin_user):
        SLAService.record_metric('search_latency', 3000.0)
        violations = SLAService.get_violations()
        assert len(violations) >= 1
        assert violations[0].severity == 'warning'

    def test_critical_violation(self, app, admin_user):
        SLAService.record_metric('search_latency', 5000.0)
        violations = SLAService.get_violations(severity='critical')
        assert len(violations) >= 1

    def test_no_violation_within_sla(self, app, admin_user):
        SLAService.record_metric('search_latency', 1500.0)
        violations = SLAService.get_violations()
        assert len(violations) == 0

    def test_acknowledge_violation(self, app, admin_user):
        SLAService.record_metric('search_latency', 3000.0)
        violations = SLAService.get_violations(acknowledged=False)
        ok, _ = SLAService.acknowledge_violation(violations[0].id, user_id=1)
        assert ok
        remaining = SLAService.get_violations(acknowledged=False)
        assert len(remaining) == 0

    def test_dashboard_stats(self, app, admin_user):
        SLAService.record_metric('search_latency', 500.0)
        SLAService.record_metric('search_latency', 3000.0)
        stats = SLAService.get_dashboard_stats()
        assert len(stats['summary']) >= 1
        assert stats['summary'][0]['count'] == 2
        assert stats['violation_count'] >= 1
