from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey
class Inventory(db.Model):
    __tablename__ = "inventory"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    variant_id = db.Column(db.BigInteger, db.ForeignKey("product_variants.id", ondelete="CASCADE"), unique=True, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reserved_quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    variant = db.relationship("ProductVariant", back_populates="inventory")

class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    variant_id = db.Column(db.BigInteger, db.ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    reference = db.Column(db.String(100))
    created_by = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    actor_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80))
    entity_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
