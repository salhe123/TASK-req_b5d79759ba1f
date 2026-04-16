import pytest
from app.services.audit_service import AuditService


class TestAuditService:

    def test_log_entry(self, app, admin_user):
        entry = AuditService.log('test_action', 'system', user_id=1, username='admin', details='test')
        assert entry.id is not None
        assert entry.action == 'test_action'
        assert entry.category == 'system'

    def test_search_logs(self, app, admin_user):
        AuditService.log('login_success', 'auth', user_id=1, username='admin')
        AuditService.log('create', 'member', user_id=1, entity_type='member', entity_id=1)

        logs = AuditService.search_logs(category='auth')
        assert logs.total >= 1
        logs = AuditService.search_logs(query='login')
        assert logs.total >= 1

    def test_anomaly_detection(self, app, admin_user):
        app.config['ANOMALY_READ_THRESHOLD'] = 3
        for i in range(4):
            AuditService.log('read', 'member', user_id=1, username='admin')

        alerts = AuditService.get_alerts(resolved=False)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == 'excessive_reads'

    def test_resolve_alert(self, app, admin_user):
        app.config['ANOMALY_READ_THRESHOLD'] = 3
        for i in range(4):
            AuditService.log('read', 'member', user_id=1, username='admin')

        alerts = AuditService.get_alerts(resolved=False)
        ok, _ = AuditService.resolve_alert(alerts[0].id, resolved_by=1)
        assert ok
        alerts = AuditService.get_alerts(resolved=False)
        assert len(alerts) == 0

    def test_anomaly_flagged_logs(self, app, admin_user):
        app.config['ANOMALY_READ_THRESHOLD'] = 3
        for i in range(4):
            AuditService.log('read', 'member', user_id=1, username='admin')

        logs = AuditService.search_logs(anomalies_only=True)
        assert logs.total >= 1

    def test_stats(self, app, admin_user):
        AuditService.log('test', 'system', user_id=1)
        stats = AuditService.get_stats()
        assert stats['total'] >= 1
        assert isinstance(stats['by_category'], list)

    def test_log_with_dict_details(self, app, admin_user):
        entry = AuditService.log('test', 'system', details={'key': 'value'})
        assert '"key"' in entry.details
