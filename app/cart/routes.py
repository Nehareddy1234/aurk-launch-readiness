from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Cart, CartItem, ProductVariant
from app.security.validators import validate_positive_quantity
from app.services.guest_cart import guest_cart, contents, save, MAX_ITEMS


cart_bp = Blueprint("cart", __name__)


def get_cart():
    """Return the guest bag or the signed-in account cart."""

    if not current_user.is_authenticated:
        return guest_cart()

    cart = Cart.query.filter_by(
        user_id=current_user.id
    ).first()

    if not cart:
        cart = Cart(
            user_id=current_user.id
        )

        db.session.add(cart)
        db.session.commit()

    return cart


def get_available_stock(variant):
    """Return currently available stock for a variant."""

    if not variant.inventory:
        return 0

    return max(
        variant.inventory.quantity
        - variant.inventory.reserved_quantity,
        0
    )


@cart_bp.get("")
def view():
    cart = get_cart()

    subtotal = 0

    checkout_ready = bool(cart.items)
    for item in cart.items:
        price = (
            item.variant.price_override
            if item.variant.price_override is not None
            else item.variant.product.current_price
        )

        item.available_stock = min(get_available_stock(item.variant), 99)
        item.unavailable = not item.variant.is_active or not item.variant.product.is_purchasable or item.available_stock == 0
        if item.unavailable or item.quantity > item.available_stock:
            checkout_ready = False
        item.unit_price = price
        item.line_total = price * item.quantity
        subtotal += item.line_total

    return render_template(
        "cart/cart.html",
        cart=cart,
        subtotal=subtotal,
        checkout_ready=checkout_ready,
    )


@cart_bp.post("/add")
def add():
    variant_id = request.form.get("variant_id", type=int)

    quantity = request.form.get("quantity", type=int) if "quantity" in request.form else 1

    if not variant_id:
        flash(
            "Please select an available option.",
            "error"
        )

        return redirect(
            url_for("products.shop")
        )

    try:
        validate_positive_quantity(quantity)
        if quantity > 99:
            raise ValueError("You can add up to 99 items of each option.")
    except ValueError as exc:

        flash(
            str(exc),
            "error"
        )

        return redirect(
            url_for("products.shop")
        )

    # A cart item must always refer to an exact SKU.  Looking up a
    # variant from independently submitted size and colour IDs can select
    # a matching variant from an entirely different product.
    variant = (
        ProductVariant.query
        .filter_by(
            id=variant_id,
            is_active=True,
        )
        .join(ProductVariant.product)
        .filter_by(is_active=True)
        .first()
    )

    if not variant or not variant.product.is_purchasable:
        flash(
            "That size and color combination is unavailable.",
            "error"
        )

        return redirect(
            url_for("products.shop")
        )

    available = get_available_stock(
        variant
    )

    if available <= 0:
        flash(
            "This variant is currently out of stock.",
            "error"
        )

        return redirect(
            url_for("products.shop")
        )

    if quantity > available:
        flash(
            f"Only {available} item(s) are available.",
            "error"
        )

        return redirect(
            url_for("products.shop")
        )

    if not current_user.is_authenticated:
        bag = contents()
        key = str(variant.id)
        combined = bag.get(key, 0) + quantity
        if combined > min(available, 99):
            flash(f"You can only add {min(available, 99)} item(s) of this option.", "error")
        elif key not in bag and len(bag) >= MAX_ITEMS:
            flash("Your bag can hold up to 40 different options. Remove an item before adding another.", "info")
        else:
            bag[key] = combined
            save(bag)
            flash("Added to cart.", "success")
        return redirect(url_for("cart.view"))

    cart = get_cart()

    item = (
        CartItem.query
        .filter_by(
            cart_id=cart.id,
            variant_id=variant.id,
        )
        .first()
    )

    if item:

        new_quantity = (
            item.quantity + quantity
        )

        if new_quantity > min(available, 99):

            flash(
                f"You can only add {min(available, 99)} item(s) of this variant.",
                "error"
            )

            return redirect(
                url_for("products.shop")
            )

        item.quantity = new_quantity

    else:

        item = CartItem(
            cart_id=cart.id,
            variant_id=variant.id,
            quantity=quantity,
        )

        db.session.add(item)

    db.session.commit()

    flash(
        "Added to cart.",
        "success"
    )

    return redirect(
        url_for("cart.view")
    )


@cart_bp.post("/update")
def update():

    item_id = request.form.get(
        "item_id",
        type=int
    )

    quantity = request.form.get(
        "quantity",
        type=int
    )

    if not item_id or quantity is None:
        return (
            "Bad request",
            400
        )

    if not current_user.is_authenticated:
        bag = contents()
        key = str(item_id)
        if key not in bag:
            return "Cart item not found", 404
        variant = db.session.get(ProductVariant, item_id)
        if not variant or not variant.is_active or not variant.product.is_purchasable:
            flash("This item is no longer available. Please remove it from your bag.", "error")
        elif quantity < 1 or quantity > min(get_available_stock(variant), 99):
            flash("Choose a quantity between 1 and the available stock (up to 99).", "error")
        else:
            bag[key] = quantity
            save(bag)
            flash("Cart updated.", "success")
        return redirect(url_for("cart.view"))

    item = db.session.get(
        CartItem,
        item_id
    )

    if not item:
        return (
            "Cart item not found",
            404
        )

    # Security check:
    # Make sure this cart item belongs to
    # the currently logged-in user.
    if item.cart.user_id != current_user.id:
        return (
            "Forbidden",
            403
        )

    try:
        validate_positive_quantity(quantity)
        if quantity > 99:
            raise ValueError("You can add up to 99 items of each option.")

    except ValueError:
        flash(
            "Invalid quantity.",
            "error"
        )

        return redirect(
            url_for("cart.view")
        )

    if not item.variant.is_active or not item.variant.product.is_purchasable:
        flash("This item is no longer available. Please remove it from your cart.", "error")
        return redirect(url_for("cart.view"))

    available = get_available_stock(
        item.variant
    )

    if available <= 0:

        flash(
            "This item is currently out of stock.",
            "error"
        )

        return redirect(
            url_for("cart.view")
        )

    if quantity > available:

        flash(
            f"Only {available} item(s) are available.",
            "error"
        )

        return redirect(
            url_for("cart.view")
        )

    item.quantity = quantity

    db.session.commit()

    flash(
        "Cart updated.",
        "success"
    )

    return redirect(
        url_for("cart.view")
    )


@cart_bp.post("/remove")
def remove():

    item_id = request.form.get(
        "item_id",
        type=int
    )

    if not item_id:
        return (
            "Bad request",
            400
        )

    if not current_user.is_authenticated:
        bag = contents()
        bag.pop(str(item_id), None)
        save(bag)
        return redirect(url_for("cart.view"))

    item = db.session.get(
        CartItem,
        item_id
    )

    if not item:
        return redirect(
            url_for("cart.view")
        )

    # Security check.
    if item.cart.user_id != current_user.id:
        return (
            "Forbidden",
            403
        )

    db.session.delete(item)
    db.session.commit()

    flash(
        "Item removed from cart.",
        "success"
    )

    return redirect(
        url_for("cart.view")
    )
