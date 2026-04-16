from datetime import datetime
from app.extensions import db


class SLAMetric(db.Model):
    __tablename__ = 'sla_metrics'

    id = db.Column(db.Integer, primary_key=True)
    metric_type = db.Column(db.String(50), nullable=False, index=True)  # search_latency, api_response, etc.
    value_ms = db.Column(db.Float, nullable=False)
    endpoint = db.Column(db.String(200), nullable=True)
    details = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<SLAMetric {self.metric_type}: {self.value_ms:.1f}ms>'


class SLAViolation(db.Model):
    __tablename__ = 'sla_violations'

    id = db.Column(db.Integer, primary_key=True)
    metric_type = db.Column(db.String(50), nullable=False, index=True)
    threshold_ms = db.Column(db.Float, nullable=False)
    actual_ms = db.Column(db.Float, nullable=False)
    endpoint = db.Column(db.String(200), nullable=True)
    details = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), default='warning')  # warning, critical
    is_acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    acknowledger = db.relationship('User', backref='acknowledged_violations')

    def __repr__(self):
        return f'<SLAViolation {self.metric_type}: {self.actual_ms:.0f}ms > {self.threshold_ms:.0f}ms>'
