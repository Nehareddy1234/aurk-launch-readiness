from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    send_file,
)
from sqlalchemy import func, or_, select

from sqlalchemy.orm import selectinload
from app.services.catalog import price_bounds, prepare_storefront_products, storefront_price_expression
from app.extensions import db, limiter
from app.models import Category, Product, ProductImage, ProductVariant


products_bp = Blueprint("products", __name__)


@products_bp.get("/shop")
def shop():
    stmt = select(Product).where(Product.is_active.is_(True), Product.is_archived.is_(False)).options(
        selectinload(Product.images), selectinload(Product.category),
        selectinload(Product.variants).selectinload(ProductVariant.inventory),
        selectinload(Product.variants).selectinload(ProductVariant.size),
        selectinload(Product.variants).selectinload(ProductVariant.color))

    q = (request.args.get("q") or "").strip()
    category_slug = (request.args.get("category") or "").strip()
    sort = request.args.get("sort", "newest")

    if q:
        like = f"%{q}%"

        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.description.ilike(like),
            )
        )

    category = None
    if category_slug:
        category = (
            Category.query
            .filter_by(
                slug=category_slug,
                is_active=True
            )
            .first_or_404()
        )

        stmt = stmt.where(
            Product.category_id == category.id
        )

    if sort not in {"price_asc", "price_desc", "featured", "newest"}:
        sort = "newest"

    if sort == "price_asc":
        stmt = stmt.order_by(storefront_price_expression().asc(), Product.id.asc())

    elif sort == "price_desc":
        stmt = stmt.order_by(storefront_price_expression().desc(), Product.id.asc())

    elif sort == "featured":
        stmt = stmt.order_by(
            Product.is_featured.desc(),
            Product.created_at.desc(),
        )

    elif sort == "newest":
        stmt = stmt.order_by(
            Product.created_at.desc()
        )

    page = max(
        request.args.get("page", 1, type=int),
        1
    )

    pagination = db.paginate(
        stmt,
        page=page,
        per_page=48,
        error_out=False,
    )

    prepare_storefront_products(pagination.items)

    categories = (
        Category.query
        .filter_by(is_active=True)
        .order_by(
            Category.sort_order,
            Category.name
        )
        .all()
    )

    return render_template(
        "shop/shop.html",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
        q=q,
        category_slug=category_slug,
        selected_category=category,
    )


@products_bp.get("/product/<slug>")
def detail(slug):
    product = (
        Product.query
        .filter_by(
            slug=slug,
            is_active=True,
            is_archived=False
        )
        .first()
    )

    if not product:
        abort(404)

    variants = [v for v in product.variants if v.is_active]
    available_variants = [v for v in variants if v.inventory and v.inventory.quantity > v.inventory.reserved_quantity]
    low, high = price_bounds(product)
    selected_variant = None
    if "variant" in request.args:
        selected_variant = next((v for v in variants if v.id == request.args.get("variant", type=int)), None)
        if selected_variant is None:
            abort(404)
        low = high = selected_variant.price_override if selected_variant.price_override is not None else product.current_price
    return render_template("shop/product.html", product=product, variants=variants,
        available_variants=available_variants, min_price=low, max_price=high, selected_variant=selected_variant)


@products_bp.get("/product-image/<int:image_id>")
def product_image(image_id):
    """
    Securely serve product images.

    Only images belonging to active products are publicly
    accessible.
    """

    image = (
        ProductImage.query
        .join(Product, Product.id == ProductImage.product_id)
        .filter(
            ProductImage.id == image_id,
            Product.is_active.is_(True),
            Product.is_archived.is_(False),
        )
        .first_or_404()
    )

    upload_dir = (
        Path(current_app.config["UPLOAD_DIR"])
        .resolve()
    )

    image_path = (
        upload_dir / image.storage_key
    ).resolve()

    # Prevent path traversal.
    try:
        image_path.relative_to(upload_dir)
    except ValueError:
        abort(404)

    if not image_path.is_file():
        abort(404)

    return send_file(
        image_path,
        mimetype=image.mime_type,
        max_age=3600,
    )


@products_bp.get("/search")
def search():
    return shop()


@products_bp.app_context_processor
def interest_context():
    import secrets
    from flask import session
    from flask_login import current_user
    from app.models import ProductInterest
    if request.endpoint not in {"products.shop", "products.search", "products.detail", "main.home"}:
        return {}
    if not current_user.is_authenticated:
        session.setdefault("interest_guest", secrets.token_hex(24))
    key = f"user:{current_user.id}" if current_user.is_authenticated else f"guest:{session['interest_guest']}"
    ids = set(db.session.scalars(db.select(ProductInterest.product_id).where(ProductInterest.identity_key == key)))
    return {"registered_interest_ids": ids}


@products_bp.post("/products/<int:product_id>/interest")
@limiter.limit("10 per minute;60 per hour")
def register_interest(product_id):
    from flask import jsonify, session, flash, redirect, url_for
    from flask_login import current_user
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from app.models import ProductInterest
    from app.services.product_interests import notify_interest

    def response(message, status=200):
        if request.accept_mimetypes.best == "application/json":
            return jsonify(message=message, success=status < 400), status
        flash(message, "success" if status < 400 else "error")
        return redirect(url_for("products.detail", slug=product.slug) if product else url_for("products.shop"))

    product = db.session.scalar(db.select(Product).where(Product.id == product_id,
        Product.is_active.is_(True), Product.is_archived.is_(False)).with_for_update())
    if not product:
        return response("This product could not be found.", 404)
    if product.product_status not in {"coming_soon", "out_of_stock"}:
        return response("This product is available. You can add it to your bag.", 409)
    if product.product_status == "coming_soon" and not current_user.is_authenticated:
        login_url = url_for("auth.login", next=url_for("products.detail", slug=product.slug))
        if request.accept_mimetypes.best == "application/json":
            return jsonify(success=False, message="Sign in or create an account to join the list.", login_url=login_url), 401
        return redirect(login_url)
    if current_user.is_authenticated:
        key = f"user:{current_user.id}"
        customer_id = current_user.id
        name = f"{current_user.first_name} {current_user.last_name}".strip()[:200]
        email, phone = current_user.email, current_user.phone
    else:
        token = session.get("interest_guest")
        if not token:
            return response("Please reload the product page and try again.", 400)
        key, customer_id, name, email, phone = f"guest:{token}", None, None, None, None
    message = "Thanks! We've recorded your interest in this product."
    if db.session.scalar(db.select(ProductInterest.id).where(
        ProductInterest.product_id == product.id, ProductInterest.identity_key == key)):
        db.session.rollback()
        return response(message)
    interest = ProductInterest(product_id=product.id, identity_key=key, customer_id=customer_id,
        customer_name=name, customer_email=email, customer_phone=phone, product_status=product.product_status)
    try:
        db.session.add(interest)
        db.session.flush()
        interest_id = interest.id
        if product.product_status == "coming_soon" and current_user.is_authenticated:
            from app.services.customer_emails import queue_interest_acknowledgement
            queue_interest_acknowledgement(interest, current_user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.scalar(db.select(ProductInterest.id).where(
            ProductInterest.product_id == product_id, ProductInterest.identity_key == key)):
            return response(message)
        current_app.logger.warning("Unable to save product interest.")
        return response("Something went wrong. Please try again.", 503)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Unable to save product interest.")
        return response("Something went wrong. Please try again.", 503)
    notify_interest(interest_id)
    return response(message)
