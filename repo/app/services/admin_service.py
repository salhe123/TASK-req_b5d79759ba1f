from datetime import datetime, timedelta

from sqlalchemy import select, func

from app.extensions import db
from app.models.user import User
from app.models.member import Member
from app.models.audit import AuditLog, AnomalyAlert
from app.models.sla import SLAMetric, SLAViolation
from app.models.search import SearchLog
from app.models.cleansing import CleansingJob


class AdminService:

    VALID_ROLES = ['admin', 'manager', 'operator', 'viewer']

    @staticmethod
    def get_dashboard_data():
        """Aggregate all key metrics for the admin dashboard."""
        now = datetime.utcnow()
        last_7d = now - timedelta(days=7)
        last_24h = now - timedelta(hours=24)

        # --- Counts ---
        total_users = db.session.execute(
            select(func.count(User.id))
        ).scalar()

        active_users = db.session.execute(
            select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
        ).scalar()

        total_members = db.session.execute(
            select(func.count(Member.id)).where(Member.is_archived == False)  # noqa: E712
        ).scalar()

        members_by_status = db.session.execute(
            select(Member.status, func.count(Member.id))
            .where(Member.is_archived == False)  # noqa: E712
            .group_by(Member.status)
        ).all()

        members_by_type = db.session.execute(
            select(Member.membership_type, func.count(Member.id))
            .where(Member.is_archived == False)  # noqa: E712
            .group_by(Member.membership_type)
        ).all()

        new_members_7d = db.session.execute(
            select(func.count(Member.id))
            .where(Member.created_at >= last_7d, Member.is_archived == False)  # noqa: E712
        ).scalar()

        # --- Anomaly Alerts ---
        open_anomalies = db.session.execute(
            select(func.count(AnomalyAlert.id))
            .where(AnomalyAlert.is_resolved == False)  # noqa: E712
        ).scalar()

        recent_anomalies = db.session.execute(
            select(AnomalyAlert)
            .where(AnomalyAlert.is_resolved == False)  # noqa: E712
            .order_by(AnomalyAlert.created_at.desc())
            .limit(5)
        ).scalars().all()

        # --- SLA ---
        sla_violations_7d = db.session.execute(
            select(func.count(SLAViolation.id))
            .where(SLAViolation.created_at >= last_7d)
        ).scalar()

        open_violations = db.session.execute(
            select(func.count(SLAViolation.id))
            .where(SLAViolation.is_acknowledged == False)  # noqa: E712
        ).scalar()

        avg_search_latency = db.session.execute(
            select(func.avg(SLAMetric.value_ms))
            .where(
                SLAMetric.metric_type == 'search_latency',
                SLAMetric.created_at >= last_24h,
            )
        ).scalar()

        # --- Audit ---
        audit_events_24h = db.session.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at >= last_24h)
        ).scalar()

        recent_audit = db.session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        ).scalars().all()

        audit_by_category = db.session.execute(
            select(AuditLog.category, func.count(AuditLog.id))
            .where(AuditLog.created_at >= last_7d)
            .group_by(AuditLog.category)
            .order_by(func.count(AuditLog.id).desc())
        ).all()

        # --- Search ---
        total_searches_7d = db.session.execute(
            select(func.count(SearchLog.id))
            .where(SearchLog.created_at >= last_7d)
        ).scalar()

        # --- Cleansing ---
        recent_jobs = db.session.execute(
            select(CleansingJob)
            .order_by(CleansingJob.created_at.desc())
            .limit(5)
        ).scalars().all()

        # --- System health ---
        health_checks = []
        health_checks.append({
            'name': 'Database',
            'status': 'ok',
            'detail': 'SQLite connected',
        })
        health_checks.append({
            'name': 'Open Anomalies',
            'status': 'warning' if open_anomalies > 0 else 'ok',
            'detail': f'{open_anomalies} unresolved',
        })
        health_checks.append({
            'name': 'SLA Compliance',
            'status': 'warning' if open_violations > 0 else 'ok',
            'detail': f'{open_violations} open violations',
        })
        health_checks.append({
            'name': 'Avg Search Latency (24h)',
            'status': 'ok' if (avg_search_latency or 0) <= 2000 else 'warning',
            'detail': f'{avg_search_latency:.0f}ms' if avg_search_latency else 'No data',
        })

        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_members': total_members,
            'new_members_7d': new_members_7d,
            'members_by_status': [{'status': s, 'count': c} for s, c in members_by_status],
            'members_by_type': [{'type': t, 'count': c} for t, c in members_by_type],
            'open_anomalies': open_anomalies,
            'recent_anomalies': recent_anomalies,
            'sla_violations_7d': sla_violations_7d,
            'open_violations': open_violations,
            'avg_search_latency': round(avg_search_latency, 1) if avg_search_latency else None,
            'audit_events_24h': audit_events_24h,
            'recent_audit': recent_audit,
            'audit_by_category': [{'category': c, 'count': n} for c, n in audit_by_category],
            'total_searches_7d': total_searches_7d,
            'recent_jobs': recent_jobs,
            'health': health_checks,
        }

    # --- User Account Management ---

    @staticmethod
    def list_users():
        return db.session.execute(
            select(User).order_by(User.created_at.desc())
        ).scalars().all()

    @staticmethod
    def deactivate_user(user_id, performed_by=None):
        user = db.session.get(User, user_id)
        if not user:
            return False, 'User not found.'
        if not user.is_active:
            return False, 'User is already deactivated.'

        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()

        AdminService._audit('deactivate_user', user, performed_by)
        return True, None

    @staticmethod
    def activate_user(user_id, performed_by=None):
        user = db.session.get(User, user_id)
        if not user:
            return False, 'User not found.'
        if user.is_active:
            return False, 'User is already active.'

        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.session.commit()

        AdminService._audit('activate_user', user, performed_by)
        return True, None

    @staticmethod
    def freeze_user(user_id, performed_by=None):
        user = db.session.get(User, user_id)
        if not user:
            return False, 'User not found.'

        # Lock the account indefinitely (set far-future lock)
        user.locked_until = datetime.utcnow() + timedelta(days=365 * 100)
        user.updated_at = datetime.utcnow()
        db.session.commit()

        AdminService._audit('freeze_user', user, performed_by)
        return True, None

    @staticmethod
    def unfreeze_user(user_id, performed_by=None):
        user = db.session.get(User, user_id)
        if not user:
            return False, 'User not found.'

        user.locked_until = None
        user.failed_login_attempts = 0
        user.updated_at = datetime.utcnow()
        db.session.commit()

        AdminService._audit('unfreeze_user', user, performed_by)
        return True, None

    @staticmethod
    def change_user_role(user_id, new_role, performed_by=None):
        if new_role not in AdminService.VALID_ROLES:
            return False, f'Invalid role. Must be one of: {", ".join(AdminService.VALID_ROLES)}'

        user = db.session.get(User, user_id)
        if not user:
            return False, 'User not found.'

        old_role = user.role
        user.role = new_role
        user.updated_at = datetime.utcnow()
        db.session.commit()

        AdminService._audit('change_role', user, performed_by,
                            details=f'{old_role} -> {new_role}')
        return True, None

    @staticmethod
    def _audit(action, user, performed_by=None, details=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action,
                category='system',
                entity_type='user',
                entity_id=user.id if user else None,
                user_id=performed_by,
                details=details or (f'User: {user.username}' if user else ''),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'Audit log failed for admin action=%s', action,
            )
