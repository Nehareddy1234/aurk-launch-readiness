from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey

class CustomerEmail(db.Model):
    __tablename__ = "customer_emails"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    event_key = db.Column(db.String(100), nullable=False, unique=True)
    kind = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="CASCADE"))
    interest_id = db.Column(db.BigInteger, db.ForeignKey("product_interests.id", ondelete="SET NULL"))
    recipient = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    # Existing MySQL DATETIME columns have second precision and round fractional
    # timestamps. Floor a new event's due time so immediate dispatch sees it.
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    submitted_at = db.Column(db.DateTime(timezone=True))
    last_error = db.Column(db.String(200))
    customer = db.relationship("User")
    order = db.relationship("Order")
    interest = db.relationship("ProductInterest")
    __table_args__ = (db.CheckConstraint("kind IN ('welcome','order_received','order_confirmed','order_shipped','order_delivered','order_cancelled','notify_interest','product_available')", name="ck_customer_email_kind"),
        db.CheckConstraint("status IN ('pending','failed','submitted','skipped')", name="ck_customer_email_status"))
