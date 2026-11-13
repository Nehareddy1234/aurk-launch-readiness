from app.extensions import db
from app.models.types import BigIntPrimaryKey


class AdminSession(db.Model):
    """Revocable elevated sessions for existing users, never a second user store."""
    __tablename__ = "admin_sessions"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    password_fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    last_seen_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
