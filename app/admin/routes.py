from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    flash,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Category,
    CartItem,
    Color,
    Inventory,
    InventoryMovement,
    Product,
    ProductImage,
    ProductVariant,
    Order,
    OrderItem,
    Size,
)
from app.security.decorators import permission_required
from app.security.validators import safe_slug, validate_money, safe_text


admin_bp = Blueprint("admin", __name__, template_folder="../templates")

ALLOWED_IMAGE_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


def _admin_product_listing():
    """Return the product workspace filters and matching catalogue items."""
    q = safe_text(request.args.get("q"), 120)
    status = request.args.get("status", "all")
    category_id = request.args.get("category", type=int)
    query = Product.query.filter(Product.is_archived.is_(False))

    if q:
        query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.slug.ilike(f"%{q}%")))
    if status == "live":
        query = query.filter(Product.is_active.is_(True))
    elif status == "hidden":
        query = query.filter(Product.is_active.is_(False))
    if category_id:
        query = query.filter(Product.category_id == category_id)

    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    pagination = query.order_by(Product.created_at.desc(), Product.id.desc()).paginate(
        page=max(1, request.args.get("page", 1, type=int)), per_page=24, error_out=False)
    return pagination.items, categories, q, status, category_id, pagination


def save_product_image(file_storage, product_id, sort_order):
    """
    Validate and securely store a product image.

    The original filename is never trusted.
    The actual image contents are validated using Pillow.
    """

    if not file_storage or not file_storage.filename:
        raise ValueError("Invalid image file.")

    if Path(file_storage.filename).suffix.lower() == ".mp4":
        from app.services.product_video import save_product_video
        return save_product_video(file_storage, product_id, sort_order)

    # Read file safely into memory.
    file_storage.stream.seek(0)
    data = file_storage.read()

    if not data:
        raise ValueError("Uploaded image is empty.")

    if len(data) > MAX_IMAGE_SIZE:
        raise ValueError("Each image must be 8 MB or smaller.")

    # Validate actual image contents rather than trusting extension/MIME.
    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        image = Image.open(__import__("io").BytesIO(data), formats=list(ALLOWED_IMAGE_FORMATS))

        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("The uploaded image has too many pixels.")
        image.verify()

        image = Image.open(__import__("io").BytesIO(data), formats=list(ALLOWED_IMAGE_FORMATS))

        image_format = image.format

        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise ValueError(
                "Only JPG, PNG, and WEBP images are allowed."
            )

        width, height = image.size

    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("The uploaded file is not a valid image.")

    if width < 1 or height < 1:
        raise ValueError("Invalid image dimensions.")

    # Never use the user's original filename for storage.
    extension = ALLOWED_IMAGE_FORMATS[image_format]

    random_name = f"{uuid4().hex}{extension}"

    relative_directory = Path("products") / str(product_id)
    absolute_directory = (
        Path(current_app.config["UPLOAD_DIR"]) / relative_directory
    )

    absolute_directory.mkdir(parents=True, exist_ok=True)

    storage_key = str(relative_directory / random_name).replace("\\", "/")
    absolute_path = Path(current_app.config["UPLOAD_DIR"]) / storage_key

    with open(absolute_path, "wb") as output:
        output.write(data)

    return {
        "storage_key": storage_key,
        "mime_type": {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }[image_format],
        "file_size": len(data),
        "width": width,
        "height": height,
        "sort_order": sort_order,
    }


@admin_bp.get("")
@admin_bp.get("/")
def legacy_dashboard():
    return redirect(url_for("admin.dashboard"))


@admin_bp.get("/products")
@login_required
@permission_required("products.view")
def products():
    products, categories, q, status, category_id, pagination = _admin_product_listing()
    return render_template(
        "admin/products.html",
        products=products,
        categories=categories,
        q=q,
        status=status,
        category_id=category_id,
        dashboard=False,
        pagination=pagination,
    )


def _discounted_price(base_price):
    """Calculate the selling price on the server; retain legacy sale-price posts."""
    if "discount_percent" not in request.form:
        return validate_money(request.form["sale_price"]) if request.form.get("sale_price") else None
    raw = safe_text(request.form.get("discount_percent"), 40)
    if not raw:
        return None
    try:
        percent = Decimal(raw)
    except InvalidOperation:
        raise ValueError("Enter a discount percentage between 0 and 100.") from None
    if not percent.is_finite() or not 0 <= percent <= 100:
        raise ValueError("Enter a discount percentage between 0 and 100.")
    if percent == 0:
        return None
    return (base_price * (Decimal("100") - percent) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@admin_bp.route("/products/create", methods=["GET", "POST"])
@login_required
@permission_required("products.create")
def create_product():

    categories = (
        Category.query
        .order_by(Category.sort_order, Category.name)
        .all()
    )

    if request.method == "POST":
        saved_image_paths = []

        try:
            name = safe_text(
                request.form.get("name"),
                255
            )

            slug = safe_slug(request.form.get("slug") or name or "product")
            if not request.form.get("slug"):
                base_slug = slug
                suffix = 2
                while Product.query.filter_by(slug=slug).first():
                    slug = f"{base_slug}-{suffix}"
                    suffix += 1

            description = safe_text(
                request.form.get("description"),
                10000
            )

            hide_price = _product_status() == "coming_soon" and request.form.get("hide_price") == "1"
            raw_price = request.form.get("base_price", "").strip()
            base_price = Decimal("0") if hide_price and not raw_price else validate_money(raw_price)
            sale_price = None if hide_price and not raw_price else _discounted_price(base_price)

            category_id = request.form.get(
                "category_id",
                type=int
            )

            if sale_price is not None and sale_price > base_price:
                raise ValueError(
                    "Sale price cannot exceed base price."
                )

            if not category_id or db.session.get(Category, category_id) is None:
                raise ValueError(
                    "Please select a category."
                )

            if not name:
                raise ValueError(
                    "Product name is required."
                )

            if not slug:
                raise ValueError(
                    "Product slug is required."
                )

            # Create product first so we have product.id.
            product = Product(
                product_status=_product_status(),
                hide_price=hide_price,
                name=name,
                slug=slug,
                description=description,
                base_price=base_price,
                sale_price=sale_price,
                category_id=category_id,
                is_active=request.form.get("is_active") == "1",
                is_featured=request.form.get("is_featured") == "1",
                is_new_arrival=request.form.get("is_new_arrival") == "1",
                is_bestseller=request.form.get("is_bestseller") == "1",
            )

            db.session.add(product)
            db.session.flush()

            if request.form.get("quick_listing") == "1":
                _add_product_variants(product)

            # Multiple product images.
            image_files = request.files.getlist("images")

            valid_files = [
                file
                for file in image_files
                if file and file.filename
            ]

            if not valid_files:
                raise ValueError(
                    "Please upload at least one product photo or video."
                )

            if len(valid_files) > 10:
                raise ValueError(
                    "You can upload a maximum of 10 photos or videos."
                )

            for index, file_storage in enumerate(valid_files):

                image_data = save_product_image(
                    file_storage,
                    product.id,
                    index
                )

                saved_image_paths.append(Path(current_app.config["UPLOAD_DIR"]) / image_data["storage_key"])

                product_image = ProductImage(
                    product_id=product.id,
                    storage_key=image_data["storage_key"],
                    mime_type=image_data["mime_type"],
                    file_size=image_data["file_size"],
                    width=image_data["width"],
                    height=image_data["height"],
                    sort_order=index,
                    is_primary=(index == 0 and not image_data["mime_type"].startswith("video/")),
                )

                db.session.add(product_image)

            db.session.commit()

            if request.form.get("quick_listing") == "1":
                flash("Product listed with photos, sizes and stock. You can add another product now.", "success")
                return redirect(url_for("admin.products"))
            flash("Product saved. Add its sizes, colours and opening stock below to finish setting up inventory.", "success")
            return redirect(url_for("admin.edit_product", product_id=product.id))

        except Exception as exc:

            db.session.rollback()
            for image_path in saved_image_paths:
                try:
                    image_path.unlink(missing_ok=True)
                except OSError:
                    current_app.logger.warning("Unable to remove an uncommitted product image.")

            return render_template(
                "admin/product_create.html",
                categories=categories,
                error=str(exc) if isinstance(exc, ValueError) else "Unable to save product. Check for a duplicate slug or SKU and try again.",
            ), 400

    return render_template(
        "admin/product_create.html",
        categories=categories,
    )

@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("products.update")
def edit_product(product_id):

    product = Product.query.filter_by(id=product_id, is_archived=False).first_or_404()

    categories = (
        Category.query
        .order_by(Category.sort_order, Category.name)
        .all()
    )

    if request.method == "POST":

        try:
            name = safe_text(
                request.form.get("name"),
                255
            )

            slug = safe_slug(
                request.form.get("slug")
            )

            description = safe_text(
                request.form.get("description"),
                10000
            )

            hide_price = _product_status() == "coming_soon" and request.form.get("hide_price") == "1"
            raw_price = request.form.get("base_price", "").strip()
            base_price = Decimal("0") if hide_price and not raw_price else validate_money(raw_price)
            sale_price = None if hide_price and not raw_price else _discounted_price(base_price)

            category_id = request.form.get(
                "category_id",
                type=int
            )

            if not name:
                raise ValueError(
                    "Product name is required."
                )

            if not slug:
                raise ValueError(
                    "Product slug is required."
                )

            if not category_id:
                raise ValueError(
                    "Please select a category."
                )

            if sale_price is not None and sale_price > base_price:
                raise ValueError(
                    "Sale price cannot exceed base price."
                )

            # Prevent duplicate slugs.
            existing_product = (
                Product.query
                .filter(
                    Product.slug == slug,
                    Product.id != product.id
                )
                .first()
            )

            if existing_product:
                raise ValueError(
                    "That product slug is already in use."
                )

            # Update product information.
            product.product_status = _product_status(product.product_status)
            product.hide_price = hide_price
            product.name = name
            product.slug = slug
            product.description = description
            if "seo_title" in request.form:
                product.seo_title = safe_text(request.form.get("seo_title"), 255) or None
            if "seo_description" in request.form:
                product.seo_description = safe_text(request.form.get("seo_description"), 500) or None
            product.base_price = base_price
            product.sale_price = sale_price
            product.category_id = category_id
            product.is_active = request.form.get("is_active") == "1"
            product.is_featured = request.form.get("is_featured") == "1"
            product.is_new_arrival = request.form.get("is_new_arrival") == "1"
            product.is_bestseller = request.form.get("is_bestseller") == "1"

            # -------------------------------------------------
            # ADDITIONAL PRODUCT IMAGES
            # -------------------------------------------------

            existing_images_count = len(product.images)

            image_files = request.files.getlist("images")

            valid_files = [
                file
                for file in image_files
                if file and file.filename
            ]

            total_images = existing_images_count + len(valid_files)

            if total_images > 10:
                raise ValueError(
                    "A product can have a maximum of 10 photos or videos."
                )

            next_sort_order = (
                max(
                    [image.sort_order for image in product.images],
                    default=-1
                ) + 1
            )

            for index, file_storage in enumerate(valid_files):

                image_data = save_product_image(
                    file_storage,
                    product.id,
                    next_sort_order + index
                )

                product_image = ProductImage(
                    product_id=product.id,
                    storage_key=image_data["storage_key"],
                    mime_type=image_data["mime_type"],
                    file_size=image_data["file_size"],
                    width=image_data["width"],
                    height=image_data["height"],
                    sort_order=next_sort_order + index,
                    is_primary=False,
                )

                db.session.add(product_image)

            db.session.commit()

            return redirect(
                url_for(
                    "admin.edit_product",
                    product_id=product.id
                )
            )

        except Exception as exc:

            db.session.rollback()

            return render_template(
                "admin/product_form.html",
                product=product,
                categories=categories,
                error=str(exc) if isinstance(exc, ValueError) else "Unable to save product. Check for a duplicate slug or SKU and try again.",
                edit_mode=True,
            ), 400

    return render_template(
        "admin/product_form.html",
        product=product,
        categories=categories,
        edit_mode=True,
    )


@admin_bp.post("/products/<int:product_id>/delete")
@login_required
@permission_required("products.delete")
def delete_product(product_id):
    """Delete an unsold product, or safely archive one with order history."""
    product = Product.query.filter_by(id=product_id, is_archived=False).first_or_404()

    has_order_history = (
        OrderItem.query
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .filter(ProductVariant.product_id == product.id)
        .first()
        is not None
    )
    has_stock_history = db.session.scalar(db.select(InventoryMovement.id).join(
        ProductVariant, ProductVariant.id == InventoryMovement.variant_id).where(
        ProductVariant.product_id == product.id).limit(1)) is not None
    if has_order_history or has_stock_history:
        product.is_active = False
        product.is_archived = True
        db.session.commit()
        flash("Product removed from your catalogue. Its past order and inventory records are retained.", "success")
        return redirect(url_for("admin.products"))

    image_paths = [Path(current_app.config["UPLOAD_DIR"]) / image.storage_key for image in product.images]
    cart_items = (
        CartItem.query
        .join(ProductVariant, ProductVariant.id == CartItem.variant_id)
        .filter(ProductVariant.product_id == product.id)
        .all()
    )
    for item in cart_items:
        db.session.delete(item)
    db.session.delete(product)
    db.session.commit()

    for image_path in image_paths:
        if not image_path.resolve().is_relative_to(Path(current_app.config["UPLOAD_DIR"]).resolve()):
            continue
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass
    return redirect(url_for("admin.products"))


def _add_product_variants(product):
    """Add selected sizes and audited stock within the caller's transaction."""
    selected_sizes = request.form.getlist("sizes")
    if selected_sizes:
        allowed = {"XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "One size"}
        if any(value not in allowed for value in selected_sizes):
            raise ValueError("Choose sizes from the available buttons.")
    size_names = selected_sizes or [safe_text(value, 30) for value in request.form.get("size_name", "").split(",") if value.strip()]
    custom_size = safe_text(request.form.get("custom_size"), 30)
    if custom_size:
        size_names.append(custom_size)
    size_names = list(dict.fromkeys(size_names))
    color_name = safe_text(request.form.get("color_name"), 50)
    # Keep older form submissions compatible; the new UI never asks for a SKU.
    sku = safe_text(request.form.get("sku"), 80).upper() if not selected_sizes and not custom_size else ""
    quantity = request.form.get("quantity", type=int)
    price_override = request.form.get("price_override")
    if not size_names or len(size_names) > 20 or not color_name:
        raise ValueError("Select at least one size and enter a colour.")
    if quantity is None or not 0 <= quantity <= 1_000_000:
        raise ValueError("Opening stock must be between 0 and 1,000,000 per size.")
    price = validate_money(price_override) if price_override else None
    color = Color.query.filter_by(name=color_name).first()
    if not color:
        color = Color(name=color_name)
        db.session.add(color)
        db.session.flush()
    for size_name in size_names:
        option_sku = (sku if len(size_names) == 1 else f"{sku}-{safe_slug(size_name).upper()}") if sku else f"ARD-{product.id}-{uuid4().hex[:16].upper()}"
        if len(option_sku) > 100 or ProductVariant.query.filter_by(sku=option_sku).first():
            raise ValueError("One of these SKUs already exists or is too long. Use a different prefix.")
        size = Size.query.filter_by(name=size_name).first()
        if not size:
            size = Size(name=size_name)
            db.session.add(size)
            db.session.flush()
        if ProductVariant.query.filter_by(product_id=product.id, size_id=size.id, color_id=color.id).first():
            raise ValueError(f"{size_name} / {color_name} already exists. Update its stock above instead.")
        variant = ProductVariant(product_id=product.id, size_id=size.id, color_id=color.id,
            sku=option_sku, price_override=price, is_active=True)
        db.session.add(variant)
        db.session.flush()
        db.session.add(Inventory(variant_id=variant.id, quantity=quantity, reserved_quantity=0))
        db.session.add(InventoryMovement(variant_id=variant.id, quantity_delta=quantity,
            reason="opening_stock", created_by=current_user.id, reference=f"product:{product.id}"))


@admin_bp.post("/products/<int:product_id>/variants")
@login_required
@permission_required("products.update")
def create_variant(product_id):
    """Create a sellable SKU and its opening inventory balance."""
    product = Product.query.filter_by(id=product_id, is_archived=False).first_or_404()
    try:
        _add_product_variants(product)
        db.session.commit()
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        return _variant_error(product, str(exc) if isinstance(exc, ValueError) else "That size, colour or SKU already exists. Refresh and try again.")

    return redirect(url_for("admin.edit_product", product_id=product.id))


@admin_bp.post("/products/<int:product_id>/variants/<int:variant_id>")
@login_required
@permission_required("products.update")
def update_variant(product_id, variant_id):
    product = Product.query.filter_by(id=product_id, is_archived=False).first_or_404()
    variant = ProductVariant.query.filter_by(id=variant_id, product_id=product.id).with_for_update().first_or_404()
    stock = db.session.scalar(db.select(Inventory).where(Inventory.variant_id == variant.id)
        .with_for_update().execution_options(populate_existing=True))
    variant.inventory = stock
    try:
        quantity = request.form.get("quantity", type=int)
        if quantity is None or quantity < 0 or quantity > 1_000_000:
            raise ValueError("Stock quantity must be between 0 and 1,000,000.")
        if variant.inventory and quantity < variant.inventory.reserved_quantity:
            raise ValueError("Stock cannot be lower than quantity reserved for orders.")
        if not variant.inventory:
            variant.inventory = Inventory(quantity=0, reserved_quantity=0)
        delta = quantity - variant.inventory.quantity
        variant.inventory.quantity = quantity
        variant.is_active = request.form.get("is_active") == "1"
        if delta:
            db.session.add(InventoryMovement(
                variant_id=variant.id,
                quantity_delta=delta,
                reason="admin_stock_adjustment",
                created_by=current_user.id,
                reference=f"product:{product.id}",
            ))
        db.session.commit()
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        return _variant_error(product, str(exc) if isinstance(exc, ValueError) else "That size, colour or SKU already exists. Refresh and try again.")
    return redirect(url_for("admin.edit_product", product_id=product.id))


def _variant_error(product, error):
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template(
        "admin/product_form.html",
        product=product,
        categories=categories,
        error=error,
        edit_mode=True,
    ), 400

@admin_bp.post("/products/<int:product_id>/images/<int:image_id>/primary")
@login_required
@permission_required("products.update")
def set_primary_image(product_id, image_id):

    product = Product.query.get_or_404(product_id)

    image = ProductImage.query.filter_by(
        id=image_id,
        product_id=product_id
    ).first_or_404()

    if image.mime_type.startswith("video/"):
        flash("Choose a photo as the product cover. Videos appear in the product gallery.", "error")
        return redirect(url_for("admin.edit_product", product_id=product.id))

    # Remove primary status from all images
    for product_image in product.images:
        product_image.is_primary = False

    # Make selected image primary
    image.is_primary = True

    db.session.commit()

    return redirect(
        url_for(
            "admin.edit_product",
            product_id=product.id
        )
    )


@admin_bp.post("/products/<int:product_id>/images/<int:image_id>/delete")
@login_required
@permission_required("products.update")
def delete_product_image(product_id, image_id):

    product = Product.query.get_or_404(product_id)

    image = ProductImage.query.filter_by(
        id=image_id,
        product_id=product_id
    ).first_or_404()

    # Don't allow deleting the last product image.
    if len(product.images) <= 1:
        return render_template(
            "admin/product_form.html",
            product=product,
            categories=(
                Category.query
                .filter_by(is_active=True)
                .order_by(Category.sort_order, Category.name)
                .all()
            ),
            error="A product must have at least one image.",
            edit_mode=True,
        ), 400

    image_path = (
        Path(current_app.config["UPLOAD_DIR"])
        / image.storage_key
    )

    was_primary = image.is_primary

    db.session.delete(image)
    db.session.flush()

    # If the deleted image was primary,
    # automatically make the first remaining image primary.
    if was_primary:

        remaining_images = (
            ProductImage.query
            .filter_by(product_id=product.id)
            .order_by(ProductImage.sort_order, ProductImage.id)
            .all()
        )

        if remaining_images:
            remaining_images[0].is_primary = True

    db.session.commit()

    # Delete the physical file after database deletion.
    try:
        if image_path.is_file():
            image_path.unlink()
    except OSError:
        pass

    return redirect(
        url_for(
            "admin.edit_product",
            product_id=product.id
        )
    )

    


@admin_bp.get("/orders")
@login_required
@permission_required("orders.manage")
def orders():
    selected_status = request.args.get("status", "").title()
    if selected_status not in {"", "Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"}:
        abort(400)
    q = request.args.get("q", "").strip()[:200]
    query = Order.query
    if selected_status:
        query = query.filter_by(status=selected_status)
    if q:
        query = query.filter(or_(Order.order_number.icontains(q, autoescape=True), Order.shipping_name.icontains(q, autoescape=True)))
    pagination = query.order_by(Order.created_at.desc(), Order.id.desc()).paginate(per_page=30)
    return render_template("admin/orders.html", pagination=pagination, selected_status=selected_status, q=q)



@admin_bp.get("/orders/<order_number>")
@login_required
@permission_required("orders.manage")
def order_detail(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    from app.models import AuditLog
    history = AuditLog.query.filter_by(entity_type="order", entity_id=str(order.id)).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()
    return render_template("admin/order_detail.html", order=order, history=history)


@admin_bp.post("/orders/<order_number>/confirm")
@login_required
@permission_required("orders.manage")
def confirm_order(order_number):
    from app.services.order_status import change_status
    try:
        changed = change_status(order_number, "Confirmed", current_user.id)
        flash("Order confirmed. Please call the customer shortly." if changed else "This order is already confirmed.", "success" if changed else "info")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin.order_detail", order_number=order_number))


@admin_bp.post("/orders/<order_number>/status")
@login_required
@permission_required("orders.manage")
def update_order_status(order_number):
    from app.services.order_status import change_status
    target = request.form.get("status")
    if target not in {"Shipped", "Delivered", "Cancelled"}:
        abort(400)
    try:
        changed = change_status(order_number, target, current_user.id, request.form.get("reason", ""))
        flash(f"Order marked {target.lower()}." if changed else "This update has already been applied.", "success" if changed else "info")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin.order_detail", order_number=order_number))


@admin_bp.post("/orders/<order_number>/retry-alerts")
@login_required
@permission_required("orders.manage")
def retry_order_alerts(order_number):
    from app.services.order_notifications import dispatch_order_alerts
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    dispatch_order_alerts(order.id)
    flash("Alert processing finished. Check each channel's status below.", "info")
    return redirect(url_for("admin.order_detail", order_number=order.order_number))


@admin_bp.post("/orders/<order_number>/payment-received")
@login_required
@permission_required("orders.manage")
def record_order_payment(order_number):
    from app.services.order_status import record_cod_received
    try:
        changed = record_cod_received(order_number, current_user.id, request.form.get("received") == "yes")
        flash("Cash-on-delivery payment recorded as received." if changed else "Payment has already been recorded.", "success" if changed else "info")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin.order_detail", order_number=order_number))


@admin_bp.get("/categories")
@login_required
@permission_required("products.update")
def categories():
    from sqlalchemy import func
    rows = db.session.execute(db.select(Category, func.count(Product.id)).outerjoin(
        Product, Product.category_id == Category.id).group_by(Category.id)
        .order_by(Category.sort_order, Category.name)).all()
    return render_template("admin/categories.html", rows=rows)


@admin_bp.route("/categories/create", methods=["GET", "POST"])
@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("products.update")
def edit_category(category_id=None):
    from sqlalchemy.exc import IntegrityError
    from app.models import AuditLog
    category = db.get_or_404(Category, category_id) if category_id is not None else None
    if request.method == "POST":
        try:
            name = safe_text(request.form.get("name"), 120)
            if not name:
                raise ValueError("Enter a collection name.")
            slug = safe_slug(safe_text(request.form.get("slug") or name, 140))
            description = safe_text(request.form.get("description"), 3000)
            sort_order = request.form.get("sort_order", type=int)
            if sort_order is None or not 0 <= sort_order <= 9999:
                raise ValueError("Display order must be a number from 0 to 9999.")
            duplicate = Category.query.filter(Category.slug == slug)
            if category:
                duplicate = duplicate.filter(Category.id != category.id)
            if duplicate.first():
                raise ValueError("That URL slug is already used by another collection.")
            created = category is None
            if created:
                category = Category()
                db.session.add(category)
            category.name, category.slug = name, slug
            category.description = description
            category.sort_order = sort_order
            category.is_active = request.form.get("is_active") == "1"
            db.session.flush()
            db.session.add(AuditLog(actor_user_id=current_user.id,
                action="category.created" if created else "category.updated",
                entity_type="category", entity_id=str(category.id)))
            db.session.commit()
            flash("Collection saved.", "success")
            return redirect(url_for("admin.categories"))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "That collection could not be saved. Its URL slug may already be in use.", "error")
    return render_template("admin/category_form.html", category=category)


from app.admin.security import protect_admin
from app.admin.auth import register_auth
from app.admin.management import register_management
admin_bp.before_request(protect_admin)
register_auth(admin_bp)
register_management(admin_bp)
from app.admin.storefront import register_storefront
register_storefront(admin_bp)
from app.admin.bills import register_bills
register_bills(admin_bp)


@admin_bp.errorhandler(ValueError)
def invalid_admin_input(error):
    db.session.rollback()
    return render_template("admin/error.html", code=400, message="Check your input and try again."), 400


def _product_status(default="available"):
    value = request.form.get("product_status", default)
    if value not in Product.STATUSES:
        raise ValueError("Choose a valid product status.")
    return value


@admin_bp.get("/interests")
@permission_required("customers.manage")
def interests():
    from app.models import ProductInterest
    from sqlalchemy import func
    query = db.select(ProductInterest).order_by(ProductInterest.created_at.desc(), ProductInterest.id.desc())
    product_id = request.args.get("product_id", type=int)
    if product_id:
        query = query.where(ProductInterest.product_id == product_id)
    pagination = db.paginate(query, page=max(1, request.args.get("page", 1, type=int)), per_page=30, error_out=False)
    counts = db.session.execute(db.select(Product.id, Product.name, func.count(ProductInterest.id))
        .join(ProductInterest).group_by(Product.id, Product.name).order_by(Product.name)).all()
    return render_template("admin/interests.html", pagination=pagination, counts=counts,
        total=sum(row[2] for row in counts), product_id=product_id)


@admin_bp.get("/worn-by-you")
@permission_required("reviews.manage")
def worn_by_you():
    from app.models import CustomerPhoto
    from sqlalchemy.orm import selectinload
    status = request.args.get("status", "pending")
    if status not in {"pending", "approved", "rejected", "withdrawn"}:
        abort(400)
    pagination = db.paginate(db.select(CustomerPhoto).where(CustomerPhoto.status == status)
        .options(selectinload(CustomerPhoto.customer), selectinload(CustomerPhoto.order_item))
        .order_by(CustomerPhoto.created_at.desc(), CustomerPhoto.id.desc()),
        page=max(1, request.args.get("page", 1, type=int)), per_page=24, error_out=False)
    return render_template("admin/customer_photos.html", pagination=pagination, status=status)


@admin_bp.post("/worn-by-you/<int:photo_id>")
@permission_required("reviews.manage")
def moderate_customer_photo(photo_id):
    from app.models import CustomerPhoto
    from app.admin.management import audit
    entry = db.session.scalar(db.select(CustomerPhoto).where(CustomerPhoto.id == photo_id).with_for_update())
    if entry is None:
        abort(404)
    action = request.form.get("action")
    if action not in {"approve", "reject"}:
        abort(400)
    if entry.status == "withdrawn":
        abort(409)
    entry.status = "approved" if action == "approve" else "rejected"
    audit("customer_photo." + entry.status, "customer_photo", entry.id)
    db.session.commit()
    flash("Customer photo updated.", "success")
    return redirect(url_for("admin.worn_by_you"))


from app.admin.fulfilment import register_fulfilment
register_fulfilment(admin_bp)
