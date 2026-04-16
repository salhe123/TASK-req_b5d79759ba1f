from datetime import datetime
from app.extensions import db


member_tags = db.Table(
    'member_tags',
    db.Column('member_id', db.Integer, db.ForeignKey('members.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
)


class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    membership_type = db.Column(db.String(50), nullable=False, default='basic')
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    organization = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    is_archived = db.Column(db.Boolean, default=False, index=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tags = db.relationship('Tag', secondary=member_tags, backref=db.backref('members', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_members')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='updated_members')

    VALID_STATUSES = ['pending', 'active', 'inactive', 'suspended', 'cancelled']
    VALID_TYPES = ['basic', 'standard', 'premium', 'enterprise']

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Member {self.full_name} ({self.status})>'


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Tag {self.name}>'
