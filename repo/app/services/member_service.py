from datetime import datetime

from sqlalchemy import select, or_, func

from app.extensions import db
from app.models.member import Member, Tag


class OptimisticLockError(Exception):
    pass


class PaginatedResult:
    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = (total + per_page - 1) // per_page if total > 0 else 1


class MemberService:

    @staticmethod
    def create(data, created_by=None, tag_names=None):
        """Create a new member with optional tags in a single atomic transaction."""
        member = Member(
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            email=data['email'].strip().lower(),
            phone=data.get('phone', '').strip() or None,
            membership_type=data.get('membership_type', 'basic'),
            status='pending',
            organization=data.get('organization', '').strip() or None,
            notes=data.get('notes', '').strip() or None,
            created_by=created_by,
            updated_by=created_by,
            version=1,
        )

        error = MemberService._validate(member)
        if error:
            return None, error

        existing = db.session.execute(
            select(Member).where(Member.email == member.email)
        ).scalar_one_or_none()
        if existing:
            return None, 'A member with this email already exists.'

        db.session.add(member)
        db.session.flush()  # assign ID without committing

        # Attach tags in the same transaction
        if tag_names:
            for tag_name in tag_names:
                tag_name = tag_name.strip().lower()
                if not tag_name:
                    continue
                tag = db.session.execute(
                    select(Tag).where(Tag.name == tag_name)
                ).scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                if tag not in member.tags:
                    member.tags.append(tag)

        db.session.commit()
        MemberService._audit('create', member, created_by)
        return member, None

    @staticmethod
    def update(member_id, data, updated_by=None, expected_version=None, tag_names=None):
        """Update a member with optimistic locking."""
        member = db.session.get(Member, member_id)
        if not member:
            return None, 'Member not found.'

        if member.is_archived:
            return None, 'Cannot update an archived member.'

        # Optimistic lock check
        if expected_version is not None and member.version != expected_version:
            raise OptimisticLockError(
                'This record was modified by another user. '
                'Please refresh and try again.'
            )

        # Check email uniqueness if changed
        new_email = data.get('email', member.email).strip().lower()
        if new_email != member.email:
            existing = db.session.execute(
                select(Member).where(Member.email == new_email, Member.id != member_id)
            ).scalar_one_or_none()
            if existing:
                return None, 'A member with this email already exists.'

        member.first_name = data.get('first_name', member.first_name).strip()
        member.last_name = data.get('last_name', member.last_name).strip()
        member.email = new_email
        member.phone = data.get('phone', member.phone)
        member.membership_type = data.get('membership_type', member.membership_type)
        member.organization = data.get('organization', member.organization)
        member.notes = data.get('notes', member.notes)
        member.updated_by = updated_by
        member.updated_at = datetime.utcnow()
        member.version += 1

        error = MemberService._validate(member)
        if error:
            db.session.rollback()
            return None, error

        # Sync tags atomically in the same transaction
        if tag_names is not None:
            new_set = {t.strip().lower() for t in tag_names if t.strip()}
            current_set = {t.name for t in member.tags}
            for t_name in new_set - current_set:
                tag = db.session.execute(
                    select(Tag).where(Tag.name == t_name)
                ).scalar_one_or_none()
                if not tag:
                    tag = Tag(name=t_name)
                    db.session.add(tag)
                member.tags.append(tag)
            for t_name in current_set - new_set:
                tag = db.session.execute(
                    select(Tag).where(Tag.name == t_name)
                ).scalar_one_or_none()
                if tag and tag in member.tags:
                    member.tags.remove(tag)

        db.session.commit()
        MemberService._audit('update', member, updated_by)
        return member, None

    @staticmethod
    def get(member_id):
        return db.session.get(Member, member_id)

    @staticmethod
    def delete(member_id, deleted_by=None):
        """Soft-delete (archive) a member."""
        member = db.session.get(Member, member_id)
        if not member:
            return False, 'Member not found.'

        member.is_archived = True
        member.status = 'cancelled'
        member.updated_by = deleted_by
        member.updated_at = datetime.utcnow()
        member.version += 1
        db.session.commit()
        MemberService._audit('archive', member, deleted_by)
        return True, None

    @staticmethod
    def restore(member_id, restored_by=None):
        member = db.session.get(Member, member_id)
        if not member:
            return False, 'Member not found.'

        member.is_archived = False
        member.status = 'inactive'
        member.updated_by = restored_by
        member.updated_at = datetime.utcnow()
        member.version += 1
        db.session.commit()
        MemberService._audit('restore', member, restored_by)
        return True, None

    @staticmethod
    def list_members(page=1, per_page=20, search=None, status=None,
                     membership_type=None, tag_name=None, include_archived=False):
        """List members with filtering and pagination."""
        query = select(Member)

        if not include_archived:
            query = query.where(Member.is_archived == False)  # noqa: E712

        if status:
            query = query.where(Member.status == status)

        if membership_type:
            query = query.where(Member.membership_type == membership_type)

        if search:
            pattern = f'%{search}%'
            query = query.where(
                or_(
                    Member.first_name.ilike(pattern),
                    Member.last_name.ilike(pattern),
                    Member.email.ilike(pattern),
                    Member.organization.ilike(pattern),
                )
            )

        if tag_name:
            query = query.join(Member.tags).where(Tag.name == tag_name)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = db.session.execute(count_query).scalar()

        # Paginate
        query = query.order_by(Member.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        members = db.session.execute(query).scalars().all()

        return PaginatedResult(members, total, page, per_page)

    # --- Tag Management ---

    @staticmethod
    def add_tag(member_id, tag_name):
        member = db.session.get(Member, member_id)
        if not member:
            return False, 'Member not found.'

        tag = db.session.execute(
            select(Tag).where(Tag.name == tag_name)
        ).scalar_one_or_none()

        if not tag:
            tag = Tag(name=tag_name.strip().lower())
            db.session.add(tag)

        if tag not in member.tags:
            member.tags.append(tag)
            db.session.commit()
            MemberService._audit('add_tag', member, details=f'Tag: {tag_name}')

        return True, None

    @staticmethod
    def remove_tag(member_id, tag_name):
        member = db.session.get(Member, member_id)
        if not member:
            return False, 'Member not found.'

        tag = db.session.execute(
            select(Tag).where(Tag.name == tag_name)
        ).scalar_one_or_none()

        if tag and tag in member.tags:
            member.tags.remove(tag)
            db.session.commit()
            MemberService._audit('remove_tag', member, details=f'Tag: {tag_name}')

        return True, None

    @staticmethod
    def get_all_tags():
        return db.session.execute(
            select(Tag).order_by(Tag.name)
        ).scalars().all()

    @staticmethod
    def create_tag(name, color='#6c757d'):
        existing = db.session.execute(
            select(Tag).where(Tag.name == name.strip().lower())
        ).scalar_one_or_none()
        if existing:
            return existing, None

        tag = Tag(name=name.strip().lower(), color=color)
        db.session.add(tag)
        db.session.commit()
        return tag, None

    # --- Validation ---

    @staticmethod
    def _validate(member):
        if not member.first_name or not member.first_name.strip():
            return 'First name is required.'
        if not member.last_name or not member.last_name.strip():
            return 'Last name is required.'
        if not member.email or not member.email.strip():
            return 'Email is required.'
        if '@' not in member.email:
            return 'Invalid email address.'
        if member.membership_type not in Member.VALID_TYPES:
            return f'Invalid membership type. Must be one of: {", ".join(Member.VALID_TYPES)}'
        if member.status not in Member.VALID_STATUSES:
            return f'Invalid status. Must be one of: {", ".join(Member.VALID_STATUSES)}'
        return None

    @staticmethod
    def _audit(action, member, user_id=None, details=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action,
                category='member',
                entity_type='member',
                entity_id=member.id,
                user_id=user_id,
                details=details or f'{member.full_name} ({member.email})',
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'Audit log failed for member action=%s member_id=%s', action, member.id,
            )
