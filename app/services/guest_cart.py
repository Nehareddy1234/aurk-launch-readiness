"""Guest bags contain only SKU IDs and quantities in the signed session."""
from types import SimpleNamespace

from flask import flash, session

from app.extensions import db
from app.models import Cart, CartItem, ProductVariant

KEY = "guest_cart"
MAX_ITEMS = 40


def contents():
    return dict(session.get(KEY, {}))


def save(items):
    if items:
        session[KEY] = items
    else:
        session.pop(KEY, None)


def guest_cart():
    stored = contents()
    variants = db.session.scalars(db.select(ProductVariant).where(ProductVariant.id.in_([int(key) for key in stored]))).all() if stored else []
    by_id = {str(v.id): v for v in variants}
    items = [SimpleNamespace(id=int(key), variant=by_id[key], quantity=quantity)
             for key, quantity in stored.items() if key in by_id]
    if len(items) != len(stored):
        save({key: value for key, value in stored.items() if key in by_id})
        flash("An item was removed from the catalogue and is no longer in your bag.", "info")
    return SimpleNamespace(items=items)


def merge_into_account(user):
    stored = contents()
    if not stored:
        return
    cart = Cart.query.filter_by(user_id=user.id).with_for_update().first()
    if cart is None:
        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.flush()
    existing = {item.variant_id: item for item in cart.items}
    adjusted = False
    for key, quantity in stored.items():
        variant_id = int(key)
        variant = db.session.get(ProductVariant, variant_id)
        if variant is None:
            adjusted = True
            continue
        item = existing.get(variant_id)
        combined = quantity + (item.quantity if item else 0)
        if combined > 99:
            adjusted = True
        if item:
            item.quantity = min(combined, 99)
        else:
            db.session.add(CartItem(cart_id=cart.id, variant_id=variant_id, quantity=min(combined, 99)))
    # Clear the guest bag only after the database has safely saved it.
    db.session.commit()
    session.pop(KEY, None)
    if adjusted:
        flash("Your bags were combined. Removed products or quantities over 99 were adjusted; please review your bag.", "info")
