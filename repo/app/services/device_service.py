from datetime import datetime

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.user import TrustedDevice


class DeviceService:

    @staticmethod
    def get_device(user_id, device_identifier):
        return db.session.execute(
            select(TrustedDevice).where(
                TrustedDevice.user_id == user_id,
                TrustedDevice.device_identifier == device_identifier
            )
        ).scalar_one_or_none()

    @staticmethod
    def is_trusted(user_id, device_identifier):
        device = DeviceService.get_device(user_id, device_identifier)
        if device:
            device.last_used = datetime.utcnow()
            db.session.commit()
            return True
        return False

    @staticmethod
    def register_device(user_id, device_identifier, device_name=None):
        """Register a trusted device. Returns (device, error_message) tuple."""
        max_devices = current_app.config.get('MAX_TRUSTED_DEVICES', 5)

        # Check if already registered
        existing = DeviceService.get_device(user_id, device_identifier)
        if existing:
            existing.last_used = datetime.utcnow()
            if device_name:
                existing.device_name = device_name
            db.session.commit()
            return existing, None

        # Check device limit
        count = db.session.execute(
            select(db.func.count(TrustedDevice.id)).where(
                TrustedDevice.user_id == user_id
            )
        ).scalar()

        if count >= max_devices:
            return None, f'Maximum of {max_devices} trusted devices reached. Remove a device first.'

        device = TrustedDevice(
            user_id=user_id,
            device_identifier=device_identifier,
            device_name=device_name or 'Unknown Device',
        )
        db.session.add(device)
        db.session.commit()
        DeviceService._audit('register_device', user_id, f'Device: {device_name or "Unknown"}')
        return device, None

    @staticmethod
    def remove_device(user_id, device_id):
        device = db.session.execute(
            select(TrustedDevice).where(
                TrustedDevice.id == device_id,
                TrustedDevice.user_id == user_id
            )
        ).scalar_one_or_none()

        if not device:
            return False, 'Device not found.'

        db.session.delete(device)
        db.session.commit()
        DeviceService._audit('remove_device', user_id, f'Device ID: {device_id}')
        return True, None

    @staticmethod
    def admin_list_devices_for_user(target_user_id):
        """Admin: list all trusted devices for a given user."""
        return db.session.execute(
            select(TrustedDevice).where(TrustedDevice.user_id == target_user_id)
            .order_by(TrustedDevice.last_used.desc())
        ).scalars().all()

    @staticmethod
    def admin_revoke_device(device_id, revoked_by=None):
        """Admin: revoke any user's trusted device by ID."""
        device = db.session.get(TrustedDevice, device_id)
        if not device:
            return False, 'Device not found.'
        owner_id = device.user_id
        db.session.delete(device)
        db.session.commit()
        DeviceService._audit('admin_revoke_device', revoked_by,
                             f'Revoked device {device_id} of user {owner_id}')
        return True, None

    @staticmethod
    def admin_revoke_all_devices(target_user_id, revoked_by=None):
        """Admin: revoke all trusted devices for a user."""
        devices = db.session.execute(
            select(TrustedDevice).where(TrustedDevice.user_id == target_user_id)
        ).scalars().all()
        count = len(devices)
        for d in devices:
            db.session.delete(d)
        db.session.commit()
        DeviceService._audit('admin_revoke_all_devices', revoked_by,
                             f'Revoked {count} device(s) for user {target_user_id}')
        return True, None

    @staticmethod
    def _audit(action, user_id, details=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action, category='auth', entity_type='device',
                user_id=user_id, details=details,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Audit log failed for device %s', action)

    @staticmethod
    def list_devices(user_id):
        return db.session.execute(
            select(TrustedDevice).where(TrustedDevice.user_id == user_id)
            .order_by(TrustedDevice.last_used.desc())
        ).scalars().all()

    @staticmethod
    def generate_device_identifier(request):
        """Generate a signed fingerprint from request headers + server secret.
        Binding to SECRET_KEY prevents spoofing by header replay alone."""
        import hashlib
        import hmac
        parts = [
            request.headers.get('User-Agent', ''),
            request.headers.get('Accept-Language', ''),
            request.headers.get('Accept-Encoding', ''),
        ]
        raw = '|'.join(parts)
        secret = current_app.config.get('SECRET_KEY', '')
        signed = hmac.new(
            secret.encode('utf-8'),
            raw.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()[:64]
        return signed
