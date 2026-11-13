from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey
class Coupon(db.Model):
    __tablename__ = "coupons"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(20), nullable=False)
    value = db.Column(db.Numeric(12,2), nullable=False)
    minimum_order = db.Column(db.Numeric(12,2), nullable=False, default=0)
    maximum_discount = db.Column(db.Numeric(12,2))
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    usage_limit = db.Column(db.Integer)
    per_user_limit = db.Column(db.Integer, default=1)
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

class CouponUsage(db.Model):
    __tablename__ = "coupon_usages"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    coupon_id = db.Column(db.BigInteger, db.ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (db.Index("ix_coupon_user", "coupon_id", "user_id"),)
