from flask import Blueprint, abort, render_template, jsonify, request, flash, redirect, url_for
from sqlalchemy import func
import re
from app.extensions import db
from app.security.validators import safe_text
from flask_login import current_user, login_required
from app.models import Order, Address

orders_bp = Blueprint("orders", __name__)


@orders_bp.get("/orders/<order_number>/bill.pdf")
@login_required
def download_bill(order_number):
    from app.services.order_bills import bill_download_response
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return bill_download_response(order)

@orders_bp.get("")
@orders_bp.get("/")
@login_required
def dashboard():
    counts = dict(db.session.execute(db.select(Order.status, func.count(Order.id)).where(
        Order.user_id == current_user.id).group_by(Order.status)).all())
    recent = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc(), Order.id.desc()).limit(4).all()
    address = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id.desc()).first()
    return render_template("account/dashboard.html", recent_orders=recent, address=address,
        total_orders=sum(counts.values()), active_orders=sum(counts.get(s, 0) for s in ("Pending", "Confirmed", "Shipped")),
        delivered_orders=counts.get("Delivered", 0))


@orders_bp.post("/profile")
@login_required
def update_profile():
    try:
        first = safe_text(request.form.get("first_name"), 100)
        last = safe_text(request.form.get("last_name"), 100)
        phone = safe_text(request.form.get("phone"), 30)
        if not first or not last:
            raise ValueError("Enter your first and last name.")
        if phone and not re.fullmatch(r"[0-9]{10,15}", re.sub(r"[\s()+-]", "", phone)):
            raise ValueError("Enter a valid phone number with 10 to 15 digits.")
        current_user.first_name, current_user.last_name, current_user.phone = first, last, phone or None
        db.session.commit()
        flash("Your account details have been saved.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("orders.dashboard", _anchor="profile"))


@orders_bp.post("/address")
@login_required
def update_address():
    from app.services.addresses import validate_shipping_details
    try:
        details = validate_shipping_details(request.form)
        address = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id.desc()).first()
        if address is None:
            address = Address(user_id=current_user.id, **details)
            db.session.add(address)
        Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
        for key, value in details.items():
            setattr(address, key, value)
        address.is_default = True
        db.session.commit()
        flash("Your delivery address has been saved for checkout. Existing orders keep their original address.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("orders.dashboard", _anchor="address"))


@orders_bp.get("/orders")
@login_required
def list_orders():
    pagination = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc(), Order.id.desc()).paginate(
        page=max(1, request.args.get("page", 1, type=int)), per_page=12, error_out=False)
    return render_template("account/orders.html", orders=pagination.items, pagination=pagination)

@orders_bp.get("/orders/<order_number>")
@login_required
def detail(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first()
    if not order: abort(404)
    return render_template("account/order_detail.html", order=order)


@orders_bp.get("/orders/<order_number>/status")
@login_required
def status(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    response = jsonify(status=order.status, label=order.status_label, message=order.status_message)
    response.headers["Cache-Control"] = "no-store"
    return response
