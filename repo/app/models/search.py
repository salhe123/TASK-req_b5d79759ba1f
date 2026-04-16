from datetime import datetime
from app.extensions import db


class SearchLog(db.Model):
    __tablename__ = 'search_logs'

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(500), nullable=False, index=True)
    results_count = db.Column(db.Integer, default=0)
    filters = db.Column(db.Text, nullable=True)  # JSON string of applied filters
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    latency_ms = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='search_logs')

    def __repr__(self):
        return f'<SearchLog "{self.query}" ({self.results_count} results)>'


def init_fts(app):
    """Create FTS5 virtual table and triggers for member search."""
    with app.app_context():
        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        # Standalone FTS5 table (not content-synced — we manage it via triggers)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS members_fts USING fts5(
                first_name,
                last_name,
                email,
                phone,
                organization,
                notes,
                membership_type,
                status,
                tokenize='porter unicode61'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS members_fts_ai AFTER INSERT ON members BEGIN
                INSERT INTO members_fts(rowid, first_name, last_name, email,
                    phone, organization, notes, membership_type, status)
                VALUES (new.id, new.first_name, new.last_name, new.email,
                    new.phone, new.organization, new.notes, new.membership_type, new.status);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS members_fts_ad AFTER DELETE ON members BEGIN
                DELETE FROM members_fts WHERE rowid = old.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS members_fts_au AFTER UPDATE ON members BEGIN
                DELETE FROM members_fts WHERE rowid = old.id;
                INSERT INTO members_fts(rowid, first_name, last_name, email,
                    phone, organization, notes, membership_type, status)
                VALUES (new.id, new.first_name, new.last_name, new.email,
                    new.phone, new.organization, new.notes, new.membership_type, new.status);
            END
        """)

        conn.commit()
        conn.close()


def rebuild_fts_index(app):
    """Rebuild the FTS index from existing member data."""
    with app.app_context():
        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM members_fts")
        cursor.execute("""
            INSERT INTO members_fts(rowid, first_name, last_name, email,
                phone, organization, notes, membership_type, status)
            SELECT id, first_name, last_name, email,
                phone, organization, notes, membership_type, status
            FROM members
        """)

        conn.commit()
        conn.close()
