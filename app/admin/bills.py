from flask import current_app, flash, redirect, url_for
from app.extensions import db, limiter
from app.models import Order, User, AuditLog
from app.security.decorators import permission_required
from app.services.order_bills import bill_download_response, email_order_bill
from flask_login import current_user


def register_bills(bp):
    @bp.get("/orders/<order_number>/bill.pdf")
    @permission_required("orders.manage")
    def download_order_bill(order_number):
        order = Order.query.filter_by(order_number=order_number).first_or_404()
        return bill_download_response(order)

    @bp.post("/orders/<order_number>/email-bill")
    @permission_required("orders.manage")
    @limiter.limit("10 per hour", key_func=lambda: str(current_user.id), methods=["POST"])
    def email_bill(order_number):
        order = Order.query.filter_by(order_number=order_number).first_or_404()
        customer = db.session.get(User, order.user_id)
        if customer is None or not customer.is_active:
            flash("This customer account is unavailable. The bill was not emailed.", "error")
            return redirect(url_for("admin.order_detail", order_number=order.order_number))
        try:
            email_order_bill(order, customer.email)
        except Exception as exc:
            current_app.logger.warning("Order bill email failed for order %s (%s)", order.id, type(exc).__name__)
            flash("The bill email could not be confirmed as sent. Check email settings and the recipient inbox before retrying.", "error")
        else:
            db.session.add(AuditLog(actor_user_id=current_user.id, action="order.bill_emailed", entity_type="order", entity_id=str(order.id)))
            db.session.commit()
            flash("Bill email accepted by the email provider. Inbox delivery is not yet confirmed.", "success")
        return redirect(url_for("admin.order_detail", order_number=order.order_number))
