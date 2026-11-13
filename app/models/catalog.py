from datetime import datetime, timezone

from app.extensions import db
from app.models.types import BigIntPrimaryKey


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    slug = db.Column(
        db.String(140),
        unique=True,
        nullable=False,
        index=True
    )

    description = db.Column(
        db.Text
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    sort_order = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    products = db.relationship(
        "Product",
        back_populates="category"
    )


class Product(db.Model):
    __tablename__ = "products"
    STATUSES = {"available": "Available", "coming_soon": "Coming Soon", "out_of_stock": "Out of Stock"}
    product_status = db.Column(db.String(20), nullable=False, default="available", server_default="available")
    __table_args__ = (db.CheckConstraint("product_status IN ('available', 'coming_soon', 'out_of_stock')", name="ck_product_status"),)
    interests = db.relationship("ProductInterest", back_populates="product", cascade="all, delete-orphan")

    hide_price = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    @property
    def show_price(self):
        return not (self.product_status == "coming_soon" and self.hide_price)

    @property
    def discount_percent(self):
        if self.sale_price is None or not self.base_price:
            return ""
        return (self.base_price - self.sale_price) * 100 / self.base_price

    @property
    def is_purchasable(self):
        return self.is_active and not self.is_archived and self.product_status == "available"

    @property
    def status_label(self):
        return self.STATUSES[self.product_status]

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    category_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "categories.id",
            ondelete="SET NULL"
        ),
        index=True
    )

    name = db.Column(
        db.String(255),
        nullable=False
    )

    slug = db.Column(
        db.String(280),
        unique=True,
        nullable=False,
        index=True
    )

    description = db.Column(
        db.Text,
        nullable=False,
        default=""
    )

    base_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    sale_price = db.Column(
        db.Numeric(12, 2)
    )

    is_archived = db.Column(db.Boolean, nullable=False, default=False, server_default="0", index=True)

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
        index=True
    )

    is_featured = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    is_new_arrival = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    is_bestseller = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True
    )

    seo_title = db.Column(
        db.String(255)
    )

    seo_description = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ---------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------

    category = db.relationship(
        "Category",
        back_populates="products"
    )

    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order"
    )

    variants = db.relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    specifications = db.relationship(
        "ProductSpecification",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    tags = db.relationship(
        "Tag",
        secondary="product_tags",
        back_populates="products"
    )

    # ---------------------------------------------------------
    # PRICE
    # ---------------------------------------------------------

    @property
    def current_price(self):
        """
        Return the sale price when available.
        Otherwise return the regular/base price.
        """

        return (
            self.sale_price
            if self.sale_price is not None
            else self.base_price
        )

    # ---------------------------------------------------------
    # PRIMARY IMAGE
    # ---------------------------------------------------------

    @property
    def primary_image(self):
        """
        Return the image explicitly marked as primary.

        If no image is marked as primary, fall back to
        the first image according to sort_order.

        If the product has no images, return None.
        """

        photos = [image for image in self.images if not image.mime_type.startswith("video/")]
        return next((image for image in photos if image.is_primary), photos[0] if photos else None)






class Size(db.Model):
    __tablename__ = "sizes"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    name = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )


class Color(db.Model):
    __tablename__ = "colors"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    name = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    hex_code = db.Column(
        db.String(7)
    )


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "products.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    size_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "sizes.id",
            ondelete="RESTRICT"
        ),
        nullable=False
    )

    color_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "colors.id",
            ondelete="RESTRICT"
        ),
        nullable=False
    )

    sku = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    price_override = db.Column(
        db.Numeric(12, 2)
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    product = db.relationship(
        "Product",
        back_populates="variants"
    )

    size = db.relationship(
        "Size"
    )

    color = db.relationship(
        "Color"
    )

    inventory = db.relationship(
        "Inventory",
        back_populates="variant",
        uselist=False,
        cascade="all, delete-orphan"
    )


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "products.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    storage_key = db.Column(
        db.String(500),
        unique=True,
        nullable=False
    )

    mime_type = db.Column(
        db.String(100),
        nullable=False
    )

    file_size = db.Column(
        db.BigInteger,
        nullable=False
    )

    width = db.Column(
        db.Integer,
        nullable=False
    )

    height = db.Column(
        db.Integer,
        nullable=False
    )

    sort_order = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    is_primary = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    product = db.relationship(
        "Product",
        back_populates="images"
    )


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    name = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    products = db.relationship(
        "Product",
        secondary="product_tags",
        back_populates="tags"
    )


class ProductTag(db.Model):
    __tablename__ = "product_tags"

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "products.id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )

    tag_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "tags.id",
            ondelete="CASCADE"
        ),
        primary_key=True
    )


class ProductSpecification(db.Model):
    __tablename__ = "product_specifications"

    id = db.Column(
        BigIntPrimaryKey,
        primary_key=True
    )

    product_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "products.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    value = db.Column(
        db.String(500),
        nullable=False
    )

    product = db.relationship(
        "Product",
        back_populates="specifications"
    )
