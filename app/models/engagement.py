from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey


class ProductInterest(db.Model):
    __tablename__ = "product_interests"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    product_id = db.Column(BigIntPrimaryKey, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(BigIntPrimaryKey, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    identity_key = db.Column(db.String(80), nullable=False)
    customer_name = db.Column(db.String(200))
    customer_email = db.Column(db.String(254), index=True)
    customer_phone = db.Column(db.String(30))
    product_status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    notified_at = db.Column(db.DateTime(timezone=True))
    notification_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    notification_next_attempt_at = db.Column(db.DateTime(timezone=True), index=True)
    notification_last_error = db.Column(db.String(200))
    product = db.relationship("Product", back_populates="interests")
    __table_args__ = (db.UniqueConstraint("product_id", "identity_key", name="uq_product_interest_identity"),)

class Wishlist(db.Model):
    __tablename__ = "wishlists"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    items = db.relationship("WishlistItem", back_populates="wishlist", cascade="all, delete-orphan")

class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    wishlist_id = db.Column(db.BigInteger, db.ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (db.UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_product"),)
    wishlist = db.relationship("Wishlist", back_populates="items")
    product = db.relationship("Product")

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    product = db.relationship("Product")
    customer = db.relationship("User")
    rating = db.Column(db.SmallInteger, nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    verified_purchase = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
