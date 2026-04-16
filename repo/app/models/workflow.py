from datetime import datetime
from app.extensions import db


class MemberTimeline(db.Model):
    __tablename__ = 'member_timeline'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=False)
    from_type = db.Column(db.String(50), nullable=True)
    to_type = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    member = db.relationship('Member', backref=db.backref('timeline', lazy='dynamic',
                             order_by='MemberTimeline.created_at.desc()'))
    performer = db.relationship('User', backref='workflow_actions')

    VALID_ACTIONS = ['JOIN', 'RENEW', 'UPGRADE', 'DOWNGRADE', 'DEACTIVATE', 'REACTIVATE', 'CANCEL']

    def __repr__(self):
        return f'<Timeline {self.action}: {self.from_status} -> {self.to_status}>'
