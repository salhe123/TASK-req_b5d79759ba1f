from datetime import datetime
import math

from sqlalchemy import select

from app.extensions import db
from app.models.address import Address, SiteAddress, ServiceArea, EligibilityLog
from app.models.member import Member


class AddressService:

    @staticmethod
    def create(member_id, data, user_id=None, username=None):
        """Create an address for a member. Returns (address, error)."""
        member = db.session.get(Member, member_id)
        if not member:
            return None, 'Member not found.'

        error = AddressService._validate(data)
        if error:
            return None, error

        # If marking as primary, unset others
        if data.get('is_primary'):
            AddressService._clear_primary(member_id)

        address = Address(
            member_id=member_id,
            label=data.get('label', 'primary').strip(),
            street=data['street'].strip(),
            city=data['city'].strip(),
            state=data['state'].strip(),
            zip_code=data['zip_code'].strip(),
            country=data.get('country', 'US').strip(),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            region=data.get('region', '').strip() or None,
            is_primary=bool(data.get('is_primary', False)),
        )
        db.session.add(address)
        db.session.commit()
        AddressService._audit('create', 'address', address.id,
                              f'{address.street}, {address.city}',
                              user_id=user_id, username=username)
        return address, None

    @staticmethod
    def update(address_id, data, expected_version=None, user_id=None, username=None):
        address = db.session.get(Address, address_id)
        if not address:
            return None, 'Address not found.'

        if expected_version is not None and address.version != expected_version:
            return None, 'This address was modified by another user. Please refresh and try again.'

        error = AddressService._validate(data)
        if error:
            return None, error

        if data.get('is_primary') and not address.is_primary:
            AddressService._clear_primary(address.member_id)

        address.label = data.get('label', address.label).strip()
        address.street = data.get('street', address.street).strip()
        address.city = data.get('city', address.city).strip()
        address.state = data.get('state', address.state).strip()
        address.zip_code = data.get('zip_code', address.zip_code).strip()
        address.country = data.get('country', address.country).strip()
        address.latitude = data.get('latitude', address.latitude)
        address.longitude = data.get('longitude', address.longitude)
        address.region = data.get('region', address.region)
        address.is_primary = bool(data.get('is_primary', address.is_primary))
        address.version += 1
        address.updated_at = datetime.utcnow()

        db.session.commit()
        AddressService._audit('update', 'address', address.id,
                              f'{address.street}, {address.city}',
                              user_id=user_id, username=username)
        return address, None

    @staticmethod
    def delete(address_id, user_id=None, username=None):
        address = db.session.get(Address, address_id)
        if not address:
            return False, 'Address not found.'
        details = f'{address.street}, {address.city}'
        db.session.delete(address)
        db.session.commit()
        AddressService._audit('delete', 'address', address_id, details,
                              user_id=user_id, username=username)
        return True, None

    @staticmethod
    def get(address_id):
        return db.session.get(Address, address_id)

    @staticmethod
    def list_by_member(member_id):
        return db.session.execute(
            select(Address).where(Address.member_id == member_id)
            .order_by(Address.is_primary.desc(), Address.created_at.desc())
        ).scalars().all()

    @staticmethod
    def _clear_primary(member_id):
        addresses = db.session.execute(
            select(Address).where(Address.member_id == member_id, Address.is_primary == True)  # noqa: E712
        ).scalars().all()
        for a in addresses:
            a.is_primary = False

    @staticmethod
    def _validate(data):
        if not data.get('street', '').strip():
            return 'Street is required.'
        if not data.get('city', '').strip():
            return 'City is required.'
        if not data.get('state', '').strip():
            return 'State is required.'
        if not data.get('zip_code', '').strip():
            return 'ZIP code is required.'
        lat = data.get('latitude')
        lng = data.get('longitude')
        if lat is not None and (lat < -90 or lat > 90):
            return 'Latitude must be between -90 and 90.'
        if lng is not None and (lng < -180 or lng > 180):
            return 'Longitude must be between -180 and 180.'
        return None

    @staticmethod
    def _audit(action, entity_type, entity_id, details=None, user_id=None, username=None):
        try:
            from app.services.audit_service import AuditService
            AuditService.log(
                action=action,
                category='member',
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                username=username,
                details=details,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Audit log failed for %s %s %s', action, entity_type, entity_id)


class SiteAddressService:
    """CRUD for the site address book — shared facility/location addresses."""

    @staticmethod
    def create(data, user_id=None, username=None):
        error = AddressService._validate(data)
        if error:
            return None, error
        if not data.get('name', '').strip():
            return None, 'Site name is required.'
        site = SiteAddress(
            name=data['name'].strip(),
            street=data['street'].strip(),
            city=data['city'].strip(),
            state=data['state'].strip(),
            zip_code=data['zip_code'].strip(),
            country=data.get('country', 'US').strip(),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            region=data.get('region', '').strip() or None,
            is_active=data.get('is_active', True),
            created_by=user_id,
        )
        db.session.add(site)
        db.session.commit()
        AddressService._audit('create', 'site_address', site.id,
                              f'{site.name}: {site.street}, {site.city}',
                              user_id=user_id, username=username)
        return site, None

    @staticmethod
    def update(site_id, data, expected_version=None, user_id=None, username=None):
        site = db.session.get(SiteAddress, site_id)
        if not site:
            return None, 'Site address not found.'
        if expected_version is not None and site.version != expected_version:
            return None, 'This site address was modified by another user. Please refresh and try again.'
        error = AddressService._validate(data)
        if error:
            return None, error
        site.name = data.get('name', site.name).strip()
        site.street = data.get('street', site.street).strip()
        site.city = data.get('city', site.city).strip()
        site.state = data.get('state', site.state).strip()
        site.zip_code = data.get('zip_code', site.zip_code).strip()
        site.country = data.get('country', site.country).strip()
        site.latitude = data.get('latitude', site.latitude)
        site.longitude = data.get('longitude', site.longitude)
        site.region = data.get('region', site.region)
        site.is_active = data.get('is_active', site.is_active)
        site.version += 1
        site.updated_at = datetime.utcnow()
        db.session.commit()
        AddressService._audit('update', 'site_address', site.id,
                              f'{site.name}: {site.street}, {site.city}',
                              user_id=user_id, username=username)
        return site, None

    @staticmethod
    def delete(site_id, user_id=None, username=None):
        site = db.session.get(SiteAddress, site_id)
        if not site:
            return False, 'Site address not found.'
        name = site.name
        db.session.delete(site)
        db.session.commit()
        AddressService._audit('delete', 'site_address', site_id,
                              f'Site: {name}', user_id=user_id, username=username)
        return True, None

    @staticmethod
    def get(site_id):
        return db.session.get(SiteAddress, site_id)

    @staticmethod
    def list_all():
        return db.session.execute(
            select(SiteAddress).order_by(SiteAddress.name)
        ).scalars().all()

    @staticmethod
    def list_active():
        return db.session.execute(
            select(SiteAddress).where(SiteAddress.is_active == True)  # noqa: E712
            .order_by(SiteAddress.name)
        ).scalars().all()


class ServiceAreaService:

    VALID_AREA_TYPES = ('region', 'radius')

    @staticmethod
    def _validate_area(data):
        """Validate service area config. Returns error string or None."""
        area_type = data.get('area_type', 'region')
        if area_type not in ServiceAreaService.VALID_AREA_TYPES:
            return f'Invalid area type. Must be one of: {", ".join(ServiceAreaService.VALID_AREA_TYPES)}'
        if not data.get('name', '').strip():
            return 'Name is required.'
        if area_type == 'region' and not data.get('region', '').strip():
            return 'Region is required for region-based service areas.'
        if area_type == 'radius':
            if data.get('center_latitude') is None or data.get('center_longitude') is None:
                return 'Center latitude and longitude are required for radius-based service areas.'
            radius = data.get('radius_miles')
            if radius is not None and (radius <= 0 or radius > 10000):
                return 'Radius must be between 0 and 10,000 miles.'
        return None

    @staticmethod
    def create(data, user_id=None, username=None):
        error = ServiceAreaService._validate_area(data)
        if error:
            return None, error
        name = data['name'].strip()
        existing = db.session.execute(
            select(ServiceArea).where(ServiceArea.name == name)
        ).scalar_one_or_none()
        if existing:
            return None, 'Service area with this name already exists.'

        area = ServiceArea(
            name=name,
            area_type=data.get('area_type', 'region'),
            region=data.get('region', '').strip() or None,
            center_latitude=data.get('center_latitude'),
            center_longitude=data.get('center_longitude'),
            radius_miles=data.get('radius_miles', 25.0),
            is_active=data.get('is_active', True),
        )
        db.session.add(area)
        db.session.commit()
        AddressService._audit('create', 'service_area', area.id,
                              f'Service area: {area.name}',
                              user_id=user_id, username=username)
        return area, None

    @staticmethod
    def get(area_id):
        return db.session.get(ServiceArea, area_id)

    @staticmethod
    def list_active():
        return db.session.execute(
            select(ServiceArea).where(ServiceArea.is_active == True)  # noqa: E712
            .order_by(ServiceArea.name)
        ).scalars().all()

    @staticmethod
    def list_all():
        return db.session.execute(
            select(ServiceArea).order_by(ServiceArea.name)
        ).scalars().all()

    @staticmethod
    def update(area_id, data, expected_version=None, user_id=None, username=None):
        area = db.session.get(ServiceArea, area_id)
        if not area:
            return None, 'Service area not found.'

        if expected_version is not None and area.version != expected_version:
            return None, 'This service area was modified by another user. Please refresh and try again.'

        error = ServiceAreaService._validate_area(data)
        if error:
            return None, error

        area.name = data.get('name', area.name).strip()
        area.area_type = data.get('area_type', area.area_type)
        area.region = data.get('region', area.region)
        area.center_latitude = data.get('center_latitude', area.center_latitude)
        area.center_longitude = data.get('center_longitude', area.center_longitude)
        area.radius_miles = data.get('radius_miles', area.radius_miles)
        area.is_active = data.get('is_active', area.is_active)
        area.version += 1
        area.updated_at = datetime.utcnow()
        db.session.commit()
        AddressService._audit('update', 'service_area', area.id,
                              f'Service area: {area.name}',
                              user_id=user_id, username=username)
        return area, None

    @staticmethod
    def delete(area_id, user_id=None, username=None):
        area = db.session.get(ServiceArea, area_id)
        if not area:
            return False, 'Service area not found.'
        name = area.name
        db.session.delete(area)
        db.session.commit()
        AddressService._audit('delete', 'service_area', area_id,
                              f'Service area: {name}',
                              user_id=user_id, username=username)
        return True, None


class EligibilityService:

    @staticmethod
    def check_eligibility(member_id, address_id=None, checked_by=None):
        """Check if a member's address falls within any active service area.
        Returns (is_eligible, reason, log_entry)."""
        member = db.session.get(Member, member_id)
        if not member:
            return False, 'Member not found.', None

        if member.status not in ('active', 'pending'):
            reason = f'Member status "{member.status}" is not eligible for service.'
            log = EligibilityService._log(member_id, address_id, None, False, reason, checked_by)
            return False, reason, log

        # Get address
        address = None
        if address_id:
            address = db.session.get(Address, address_id)
            if address and address.member_id != member_id:
                reason = 'Address does not belong to this member.'
                log = EligibilityService._log(member_id, address_id, None, False, reason, checked_by)
                return False, reason, log
        else:
            # Use primary address
            address = db.session.execute(
                select(Address).where(
                    Address.member_id == member_id,
                    Address.is_primary == True  # noqa: E712
                )
            ).scalar_one_or_none()

        if not address:
            reason = 'No address found for eligibility check.'
            log = EligibilityService._log(member_id, None, None, False, reason, checked_by)
            return False, reason, log

        # Check against all active service areas
        service_areas = ServiceAreaService.list_active()
        if not service_areas:
            reason = 'No active service areas configured.'
            log = EligibilityService._log(member_id, address.id, None, False, reason, checked_by)
            return False, reason, log

        for area in service_areas:
            eligible, area_reason = EligibilityService._check_area(address, area)
            if eligible:
                reason = f'Eligible via service area "{area.name}": {area_reason}'
                log = EligibilityService._log(member_id, address.id, area.id, True, reason, checked_by)
                return True, reason, log

        reason = 'Address is not within any active service area.'
        log = EligibilityService._log(member_id, address.id, None, False, reason, checked_by)
        return False, reason, log

    @staticmethod
    def _check_area(address, area):
        """Check if address is within a service area. Returns (bool, reason)."""
        if area.area_type == 'region':
            if address.region and address.region.lower() == area.region.lower():
                return True, f'Region match: {area.region}'
            return False, f'Region mismatch: {address.region} != {area.region}'

        elif area.area_type == 'radius':
            if any(v is None for v in [address.latitude, address.longitude,
                                       area.center_latitude, area.center_longitude]):
                return False, 'Missing coordinates for radius check.'

            distance = EligibilityService._haversine(
                address.latitude, address.longitude,
                area.center_latitude, area.center_longitude
            )
            if distance <= area.radius_miles:
                return True, f'{distance:.1f} miles (within {area.radius_miles} mile radius)'
            return False, f'{distance:.1f} miles (exceeds {area.radius_miles} mile radius)'

        return False, f'Unknown area type: {area.area_type}'

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in miles between two lat/lng points."""
        R = 3958.8  # Earth's radius in miles
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    @staticmethod
    def _log(member_id, address_id, service_area_id, is_eligible, reason, checked_by):
        log = EligibilityLog(
            member_id=member_id,
            address_id=address_id,
            service_area_id=service_area_id,
            is_eligible=is_eligible,
            reason=reason,
            checked_by=checked_by,
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def get_logs(member_id=None, limit=50):
        query = select(EligibilityLog)
        if member_id:
            query = query.where(EligibilityLog.member_id == member_id)
        return db.session.execute(
            query.order_by(EligibilityLog.created_at.desc()).limit(limit)
        ).scalars().all()
