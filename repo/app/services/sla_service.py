from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import select, func

from app.extensions import db
from app.models.sla import SLAMetric, SLAViolation


# Default SLA thresholds in milliseconds
DEFAULT_THRESHOLDS = {
    'search_latency': 2000.0,  # 2 seconds
}


class SLAService:

    @staticmethod
    def record_metric(metric_type, value_ms, endpoint=None, details=None, user_id=None):
        """Record a performance metric and check against SLA threshold."""
        metric = SLAMetric(
            metric_type=metric_type,
            value_ms=value_ms,
            endpoint=endpoint,
            details=details,
            user_id=user_id,
        )
        db.session.add(metric)
        db.session.commit()

        # Audit the metric recording
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action='record_metric', category='system', entity_type='sla_metric',
                entity_id=metric.id, user_id=user_id,
                details=f'{metric_type}={value_ms:.1f}ms',
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Audit log failed for SLA metric')

        # Check SLA threshold
        threshold = SLAService._get_threshold(metric_type)
        if threshold and value_ms > threshold:
            SLAService._record_violation(metric_type, threshold, value_ms,
                                         endpoint, details)

        return metric

    @staticmethod
    def _get_threshold(metric_type):
        """Get the SLA threshold for a metric type."""
        config_key = f'SLA_{metric_type.upper()}_MS'
        threshold = current_app.config.get(config_key)
        if threshold:
            return float(threshold)

        # Convert SEARCH_SLA_SECONDS config to ms
        if metric_type == 'search_latency':
            sla_seconds = current_app.config.get('SEARCH_SLA_SECONDS', 2)
            return float(sla_seconds) * 1000

        return DEFAULT_THRESHOLDS.get(metric_type)

    @staticmethod
    def _record_violation(metric_type, threshold_ms, actual_ms, endpoint=None, details=None):
        severity = 'critical' if actual_ms > threshold_ms * 2 else 'warning'

        violation = SLAViolation(
            metric_type=metric_type,
            threshold_ms=threshold_ms,
            actual_ms=actual_ms,
            endpoint=endpoint,
            details=details,
            severity=severity,
        )
        db.session.add(violation)
        db.session.commit()
        return violation

    @staticmethod
    def get_violations(metric_type=None, acknowledged=None, severity=None,
                       limit=50):
        q = select(SLAViolation)
        if metric_type:
            q = q.where(SLAViolation.metric_type == metric_type)
        if acknowledged is not None:
            q = q.where(SLAViolation.is_acknowledged == acknowledged)
        if severity:
            q = q.where(SLAViolation.severity == severity)
        q = q.order_by(SLAViolation.created_at.desc()).limit(limit)
        return db.session.execute(q).scalars().all()

    @staticmethod
    def acknowledge_violation(violation_id, user_id=None):
        v = db.session.get(SLAViolation, violation_id)
        if not v:
            return False, 'Violation not found.'
        v.is_acknowledged = True
        v.acknowledged_by = user_id
        v.acknowledged_at = datetime.utcnow()
        db.session.commit()
        return True, None

    @staticmethod
    def get_dashboard_stats(days=7):
        """Get SLA metrics summary for the admin dashboard."""
        since = datetime.utcnow() - timedelta(days=days)

        # Overall metrics by type
        metrics_summary = db.session.execute(
            select(
                SLAMetric.metric_type,
                func.count(SLAMetric.id).label('count'),
                func.avg(SLAMetric.value_ms).label('avg_ms'),
                func.min(SLAMetric.value_ms).label('min_ms'),
                func.max(SLAMetric.value_ms).label('max_ms'),
            )
            .where(SLAMetric.created_at >= since)
            .group_by(SLAMetric.metric_type)
        ).all()

        summary = []
        for row in metrics_summary:
            metric_type = row[0]
            total = row[1]
            threshold = SLAService._get_threshold(metric_type) or DEFAULT_THRESHOLDS.get(metric_type, 2000)

            # Count within-SLA using the configured threshold
            within_sla = db.session.execute(
                select(func.count(SLAMetric.id))
                .where(
                    SLAMetric.metric_type == metric_type,
                    SLAMetric.created_at >= since,
                    SLAMetric.value_ms <= threshold,
                )
            ).scalar() or 0

            compliance = (within_sla / total * 100) if total > 0 else 100.0

            summary.append({
                'metric_type': metric_type,
                'count': total,
                'avg_ms': round(row[2] or 0, 1),
                'min_ms': round(row[3] or 0, 1),
                'max_ms': round(row[4] or 0, 1),
                'within_sla': within_sla,
                'compliance_pct': round(compliance, 1),
                'threshold_ms': threshold,
            })

        # Violation counts
        violation_count = db.session.execute(
            select(func.count(SLAViolation.id))
            .where(SLAViolation.created_at >= since)
        ).scalar()

        unacknowledged = db.session.execute(
            select(func.count(SLAViolation.id))
            .where(
                SLAViolation.created_at >= since,
                SLAViolation.is_acknowledged == False,  # noqa: E712
            )
        ).scalar()

        # Recent latency trend (hourly averages for last 24h)
        since_24h = datetime.utcnow() - timedelta(hours=24)
        hourly = db.session.execute(
            select(
                func.strftime('%Y-%m-%d %H:00', SLAMetric.created_at).label('hour'),
                func.avg(SLAMetric.value_ms).label('avg_ms'),
                func.count(SLAMetric.id).label('count'),
            )
            .where(
                SLAMetric.created_at >= since_24h,
                SLAMetric.metric_type == 'search_latency',
            )
            .group_by(func.strftime('%Y-%m-%d %H:00', SLAMetric.created_at))
            .order_by(func.strftime('%Y-%m-%d %H:00', SLAMetric.created_at))
        ).all()

        trend = [{'hour': r[0], 'avg_ms': round(r[1], 1), 'count': r[2]} for r in hourly]

        return {
            'summary': summary,
            'violation_count': violation_count,
            'unacknowledged': unacknowledged,
            'trend': trend,
        }
