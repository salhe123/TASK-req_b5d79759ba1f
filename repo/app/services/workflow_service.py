from datetime import datetime

from app.extensions import db
from app.models.member import Member
from app.models.workflow import MemberTimeline


class InvalidTransitionError(Exception):
    pass


# State machine: action -> {allowed_from_statuses: to_status}
TRANSITION_MAP = {
    'JOIN': {
        'from': ['pending'],
        'to': 'active',
    },
    'RENEW': {
        'from': ['active', 'inactive'],
        'to': 'active',
    },
    'UPGRADE': {
        'from': ['active'],
        'to': 'active',  # status stays active, membership_type changes
    },
    'DOWNGRADE': {
        'from': ['active'],
        'to': 'active',  # status stays active, membership_type changes
    },
    'DEACTIVATE': {
        'from': ['active', 'suspended'],
        'to': 'inactive',
    },
    'REACTIVATE': {
        'from': ['inactive'],
        'to': 'active',
    },
    'CANCEL': {
        'from': ['active', 'inactive', 'suspended', 'pending'],
        'to': 'cancelled',
    },
}

# Membership type hierarchy for upgrade/downgrade validation
TYPE_HIERARCHY = {
    'basic': 0,
    'standard': 1,
    'premium': 2,
    'enterprise': 3,
}


class WorkflowService:

    @staticmethod
    def get_available_actions(member):
        """Return list of actions valid for the member's current state."""
        if member.is_archived:
            return []

        available = []
        for action, rule in TRANSITION_MAP.items():
            if member.status in rule['from']:
                # For UPGRADE/DOWNGRADE, check if there's a valid type to move to
                if action == 'UPGRADE':
                    current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)
                    if current_rank < max(TYPE_HIERARCHY.values()):
                        available.append(action)
                elif action == 'DOWNGRADE':
                    current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)
                    if current_rank > 0:
                        available.append(action)
                else:
                    available.append(action)
        return available

    @staticmethod
    def execute(member_id, action, performed_by=None, notes=None, new_membership_type=None):
        """Execute a workflow transition. Returns (member, timeline_entry) or raises InvalidTransitionError."""
        member = db.session.get(Member, member_id)
        if not member:
            raise InvalidTransitionError('Member not found.')

        if member.is_archived:
            raise InvalidTransitionError('Cannot perform actions on archived members.')

        action = action.upper()
        if action not in TRANSITION_MAP:
            raise InvalidTransitionError(f'Unknown action: {action}')

        rule = TRANSITION_MAP[action]

        if member.status not in rule['from']:
            raise InvalidTransitionError(
                f'Cannot {action} a member with status "{member.status}". '
                f'Allowed from: {", ".join(rule["from"])}.'
            )

        from_status = member.status
        from_type = member.membership_type
        to_type = from_type

        # Handle UPGRADE/DOWNGRADE type changes
        if action == 'UPGRADE':
            to_type = WorkflowService._get_upgrade_type(member, new_membership_type)
        elif action == 'DOWNGRADE':
            to_type = WorkflowService._get_downgrade_type(member, new_membership_type)

        # Apply the transition
        member.status = rule['to']
        if action in ('UPGRADE', 'DOWNGRADE'):
            member.membership_type = to_type
        member.updated_by = performed_by
        member.updated_at = datetime.utcnow()
        member.version += 1

        # Record timeline
        timeline = MemberTimeline(
            member_id=member_id,
            action=action,
            from_status=from_status,
            to_status=member.status,
            from_type=from_type,
            to_type=to_type,
            notes=notes,
            performed_by=performed_by,
        )
        db.session.add(timeline)
        db.session.commit()

        # Audit log
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action.lower(),
                category='workflow',
                entity_type='member',
                entity_id=member_id,
                user_id=performed_by,
                details=f'{from_status} -> {member.status}' + (f', {from_type} -> {to_type}' if from_type != to_type else ''),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'Audit log failed for workflow action=%s member_id=%s', action, member_id,
            )

        return member, timeline

    @staticmethod
    def get_timeline(member_id, limit=50):
        """Get timeline entries for a member, most recent first."""
        return MemberTimeline.query.filter_by(member_id=member_id)\
            .order_by(MemberTimeline.created_at.desc())\
            .limit(limit).all()

    @staticmethod
    def _get_upgrade_type(member, new_type=None):
        current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)

        if new_type:
            new_rank = TYPE_HIERARCHY.get(new_type)
            if new_rank is None:
                raise InvalidTransitionError(f'Invalid membership type: {new_type}')
            if new_rank <= current_rank:
                raise InvalidTransitionError(
                    f'Cannot upgrade from {member.membership_type} to {new_type}. '
                    f'New type must be higher.'
                )
            return new_type

        # Default: move to next tier
        for type_name, rank in sorted(TYPE_HIERARCHY.items(), key=lambda x: x[1]):
            if rank > current_rank:
                return type_name

        raise InvalidTransitionError('Already at highest membership tier.')

    @staticmethod
    def _get_downgrade_type(member, new_type=None):
        current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)

        if new_type:
            new_rank = TYPE_HIERARCHY.get(new_type)
            if new_rank is None:
                raise InvalidTransitionError(f'Invalid membership type: {new_type}')
            if new_rank >= current_rank:
                raise InvalidTransitionError(
                    f'Cannot downgrade from {member.membership_type} to {new_type}. '
                    f'New type must be lower.'
                )
            return new_type

        # Default: move to previous tier
        for type_name, rank in sorted(TYPE_HIERARCHY.items(), key=lambda x: x[1], reverse=True):
            if rank < current_rank:
                return type_name

        raise InvalidTransitionError('Already at lowest membership tier.')

    @staticmethod
    def get_type_options_for_upgrade(member):
        """Return membership types available for upgrade."""
        current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)
        return [t for t, r in sorted(TYPE_HIERARCHY.items(), key=lambda x: x[1]) if r > current_rank]

    @staticmethod
    def get_type_options_for_downgrade(member):
        """Return membership types available for downgrade."""
        current_rank = TYPE_HIERARCHY.get(member.membership_type, 0)
        return [t for t, r in sorted(TYPE_HIERARCHY.items(), key=lambda x: x[1]) if r < current_rank]
