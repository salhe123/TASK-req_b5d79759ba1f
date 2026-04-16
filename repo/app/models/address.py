from datetime import datetime
from app.extensions import db


class Address(db.Model):
    __tablename__ = 'addresses'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    label = db.Column(db.String(50), default='primary')  # primary, billing, service, etc.
    street = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(50), default='US')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    region = db.Column(db.String(50), nullable=True, index=True)
    is_primary = db.Column(db.Boolean, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = db.relationship('Member', backref=db.backref('addresses', lazy='dynamic',
                             cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Address {self.street}, {self.city} ({self.label})>'


class SiteAddress(db.Model):
    """Site address book — shared/facility addresses not bound to a single member.
    Used for dispatch eligibility checks against known service locations."""
    __tablename__ = 'site_addresses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    street = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(50), default='US')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    region = db.Column(db.String(50), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', backref='site_addresses')

    def __repr__(self):
        return f'<SiteAddress {self.name}: {self.street}, {self.city}>'


class ServiceArea(db.Model):
    __tablename__ = 'service_areas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    area_type = db.Column(db.String(20), nullable=False, default='region')  # region or radius
    # For region-based
    region = db.Column(db.String(50), nullable=True, index=True)
    # For radius-based
    center_latitude = db.Column(db.Float, nullable=True)
    center_longitude = db.Column(db.Float, nullable=True)
    radius_miles = db.Column(db.Float, nullable=True, default=25.0)
    is_active = db.Column(db.Boolean, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ServiceArea {self.name} ({self.area_type})>'


class EligibilityLog(db.Model):
    __tablename__ = 'eligibility_logs'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    address_id = db.Column(db.Integer, db.ForeignKey('addresses.id'), nullable=True)
    service_area_id = db.Column(db.Integer, db.ForeignKey('service_areas.id'), nullable=True)
    is_eligible = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship('Member', backref=db.backref('eligibility_checks', lazy='dynamic'))
    address = db.relationship('Address')
    service_area = db.relationship('ServiceArea')
    checker = db.relationship('User', backref='eligibility_checks')

    def __repr__(self):
        return f'<EligibilityLog member={self.member_id} eligible={self.is_eligible}>'
