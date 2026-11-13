from datetime import datetime, timezone
from app.extensions import db
from app.models.types import BigIntPrimaryKey


class StoreSettings(db.Model):
    __tablename__ = "store_settings"
    id = db.Column(db.Integer, primary_key=True)
    values = db.Column(db.JSON, nullable=False)


class Shipment(db.Model):
    __tablename__ = "shipments"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    courier = db.Column(db.String(40), nullable=False, default="DTDC")
    awb = db.Column(db.String(80))
    status = db.Column(db.String(40), nullable=False, default="Not booked")
    weight_grams = db.Column(db.Integer)
    serviceability_confirmed_at = db.Column(db.DateTime(timezone=True))
    dispatched_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.String(1000))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    order = db.relationship("Order", backref=db.backref("shipment", uselist=False))


class CodSettlement(db.Model):
    __tablename__ = "cod_settlements"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    order_id = db.Column(db.BigInteger, db.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    reference = db.Column(db.String(100), nullable=False)
    net_amount = db.Column(db.Numeric(12,2), nullable=False)
    fees = db.Column(db.Numeric(12,2), nullable=False)
    received_on = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.BigInteger, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    order = db.relationship("Order", backref="settlements")
    __table_args__ = (db.UniqueConstraint("order_id", "reference", name="uq_cod_settlement_reference"),
                     db.CheckConstraint("net_amount >= 0 AND fees >= 0 AND net_amount + fees > 0", name="ck_cod_settlement_amount"))
