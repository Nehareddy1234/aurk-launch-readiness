from datetime import datetime, timezone
from decimal import Decimal
from app.models import Coupon, CouponUsage

def validate_coupon(code, user_id, subtotal):
    coupon = Coupon.query.filter_by(code=code.strip().upper(), is_active=True).first()
    if not coupon: raise ValueError("Invalid coupon.")
    now = datetime.now(timezone.utc)
    if now < coupon.starts_at or now > coupon.expires_at: raise ValueError("Coupon is expired or not active yet.")
    if subtotal < coupon.minimum_order: raise ValueError("Minimum order value not met.")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit: raise ValueError("Coupon usage limit reached.")
    used = CouponUsage.query.filter_by(coupon_id=coupon.id, user_id=user_id).count()
    if coupon.per_user_limit is not None and used >= coupon.per_user_limit: raise ValueError("Coupon usage limit reached for this account.")
    if coupon.discount_type == "percentage": discount = subtotal * (coupon.value / Decimal("100"))
    elif coupon.discount_type == "fixed": discount = coupon.value
    else: raise ValueError("Invalid coupon configuration.")
    if coupon.maximum_discount is not None: discount = min(discount, coupon.maximum_discount)
    return min(discount, subtotal), coupon
