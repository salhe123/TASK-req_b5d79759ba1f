from datetime import datetime
from app.extensions import db


class CleansingTemplate(db.Model):
    __tablename__ = 'cleansing_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True)

    # JSON config fields
    field_mapping = db.Column(db.Text, nullable=True)        # {"csv_col": "member_field", ...}
    missing_value_rules = db.Column(db.Text, nullable=True)  # {"field": {"action": "default|skip|flag", "value": "..."}}
    dedup_fields = db.Column(db.Text, nullable=True)         # ["email"] or ["first_name", "last_name"]
    dedup_threshold = db.Column(db.Float, default=1.0)       # 1.0 = exact match, <1.0 = fuzzy
    format_rules = db.Column(db.Text, nullable=True)         # {"email": "lowercase", "phone": "digits_only", "name": "titlecase"}
    sensitive_fields = db.Column(db.Text, nullable=True)     # ["ssn", "tax_id", ...] — fields to mask in UI

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', backref='cleansing_templates')
    jobs = db.relationship('CleansingJob', backref='template', lazy='dynamic',
                           order_by='CleansingJob.created_at.desc()')

    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='uq_template_name_version'),
    )

    def __repr__(self):
        return f'<CleansingTemplate {self.name} v{self.version}>'


class CleansingJob(db.Model):
    __tablename__ = 'cleansing_jobs'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('cleansing_templates.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    # pending -> processing -> completed / failed

    total_rows = db.Column(db.Integer, default=0)
    processed_rows = db.Column(db.Integer, default=0)
    clean_rows = db.Column(db.Integer, default=0)
    flagged_rows = db.Column(db.Integer, default=0)
    duplicate_rows = db.Column(db.Integer, default=0)
    skipped_rows = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)

    # JSON results
    results = db.Column(db.Text, nullable=True)       # cleaned data as JSON
    flagged_data = db.Column(db.Text, nullable=True)   # rows that need review
    raw_data = db.Column(db.Text, nullable=True)       # original uploaded data

    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='cleansing_jobs')

    VALID_STATUSES = ['pending', 'processing', 'completed', 'failed']

    def __repr__(self):
        return f'<CleansingJob #{self.id} ({self.status})>'
