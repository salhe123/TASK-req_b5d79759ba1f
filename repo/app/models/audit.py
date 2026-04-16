from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)  # auth, member, workflow, eligibility, search, system
    entity_type = db.Column(db.String(50), nullable=True, index=True)  # user, member, address, etc.
    entity_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON string with additional context
    ip_address = db.Column(db.String(45), nullable=True)
    is_anomaly = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'))

    CATEGORIES = ['auth', 'member', 'workflow', 'eligibility', 'search', 'system']

    def __repr__(self):
        return f'<AuditLog {self.category}:{self.action} by {self.username}>'


class AnomalyAlert(db.Model):
    __tablename__ = 'anomaly_alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='anomaly_alerts')
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        return f'<AnomalyAlert {self.alert_type} ({self.severity})>'
