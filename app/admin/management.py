"""Store operations built on the existing catalogue, commerce and user models."""
from datetime import datetime, timedelta
from pathlib import Path
import re

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.models import (User, Role, Product, ProductVariant, ProductImage, Category,
    Order, OrderItem, Payment, Inventory, InventoryMovement, AuditLog, Coupon, CouponUsage, Review)
from app.models.admin_session import AdminSession
from app.security.decorators import permission_required
from app.security.validators import safe_text, validate_money
from app.admin.security import utcnow, revoke_admin_session


def audit(action, entity, entity_id, details=None):
    db.session.add(AuditLog(actor_user_id=current_user.id, action=action,
        entity_type=entity, entity_id=str(entity_id), details=details,
        ip_address=(request.remote_addr or "")[:45], user_agent=request.user_agent.string[:500]))


def customer_query():
    return db.select(User).where(~User.roles.any(Role.name.in_(["Admin", "Super Admin"])))


def page(query):
    return db.paginate(query, page=max(1, request.args.get("page", 1, type=int)), per_page=25, error_out=False)


def integer(name, minimum=0, maximum=1_000_000, optional=False):
    value = request.form.get(name, "").strip()
    if optional and not value:
        return None
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Enter a valid whole number for {name.replace('_', ' ')}.") from None
    if not minimum <= result <= maximum:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} must be between {minimum} and {maximum}.")
    return result


def inventory_query():
    return db.select(ProductVariant).join(Product).outerjoin(Inventory).where(Product.is_archived.is_(False))


def low_stock_filter():
    return or_(Inventory.id.is_(None), Inventory.quantity - Inventory.reserved_quantity <= Inventory.low_stock_threshold)


def metrics():
    now = utcnow()
    since = now - timedelta(days=30)
    total_orders = db.session.scalar(db.select(func.count(Order.id)))
    open_orders = db.session.scalar(db.select(func.count(Order.id)).where(Order.status.in_(["Pending", "Confirmed", "Shipped"])))
    # Cash receipts and booked order value deliberately have different meanings.
    received = db.session.scalar(db.select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid"))
    booked = db.session.scalar(db.select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != "Cancelled"))
    recent_received = db.session.scalar(db.select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid", Payment.paid_at >= since))
    customers = db.session.scalar(db.select(func.count()).select_from(customer_query().subquery()))
    products = db.session.scalar(db.select(func.count(Product.id)).where(Product.is_archived.is_(False)))
    low = db.session.scalar(db.select(func.count()).select_from(inventory_query().where(low_stock_filter()).subquery()))
    return dict(orders=total_orders, open_orders=open_orders, received=received, booked=booked,
        recent_received=recent_received, customers=customers, products=products, low_stock=low)


def register_management(bp):
    from app.admin.reports import register_reports, period, overview, bounds
    register_reports(bp)
    @bp.get("/dashboard")
    @permission_required("dashboard.view")
    def dashboard():
        dates = period()
        recent = db.session.scalars(db.select(Order).where(*bounds(Order.created_at, dates)).order_by(Order.created_at.desc(), Order.id.desc()).limit(6)).all()
        return render_template("admin/dashboard.html", stats=metrics(), recent=recent, dates=dates, report=overview(dates))

    @bp.get("/customers")
    @permission_required("customers.manage")
    def customers():
        q = safe_text(request.args.get("q"), 120)
        query = customer_query()
        if q:
            query = query.where(or_(User.email.icontains(q, autoescape=True), User.first_name.icontains(q, autoescape=True), User.last_name.icontains(q, autoescape=True)))
        return render_template("admin/customers.html", pagination=page(query.order_by(User.created_at.desc(), User.id.desc())), q=q)

    @bp.route("/customers/<int:user_id>", methods=["GET", "POST"])
    @permission_required("customers.manage")
    def customer_detail(user_id):
        query = customer_query().where(User.id == user_id)
        if request.method == "POST":
            query = query.with_for_update()
        customer = db.session.scalar(query)
        if not customer:
            abort(404)
        if request.method == "POST":
            # Account status only. Never bind arbitrary form keys or role assignments.
            status = request.form.get("status")
            if status not in ("active", "disabled"):
                abort(400)
            customer.is_active = status == "active"
            audit("customer.status_updated", "user", customer.id, {"active": customer.is_active})
            db.session.commit()
            flash("Customer account status updated.", "success")
            return redirect(url_for("admin.customer_detail", user_id=user_id))
        orders = page(db.select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc(), Order.id.desc()))
        return render_template("admin/customer_detail.html", customer=customer, pagination=orders)

    @bp.get("/inventory")
    @permission_required("inventory.manage")
    def inventory():
        q = safe_text(request.args.get("q"), 120)
        low = request.args.get("low") == "1"
        query = inventory_query()
        if q:
            query = query.where(or_(ProductVariant.sku.icontains(q, autoescape=True), Product.name.icontains(q, autoescape=True)))
        if low:
            query = query.where(low_stock_filter())
        return render_template("admin/inventory.html", pagination=page(query.order_by(Product.name, ProductVariant.id)), q=q, low=low)

    @bp.post("/inventory/<int:variant_id>")
    @permission_required("inventory.manage")
    def update_inventory(variant_id):
        variant = db.session.scalar(db.select(ProductVariant).where(ProductVariant.id == variant_id).with_for_update())
        if not variant or variant.product.is_archived:
            abort(404)
        try:
            quantity = integer("quantity")
            threshold = integer("low_stock_threshold")
            stock = db.session.scalar(db.select(Inventory).where(Inventory.variant_id == variant_id).with_for_update().execution_options(populate_existing=True))
            if not stock:
                stock = Inventory(variant_id=variant_id, quantity=0, reserved_quantity=0)
                db.session.add(stock)
            if quantity < stock.reserved_quantity:
                raise ValueError("Stock cannot be lower than the quantity reserved for orders.")
            before = stock.quantity
            stock.quantity = quantity
            stock.low_stock_threshold = threshold
            if quantity != before:
                db.session.add(InventoryMovement(variant_id=variant_id, quantity_delta=quantity-before,
                    reason="admin_stock_adjustment", created_by=current_user.id, reference=f"inventory:{variant_id}"))
            audit("inventory.updated", "variant", variant_id, {"before": before, "after": quantity, "threshold": threshold})
            db.session.commit()
            flash("Inventory updated.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template("admin/error.html", code=400, message=str(exc)), 400
        return redirect(url_for("admin.inventory"))

    @bp.post("/categories/<int:category_id>/delete")
    @permission_required("products.delete")
    def delete_category(category_id):
        category = db.get_or_404(Category, category_id)
        # Explicitly unassign products; never delete a collection's products.
        db.session.execute(db.update(Product).where(Product.category_id == category_id).values(category_id=None))
        audit("category.deleted", "category", category_id, {"name": category.name})
        db.session.delete(category)
        db.session.commit()
        flash("Collection deleted. Its products are now uncategorised.", "success")
        return redirect(url_for("admin.categories"))

    @bp.get("/coupons")
    @permission_required("coupons.manage")
    def coupons():
        return render_template("admin/coupons.html", pagination=page(db.select(Coupon).order_by(Coupon.id.desc())))

    @bp.route("/coupons/create", methods=["GET", "POST"])
    @bp.route("/coupons/<int:coupon_id>/edit", methods=["GET", "POST"])
    @permission_required("coupons.manage")
    def edit_coupon(coupon_id=None):
        coupon = db.get_or_404(Coupon, coupon_id) if coupon_id else None
        error = None
        if request.method == "POST":
            try:
                code = safe_text(request.form.get("code"), 80).upper()
                if not re.fullmatch(r"[A-Z0-9_-]{3,80}", code):
                    raise ValueError("Use 3-80 letters, numbers, hyphens or underscores for the code.")
                kind = request.form.get("discount_type")
                value = validate_money(request.form.get("value"))
                if kind not in ("percentage", "fixed") or value <= 0 or (kind == "percentage" and value > 100):
                    raise ValueError("Choose a positive fixed discount or a percentage up to 100.")
                starts = datetime.fromisoformat(request.form.get("starts_at", ""))
                expires = datetime.fromisoformat(request.form.get("expires_at", ""))
                if starts.tzinfo or expires.tzinfo or starts >= expires:
                    raise ValueError("Expiry must be after the start time. Enter UTC dates.")
                maximum = validate_money(request.form["maximum_discount"]) if request.form.get("maximum_discount") else None
                if maximum is not None and maximum <= 0:
                    raise ValueError("Maximum discount must be greater than zero or left empty.")
                data = dict(code=code, discount_type=kind, value=value,
                    minimum_order=validate_money(request.form.get("minimum_order", "0")), maximum_discount=maximum,
                    starts_at=starts, expires_at=expires, usage_limit=integer("usage_limit", 1, optional=True),
                    per_user_limit=integer("per_user_limit", 1), is_active=request.form.get("is_active") == "1")
                if not coupon:
                    coupon = Coupon(**data)
                    db.session.add(coupon)
                else:
                    for key, value in data.items():
                        setattr(coupon, key, value)
                db.session.flush()
                audit("coupon.saved", "coupon", coupon.id)
                db.session.commit()
                flash("Coupon saved.", "success")
                return redirect(url_for("admin.coupons"))
            except (ValueError, IntegrityError) as exc:
                db.session.rollback()
                error = "Check the date format and coupon values." if isinstance(exc, ValueError) and "Invalid isoformat" in str(exc) else str(exc) if isinstance(exc, ValueError) else "That coupon code is already in use."
        return render_template("admin/coupon_form.html", coupon=coupon, error=error), 400 if error else 200

    @bp.post("/coupons/<int:coupon_id>/<action>")
    @permission_required("coupons.manage")
    def coupon_action(coupon_id, action):
        coupon = db.session.scalar(db.select(Coupon).where(Coupon.id == coupon_id).with_for_update())
        if not coupon or action not in ("disable", "delete"):
            abort(404)
        if action == "delete" and (coupon.usage_count or db.session.scalar(db.select(CouponUsage.id).where(CouponUsage.coupon_id == coupon_id).limit(1))):
            flash("Used coupons are retained for order history. Disable this coupon instead.", "error")
            return redirect(url_for("admin.coupons"))
        audit(f"coupon.{action}", "coupon", coupon_id)
        if action == "delete":
            db.session.delete(coupon)
        else:
            coupon.is_active = False
        db.session.commit()
        flash("Coupon updated.", "success")
        return redirect(url_for("admin.coupons"))

    @bp.get("/reviews")
    @permission_required("reviews.manage")
    def reviews():
        query = db.select(Review).order_by(Review.created_at.desc(), Review.id.desc())
        return render_template("admin/reviews.html", pagination=page(query))

    @bp.post("/reviews/<int:review_id>")
    @permission_required("reviews.manage")
    def moderate_review(review_id):
        review = db.get_or_404(Review, review_id)
        action = request.form.get("action")
        if action not in ("approve", "reject"):
            abort(400)
        # Existing model supports visible / unapproved, not a third moderation state.
        review.is_approved = action == "approve"
        audit(f"review.{action}", "review", review_id)
        db.session.commit()
        flash("Review approved." if review.is_approved else "Review rejected and hidden.", "success")
        return redirect(url_for("admin.reviews"))

    @bp.get("/analytics")
    @permission_required("analytics.view")
    def analytics():
        statuses = db.session.execute(db.select(Order.status, func.count(Order.id), func.sum(Order.total)).group_by(Order.status)).all()
        best = db.session.execute(db.select(OrderItem.product_name_snapshot, func.sum(OrderItem.quantity).label("units"), func.sum(OrderItem.line_total))
            .join(Order, Order.id == OrderItem.order_id).where(Order.status != "Cancelled")
            .group_by(OrderItem.product_name_snapshot).order_by(func.sum(OrderItem.quantity).desc()).limit(10)).all()
        return render_template("admin/analytics.html", stats=metrics(), statuses=statuses, best=best)

    @bp.route("/settings", methods=["GET", "POST"])
    @permission_required("settings.manage")
    @limiter.limit("10 per hour", methods=["POST"])
    def settings():
        error = None
        if request.method == "POST":
            try:
                if not check_password_hash(current_user.password_hash, request.form.get("current_password", "")[:1024]):
                    raise ValueError("Current password is incorrect.")
                first = safe_text(request.form.get("first_name"), 100)
                last = safe_text(request.form.get("last_name"), 100)
                if not first or not last:
                    raise ValueError("Enter your first and last name.")
                password = request.form.get("new_password", "")
                if password and (len(password) < 12 or len(password) > 1024):
                    raise ValueError("Use a password between 12 and 1024 characters.")
                if password != request.form.get("confirm_password", ""):
                    raise ValueError("The new passwords do not match.")
                current_user.first_name, current_user.last_name = first, last
                if password:
                    current_user.password_hash = generate_password_hash(password)
                audit("admin.profile_updated", "user", current_user.id, {"password_changed": bool(password)})
                if password or request.form.get("revoke_sessions") == "1":
                    db.session.execute(db.delete(AdminSession).where(AdminSession.user_id == current_user.id))
                db.session.commit()
                if password or request.form.get("revoke_sessions") == "1":
                    revoke_admin_session()
                    flash("Security settings updated. Sign in to admin again.", "success")
                    return redirect(url_for("admin.login"))
                flash("Profile saved.", "success")
                return redirect(url_for("admin.settings"))
            except ValueError as exc:
                db.session.rollback()
                error = str(exc)
        return render_template("admin/settings.html", error=error,
            idle_minutes=current_app.config["ADMIN_SESSION_IDLE_SECONDS"] // 60,
            max_hours=current_app.config["ADMIN_SESSION_MAX_SECONDS"] // 3600), 400 if error else 200

    @bp.get("/product-images/<int:image_id>")
    @permission_required("products.view")
    def product_image(image_id):
        image = db.get_or_404(ProductImage, image_id)
        root = Path(current_app.config["UPLOAD_DIR"]).resolve()
        target = (root / image.storage_key).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            abort(404)
        return send_file(target, mimetype=image.mime_type, max_age=0)
