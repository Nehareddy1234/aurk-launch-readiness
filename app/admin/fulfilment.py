from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from app.extensions import db
from app.models import Order, Shipment, CodSettlement, StoreSettings, AuditLog, Payment
from app.security.decorators import permission_required
from app.services.store_settings import get_settings, validate_settings

SHIPMENT_STATES = ("Not booked", "Booked", "In transit", "Delivery failed", "RTO initiated", "Returned")


def register_fulfilment(bp):
    @bp.route("/launch-settings", methods=["GET", "POST"])
    @permission_required("settings.manage")
    def launch_settings():
        values = get_settings()
        if request.method == "POST":
            try:
                values = validate_settings(request.form)
                row = db.session.get(StoreSettings, 1)
                if row is None:
                    row = StoreSettings(id=1, values=values)
                    db.session.add(row)
                row.values = values
                db.session.add(AuditLog(actor_user_id=current_user.id, action="settings.business_updated", entity_type="settings", entity_id="1"))
                db.session.commit()
                flash("Business and delivery settings saved.", "success")
                return redirect(url_for("admin.launch_settings"))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
        return render_template("admin/launch_settings.html", settings=values)

    @bp.post("/orders/<order_number>/shipment")
    @permission_required("orders.manage")
    def save_shipment(order_number):
        order = Order.query.filter_by(order_number=order_number).with_for_update().populate_existing().first_or_404()
        try:
            if order.status == "Cancelled":
                raise ValueError("Cancelled orders cannot be dispatched.")
            awb = request.form.get("awb", "").strip().upper()
            status = request.form.get("shipment_status", "Not booked")
            notes = request.form.get("notes", "").strip()
            if awb and not re.fullmatch(r"[A-Z0-9-]{4,80}", awb):
                raise ValueError("Enter the tracking number issued by DTDC.")
            if status not in SHIPMENT_STATES or len(notes) > 1000:
                raise ValueError("Check the shipment status and notes.")
            weight = int(request.form.get("weight_grams") or 0)
            if not 0 <= weight <= 1000000:
                raise ValueError("Enter a valid weight in grams.")
            if status != "Not booked" and not awb:
                raise ValueError("Enter the AWB before recording a booked shipment.")
            if status in {"In transit", "Delivery failed", "RTO initiated", "Returned"} and order.status != "Shipped":
                raise ValueError("These shipment states require an order marked Shipped.")
            shipment = order.shipment or Shipment(order=order)
            shipment.awb, shipment.status, shipment.weight_grams, shipment.notes = awb or None, status, weight or None, notes or None
            if request.form.get("serviceability_confirmed") == "yes":
                shipment.serviceability_confirmed_at = datetime.now(timezone.utc)
            if status == "In transit" and shipment.dispatched_at is None:
                shipment.dispatched_at = datetime.now(timezone.utc)
            db.session.add(shipment)
            db.session.add(AuditLog(actor_user_id=current_user.id, action="order.shipment_updated", entity_type="order", entity_id=str(order.id), details={"status":status,"awb":awb}))
            db.session.commit()
            flash("Shipment saved. Returned parcels require inspection and a separate inventory adjustment.", "success")
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
        return redirect(url_for("admin.order_detail", order_number=order_number))

    @bp.post("/orders/<order_number>/settlements")
    @permission_required("orders.manage")
    def save_settlement(order_number):
        order = Order.query.filter_by(order_number=order_number).with_for_update().populate_existing().first_or_404()
        try:
            if order.status != "Delivered" or request.form.get("received") != "yes":
                raise ValueError("Verify the remittance and mark the order Delivered before recording settlement.")
            reference = request.form.get("reference", "").strip()
            if not 3 <= len(reference) <= 100:
                raise ValueError("Enter a settlement reference between 3 and 100 characters.")
            if CodSettlement.query.filter_by(order_id=order.id, reference=reference).first():
                flash("This settlement reference was already recorded; nothing was added.", "info")
                return redirect(url_for("admin.order_detail", order_number=order_number))
            net, fees = (Decimal(request.form.get(k, "0")) for k in ("net_amount", "fees"))
            if any(not n.is_finite() or n < 0 or n != n.quantize(Decimal("0.01")) for n in (net,fees)) or net+fees <= 0:
                raise ValueError("Enter non-negative amounts with at most two decimal places.")
            received_on = date.fromisoformat(request.form.get("received_on", ""))
            if received_on > datetime.now(timezone.utc).date() or received_on < order.created_at.date():
                raise ValueError("Settlement date must be between order placement and today.")
            payments = list(db.session.scalars(db.select(Payment).where(Payment.order_id==order.id).with_for_update()))
            if len(payments)!=1 or payments[0].provider!="cash_on_delivery" or payments[0].status!="pending":
                raise ValueError("This order's payment is already recorded or requires review.")
            if payments[0].amount != order.total or payments[0].currency != order.currency:
                raise ValueError("The payment does not match this order. Review the payment records first.")
            previous = db.session.scalar(db.select(db.func.coalesce(db.func.sum(CodSettlement.net_amount+CodSettlement.fees),0)).where(CodSettlement.order_id==order.id))
            if previous+net+fees > order.total:
                raise ValueError("Settlement exceeds the outstanding COD amount.")
            db.session.add(CodSettlement(order_id=order.id, reference=reference, net_amount=net, fees=fees, received_on=received_on, created_by=current_user.id))
            if previous+net+fees == order.total:
                payments[0].status="paid"
                payments[0].paid_at=datetime.now(timezone.utc)
            db.session.add(AuditLog(actor_user_id=current_user.id, action="order.settlement_recorded", entity_type="order", entity_id=str(order.id), details={"reference":reference,"net":str(net),"fees":str(fees)}))
            db.session.commit()
            flash("Verified settlement recorded. Payment becomes paid when the full COD amount is reconciled.", "success")
        except (ValueError, InvalidOperation, TypeError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Check the settlement values.", "error")
        return redirect(url_for("admin.order_detail", order_number=order_number))
