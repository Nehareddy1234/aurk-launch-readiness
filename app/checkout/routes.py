from decimal import Decimal
from uuid import uuid4

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Address,
    Cart,
    CartItem,
    Inventory,
    InventoryMovement,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductVariant,
)
from app.services.order_notifications import queue_order_alerts
from app.services.pricing import calculate_subtotal, calculate_total


checkout_bp = Blueprint("checkout", __name__)
ZERO = Decimal("0.00")


def _cart_for_current_user():
    query = Cart.query.filter_by(user_id=current_user.id)
    if request.method == "POST":
        query = query.with_for_update()
    return query.first()


def _cart_items(cart):
    if not cart:
        return []
    if request.method == "POST":
        # Current locking read also protects against stale repeatable-read
        # snapshots when the same checkout is submitted concurrently.
        return list(db.session.scalars(db.select(CartItem).where(CartItem.cart_id == cart.id)
            .order_by(CartItem.variant_id).with_for_update().execution_options(populate_existing=True)))
    return list(cart.items)


def _shipping_details_from_form():
    from app.services.addresses import validate_shipping_details
    return validate_shipping_details(request.form)


@checkout_bp.route("", methods=["GET", "POST"])
@login_required
def checkout():
    cart = _cart_for_current_user()
    items = _cart_items(cart)
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view"))

    if request.method == "POST":
        try:
            shipping = _shipping_details_from_form()
            from app.services.store_settings import check_cod_coverage
            check_cod_coverage(shipping["postal_code"])

            # Lock every inventory row before checking and decrementing it.
            # This prevents two simultaneous checkouts from overselling stock.
            # Serialize availability changes with checkout using current product reads.
            product_ids = sorted({item.variant.product_id for item in items if item.variant})
            locked_products = {p.id: p for p in db.session.scalars(db.select(Product)
                .where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
                .execution_options(populate_existing=True))}
            variants = {v.id: v for v in db.session.scalars(db.select(ProductVariant)
                .where(ProductVariant.id.in_([item.variant_id for item in items]))
                .order_by(ProductVariant.id).with_for_update()
                .execution_options(populate_existing=True))}
            locked_inventory = {}
            prices = {}
            for item in items:
                variant = variants.get(item.variant_id)
                if item.quantity < 1:
                    raise ValueError("An item has an invalid quantity. Please update your cart.")
                if (not variant or not variant.is_active or variant.product_id not in locked_products
                        or not locked_products[variant.product_id].is_purchasable):
                    raise ValueError("One of the selected items is no longer available.")
                inventory = db.session.execute(
                    db.select(Inventory)
                    .where(Inventory.variant_id == variant.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
                product = locked_products[variant.product_id]
                if not inventory or inventory.quantity - inventory.reserved_quantity < item.quantity:
                    raise ValueError(f"{product.name} no longer has enough stock.")
                locked_inventory[item.id] = inventory
                prices[item.id] = variant.price_override if variant.price_override is not None else product.current_price

            subtotal = sum((prices[item.id] * item.quantity for item in items), ZERO)
            total = calculate_total(subtotal)

            order_number = f"ARD-{uuid4().hex[:12].upper()}"
            order = Order(
                user_id=current_user.id,
                order_number=order_number,
                status="Pending",
                subtotal=subtotal,
                discount=ZERO,
                shipping=ZERO,
                tax=ZERO,
                total=total,
                currency="INR",
                shipping_name=shipping["recipient_name"],
                shipping_phone=shipping["phone"],
                shipping_line1=shipping["line1"],
                shipping_line2=shipping["line2"] or None,
                shipping_city=shipping["city"],
                shipping_state=shipping["state"],
                shipping_postal_code=shipping["postal_code"],
                shipping_country=shipping["country"],
            )
            db.session.add(order)
            db.session.flush()

            for item in items:
                variant = variants[item.variant_id]
                unit_price = prices[item.id]
                db.session.add(OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    product_name_snapshot=locked_products[variant.product_id].name,
                    sku_snapshot=variant.sku,
                    size_snapshot=variant.size.name if variant.size else "One size",
                    color_snapshot=variant.color.name if variant.color else "Default",
                    unit_price=unit_price,
                    quantity=item.quantity,
                    line_total=unit_price * item.quantity,
                ))
                inventory = locked_inventory[item.id]
                inventory.quantity -= item.quantity
                db.session.add(InventoryMovement(
                    variant_id=variant.id,
                    quantity_delta=-item.quantity,
                    reason="order_placed",
                    reference=order_number,
                    created_by=current_user.id,
                ))

            # Cash on delivery is a usable offline payment option while an
            # online gateway is intentionally not configured.
            db.session.add(Payment(
                order_id=order.id,
                provider="cash_on_delivery",
                provider_order_id=f"cod_{order_number}",
                status="pending",
                amount=total,
                currency="INR",
            ))

            if request.form.get("save_address"):
                if request.form.get("make_default"):
                    Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
                db.session.add(Address(user_id=current_user.id, is_default=bool(request.form.get("make_default")), **shipping))

            for item in items:
                db.session.delete(item)
            queue_order_alerts(order)
            from app.services.customer_emails import queue_customer_email
            queue_customer_email("order_received", current_user, order)
            db.session.commit()
            return redirect(url_for("checkout.success", order_number=order.order_number))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        except Exception:
            db.session.rollback()
            raise

    subtotal = calculate_subtotal(items)
    total = calculate_total(subtotal)
    address = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id.desc()).first()
    defaults = {"recipient_name": f"{current_user.first_name} {current_user.last_name}", "phone": current_user.phone or "", "country": "India"}
    if address:
        defaults.update({key: getattr(address, key) or "" for key in ("recipient_name", "phone", "line1", "line2", "city", "state", "postal_code", "country")})
    defaults["country"] = "India"
    return render_template("checkout/checkout.html", cart=cart, subtotal=subtotal, total=total, defaults=defaults)


@checkout_bp.get("/success/<order_number>")
@login_required
def success(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template("checkout/success.html", order=order)
