from pathlib import Path
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload
from app.extensions import db, limiter
from app.models import CustomerPhoto, Order, OrderItem, ProductVariant
from app.security.validators import safe_text
from app.services.customer_photos import save_customer_photo

community_bp = Blueprint("community", __name__)

def purchased_items():
    return db.select(OrderItem).join(Order).where(Order.user_id == current_user.id, Order.status == "Delivered").options(selectinload(OrderItem.order))

@community_bp.get("/worn-by-you")
def gallery():
    photos = db.paginate(db.select(CustomerPhoto).where(CustomerPhoto.status == "approved")
        .options(selectinload(CustomerPhoto.customer), selectinload(CustomerPhoto.product), selectinload(CustomerPhoto.order_item))
        .order_by(CustomerPhoto.created_at.desc(), CustomerPhoto.id.desc()),
        page=max(1, request.args.get("page", 1, type=int)), per_page=24, error_out=False)
    items, own, own_pagination = [], [], None
    if current_user.is_authenticated:
        items = list(db.session.scalars(purchased_items().order_by(OrderItem.id.desc())))
        own_pagination = db.paginate(db.select(CustomerPhoto).where(CustomerPhoto.user_id == current_user.id)
            .options(selectinload(CustomerPhoto.order_item)).order_by(CustomerPhoto.id.desc()),
            page=max(1, request.args.get("my_page", 1, type=int)), per_page=12, error_out=False)
        own = own_pagination.items
    response = current_app.make_response(render_template("community/gallery.html", pagination=photos, purchased_items=items, own_photos=own, own_pagination=own_pagination))
    response.headers["Cache-Control"] = "no-store, private"
    return response

@community_bp.post("/worn-by-you/upload")
@login_required
@limiter.limit("10 per hour;30 per day", key_func=lambda: str(current_user.id))
def upload():
    key = None
    try:
        # Lock the owning user row to serialize each customer's upload limits.
        from app.models import User
        db.session.execute(db.select(User.id).where(User.id == current_user.id).with_for_update()).scalar_one()
        item = db.session.scalar(purchased_items().where(OrderItem.id == request.form.get("order_item_id", type=int)))
        if item is None:
            abort(403)
        if request.form.get("publish_consent") != "1":
            raise ValueError("Give permission to publish your photo before uploading.")
        caption = safe_text(request.form.get("caption"), 400)
        count = len(db.session.scalars(db.select(CustomerPhoto.id).where(
            CustomerPhoto.user_id == current_user.id, CustomerPhoto.order_item_id == item.id).with_for_update()).all())
        if count >= 5:
            raise ValueError("You can upload up to five photos for this purchased item.")
        key = save_customer_photo(request.files.get("photo"))
        variant = db.session.get(ProductVariant, item.variant_id)
        db.session.add(CustomerPhoto(user_id=current_user.id, product_id=variant.product_id,
            order_item_id=item.id, storage_key=key, caption=caption, status="pending"))
        db.session.commit()
        flash("Photo uploaded! It will appear after our team approves it.", "success")
    except Exception as exc:
        db.session.rollback()
        if key:
            (Path(current_app.config["UPLOAD_DIR"]) / key).unlink(missing_ok=True)
        if not isinstance(exc, ValueError):
            raise
        flash(str(exc), "error")
    return redirect(url_for("community.gallery", _anchor="your-photos"))

@community_bp.get("/worn-by-you/photos/<int:photo_id>")
def photo(photo_id):
    entry = db.get_or_404(CustomerPhoto, photo_id)
    if entry.status != "approved":
        owner = current_user.is_authenticated and current_user.id == entry.user_id
        if not owner:
            from app.admin.security import valid_admin_session
            if not (valid_admin_session() and current_user.has_permission("reviews.manage")):
                abort(404)
    root = Path(current_app.config["UPLOAD_DIR"]).resolve()
    path = (root / entry.storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/jpeg", conditional=True)
    response.headers["Cache-Control"] = "no-store, private"
    return response

@community_bp.post("/worn-by-you/<int:photo_id>/withdraw")
@login_required
def withdraw(photo_id):
    entry = db.session.scalar(db.select(CustomerPhoto).where(CustomerPhoto.id == photo_id,
        CustomerPhoto.user_id == current_user.id).with_for_update())
    if entry is None:
        abort(404)
    entry.status = "withdrawn"
    db.session.commit()
    flash("Your photo is hidden from the gallery.", "success")
    return redirect(url_for("community.gallery", _anchor="your-photos"))
