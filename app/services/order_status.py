from app.extensions import db
from app.models import Order, Inventory, InventoryMovement, AuditLog, Payment, OrderNotification

LABELS = {"Pending": "Awaiting confirmation", "Confirmed": "Order confirmed", "Shipped": "Order shipped", "Delivered": "Order delivered", "Cancelled": "Order cancelled"}
MESSAGES = {"Pending": "We have received your order. Our team will review it shortly.",
    "Confirmed": "Order confirmed \u2014 you will receive a call shortly.",
    "Shipped": "Your order is on its way. Please keep your phone available for delivery.",
    "Delivered": "Your order has been delivered. Thank you for shopping with AURK.",
    "Cancelled": "This order has been cancelled. No delivery payment is due."}
TRANSITIONS = {"Pending": {"Confirmed", "Cancelled"}, "Confirmed": {"Shipped", "Cancelled"}, "Shipped": {"Delivered"}}


def change_status(order_number, target, actor_id, reason=""):
    from flask import current_app
    from datetime import datetime, timezone
    order = Order.query.filter_by(order_number=order_number).with_for_update().populate_existing().first_or_404()
    if target == order.status:
        return False
    if target not in TRANSITIONS.get(order.status, set()):
        raise ValueError("This status change is not available for the order's current status.")
    previous = order.status
    if current_app.config.get("COD_SERVICEABILITY_REQUIRED"):
        if target == "Confirmed":
            from app.services.store_settings import check_cod_coverage, get_settings
            check_cod_coverage(order.shipping_postal_code)
            if get_settings()["coverage_mode"] == "manual" and not (order.shipment and order.shipment.serviceability_confirmed_at):
                raise ValueError("Verify DTDC COD service for this PIN code and save the coverage confirmation first.")
        if target == "Shipped" and not (order.shipment and order.shipment.awb):
            raise ValueError("Save the DTDC tracking number before marking the order shipped.")
    if target == "Delivered" and order.shipment and order.shipment.status in {"Delivery failed", "RTO initiated", "Returned"}:
        raise ValueError("Resolve the failed delivery or return before marking this order delivered.")
    if target == "Shipped" and order.shipment:
        order.shipment.status = "In transit"
        order.shipment.dispatched_at = datetime.now(timezone.utc)
    if target == "Cancelled":
        reason = reason.strip()
        if not 3 <= len(reason) <= 500:
            raise ValueError("Enter a cancellation reason between 3 and 500 characters.")
        payments = list(db.session.scalars(db.select(Payment).where(Payment.order_id == order.id).with_for_update()))
        if any(p.provider != "cash_on_delivery" or p.status != "pending" for p in payments):
            raise ValueError("This order's payment needs review before cancellation.")
        for item in sorted(order.items, key=lambda item: item.variant_id):
            inventory = db.session.execute(db.select(Inventory).where(Inventory.variant_id == item.variant_id)
                .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if inventory is None:
                raise ValueError("Inventory is missing for an order item. Resolve it before cancelling.")
            inventory.quantity += item.quantity
            db.session.add(InventoryMovement(variant_id=item.variant_id, quantity_delta=item.quantity,
                reason="order_cancelled", reference=order.order_number, created_by=actor_id))
        for payment in payments:
            payment.status = "cancelled"
        db.session.execute(db.update(OrderNotification).where(OrderNotification.order_id == order.id,
            OrderNotification.status.in_(["pending", "failed"])).values(status="skipped", last_error=None))
    order.status = target
    from app.services.customer_emails import queue_customer_email
    from app.models import User, CustomerEmail
    if target == "Cancelled":
        db.session.execute(db.update(CustomerEmail).where(CustomerEmail.order_id == order.id,
            CustomerEmail.status.in_(["pending", "failed"])).values(status="skipped", last_error=None))
    queue_customer_email("order_" + target.lower(), db.session.get(User, order.user_id), order)
    db.session.add(AuditLog(actor_user_id=actor_id, action="order." + target.lower(),
        entity_type="order", entity_id=str(order.id),
        details={"previous_status": previous, "status": target, "reason": reason if target == "Cancelled" else None}))
    db.session.commit()
    return True


def record_cod_received(order_number, actor_id, acknowledged=False):
    from datetime import datetime, timezone
    order = Order.query.filter_by(order_number=order_number).with_for_update().populate_existing().first_or_404()
    if order.status != "Delivered":
        raise ValueError("Mark the order delivered before recording payment received.")
    payments = list(db.session.scalars(db.select(Payment).where(Payment.order_id == order.id)
        .with_for_update().execution_options(populate_existing=True)))
    if len(payments) != 1:
        raise ValueError("This order's payment records need review.")
    payment = payments[0]
    if payment.provider != "cash_on_delivery" or payment.amount != order.total or payment.currency != order.currency:
        raise ValueError("The payment does not match this cash-on-delivery order.")
    if payment.status == "paid":
        return False
    if payment.status != "pending":
        raise ValueError("This payment cannot be marked received from its current status.")
    if not acknowledged:
        raise ValueError("Confirm that the full cash-on-delivery amount has been received.")
    if order.settlements:
        raise ValueError("Partial settlements exist. Reconcile the remaining amount using the settlement form.")
    payment.status = "paid"
    payment.paid_at = datetime.now(timezone.utc)
    db.session.add(AuditLog(actor_user_id=actor_id, action="order.payment_received",
        entity_type="order", entity_id=str(order.id), details={"payment_id":payment.id,
        "amount":str(payment.amount), "currency":payment.currency}))
    db.session.commit()
    return True
