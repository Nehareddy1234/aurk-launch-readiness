from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey
class Address(db.Model):
    __tablename__ = "addresses"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(50))
    recipient_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    line1 = db.Column(db.String(255), nullable=False)
    line2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False, default="India")
    is_default = db.Column(db.Boolean, nullable=False, default=False)

class Cart(db.Model):
    __tablename__ = "carts"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    coupon_code = db.Column(db.String(100))
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    cart_id = db.Column(db.BigInteger, db.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    variant_id = db.Column(db.BigInteger, db.ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("cart_id", "variant_id", name="uq_cart_variant"),)
    cart = db.relationship("Cart", back_populates="items")
    variant = db.relationship("ProductVariant")

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="Pending", index=True)
    subtotal = db.Column(db.Numeric(12,2), nullable=False)
    discount = db.Column(db.Numeric(12,2), nullable=False, default=0)
    shipping = db.Column(db.Numeric(12,2), nullable=False, default=0)
    tax = db.Column(db.Numeric(12,2), nullable=False, default=0)
    total = db.Column(db.Numeric(12,2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    shipping_name = db.Column(db.String(200), nullable=False)
    shipping_phone = db.Column(db.String(30), nullable=False)
    shipping_line1 = db.Column(db.String(255), nullable=False)
    shipping_line2 = db.Column(db.String(255))
    shipping_city = db.Column(db.String(100), nullable=False)
    shipping_state = db.Column(db.String(100), nullable=False)
    shipping_postal_code = db.Column(db.String(20), nullable=False)
    shipping_country = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="order", cascade="all, delete-orphan")

    @property
    def status_label(self):
        from app.services.order_status import LABELS
        return LABELS.get(self.status, self.status)

    @property
    def status_message(self):
        from app.services.order_status import MESSAGES
        return MESSAGES.get(self.status, "Follow your order's progress here.")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    variant_id = db.Column(db.BigInteger, db.ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)
    product_name_snapshot = db.Column(db.String(255), nullable=False)
    sku_snapshot = db.Column(db.String(100), nullable=False)
    size_snapshot = db.Column(db.String(50), nullable=False)
    color_snapshot = db.Column(db.String(80), nullable=False)
    unit_price = db.Column(db.Numeric(12,2), nullable=False)
    discount = db.Column(db.Numeric(12,2), nullable=False, default=0)
    tax = db.Column(db.Numeric(12,2), nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(12,2), nullable=False)
    order = db.relationship("Order", back_populates="items")

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False)
    provider_order_id = db.Column(db.String(255), unique=True, nullable=False)
    provider_payment_id = db.Column(db.String(255), unique=True)
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    amount = db.Column(db.Numeric(12,2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    paid_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    order = db.relationship("Order", back_populates="payments")


class OrderNotification(db.Model):
    __tablename__ = "order_notifications"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    channel = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime(timezone=True))
    next_attempt_at = db.Column(db.DateTime(timezone=True), index=True)
    order = db.relationship("Order", backref="notifications")
    __table_args__ = (db.UniqueConstraint("order_id", "channel", name="uq_order_notification_channel"),)
