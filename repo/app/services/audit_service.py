import json
from datetime import datetime, timedelta

from flask import current_app, request as flask_request
from sqlalchemy import select, func, or_

from app.extensions import db
from app.models.audit import AuditLog, AnomalyAlert


class AuditService:

    @staticmethod
    def log(action, category, entity_type=None, entity_id=None,
            user_id=None, username=None, details=None, ip_address=None):
        """Create an audit log entry and check for anomalies."""
        if ip_address is None:
            try:
                ip_address = flask_request.remote_addr
            except RuntimeError:
                ip_address = None

        if isinstance(details, dict):
            details = json.dumps(details)

        # Always resolve username from user_id when absent
        if user_id and not username:
            try:
                from app.models.user import User
                user = db.session.get(User, user_id)
                if user:
                    username = user.username
            except Exception:
                pass

        entry = AuditLog(
            action=action,
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            username=username,
            details=details,
            ip_address=ip_address,
        )
        db.session.add(entry)
        db.session.commit()

        # Check for anomalies after logging
        if user_id and category in ('member', 'search'):
            AuditService._check_read_anomaly(user_id, username)

        return entry

    @staticmethod
    def _check_read_anomaly(user_id, username=None):
        """Detect if a user has exceeded the read threshold."""
        threshold = current_app.config.get('ANOMALY_READ_THRESHOLD', 50)
        window_minutes = current_app.config.get('ANOMALY_READ_WINDOW_MINUTES', 10)
        since = datetime.utcnow() - timedelta(minutes=window_minutes)

        count = db.session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == user_id,
                AuditLog.action.in_(['read', 'list', 'search', 'view']),
                AuditLog.created_at >= since,
            )
        ).scalar()

        if count >= threshold:
            # Check if we already raised this alert recently (within the window)
            recent_alert = db.session.execute(
                select(AnomalyAlert).where(
                    AnomalyAlert.user_id == user_id,
                    AnomalyAlert.alert_type == 'excessive_reads',
                    AnomalyAlert.created_at >= since,
                )
            ).scalar_one_or_none()

            if not recent_alert:
                alert = AnomalyAlert(
                    alert_type='excessive_reads',
                    description=f'User "{username or user_id}" performed {count} read operations in {window_minutes} minutes (threshold: {threshold}).',
                    user_id=user_id,
                    severity='warning',
                )
                db.session.add(alert)

                # Mark the triggering log as anomaly
                db.session.execute(
                    AuditLog.__table__.update()
                    .where(
                        AuditLog.user_id == user_id,
                        AuditLog.created_at >= since,
                    )
                    .values(is_anomaly=True)
                )
                db.session.commit()

    @staticmethod
    def search_logs(query=None, category=None, action=None, user_id=None,
                    entity_type=None, anomalies_only=False,
                    date_from=None, date_to=None,
                    page=1, per_page=50):
        """Search audit logs with filters."""
        q = select(AuditLog)

        if query:
            pattern = f'%{query}%'
            q = q.where(
                or_(
                    AuditLog.action.ilike(pattern),
                    AuditLog.details.ilike(pattern),
                    AuditLog.username.ilike(pattern),
                    AuditLog.entity_type.ilike(pattern),
                )
            )

        if category:
            q = q.where(AuditLog.category == category)
        if action:
            q = q.where(AuditLog.action == action)
        if user_id:
            q = q.where(AuditLog.user_id == user_id)
        if entity_type:
            q = q.where(AuditLog.entity_type == entity_type)
        if anomalies_only:
            q = q.where(AuditLog.is_anomaly == True)  # noqa: E712
        if date_from:
            q = q.where(AuditLog.created_at >= date_from)
        if date_to:
            q = q.where(AuditLog.created_at <= date_to)

        # Count
        count_q = select(func.count()).select_from(q.subquery())
        total = db.session.execute(count_q).scalar()

        # Paginate
        q = q.order_by(AuditLog.created_at.desc())
        q = q.offset((page - 1) * per_page).limit(per_page)
        items = db.session.execute(q).scalars().all()

        from app.services.member_service import PaginatedResult
        return PaginatedResult(items, total, page, per_page)

    @staticmethod
    def get_alerts(resolved=None, limit=50):
        q = select(AnomalyAlert)
        if resolved is not None:
            q = q.where(AnomalyAlert.is_resolved == resolved)
        q = q.order_by(AnomalyAlert.created_at.desc()).limit(limit)
        return db.session.execute(q).scalars().all()

    @staticmethod
    def resolve_alert(alert_id, resolved_by=None):
        alert = db.session.get(AnomalyAlert, alert_id)
        if not alert:
            return False, 'Alert not found.'
        alert.is_resolved = True
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.utcnow()
        db.session.commit()
        return True, None

    @staticmethod
    def get_stats(days=7):
        """Get audit log statistics for the last N days."""
        since = datetime.utcnow() - timedelta(days=days)

        by_category = db.session.execute(
            select(AuditLog.category, func.count(AuditLog.id))
            .where(AuditLog.created_at >= since)
            .group_by(AuditLog.category)
            .order_by(func.count(AuditLog.id).desc())
        ).all()

        by_action = db.session.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.created_at >= since)
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(10)
        ).all()

        total = db.session.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at >= since)
        ).scalar()

        anomaly_count = db.session.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at >= since, AuditLog.is_anomaly == True)  # noqa: E712
        ).scalar()

        return {
            'total': total,
            'anomaly_count': anomaly_count,
            'by_category': [{'category': c, 'count': n} for c, n in by_category],
            'by_action': [{'action': a, 'count': n} for a, n in by_action],
        }
