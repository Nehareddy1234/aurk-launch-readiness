from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey

class CustomerPhoto(db.Model):
    __tablename__ = "customer_photos"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_item_id = db.Column(db.BigInteger, db.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False, unique=True)
    caption = db.Column(db.String(400), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_customer_photo_status"),)
    customer = db.relationship("User")
    product = db.relationship("Product")
    order_item = db.relationship("OrderItem")
