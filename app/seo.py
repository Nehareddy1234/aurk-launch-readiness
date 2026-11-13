"""Public search metadata. All absolute URLs use the configured origin, never Host."""
from math import ceil
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring
import re

from flask import Blueprint, abort, current_app, request, url_for, Response
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import Product, ProductVariant, Category

seo_bp = Blueprint("seo", __name__)
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
GOOGLE_NS = "http://base.google.com/ns/1.0"


def origin():
    value = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment:
        return ""
    return value


def absolute(endpoint, **values):
    return origin() + url_for(endpoint, **values)


def public_products():
    return Product.query.filter_by(is_active=True, is_archived=False)


def summary(value, limit=160):
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def metadata(product=None, category=None):
    title = "AURK | Indian Streetwear"
    description = "Discover AURK streetwear, explore the collection and shop with cash on delivery in India."
    pages = {
        "main.home": ("AURK | More than fits", "Explore AURK Indian streetwear, discover new drops and choose your next fit. Cash on delivery is available at serviceable addresses in India."),
        "main.about": ("About AURK | Indian Streetwear", "Meet AURK: Indian streetwear inspired by people, places and stories. Learn about the brand and explore the collection."),
        "main.contact": ("Contact AURK | Order and Product Support", "Contact AURK by email, phone or WhatsApp for product questions, delivery updates, returns and help with your order."),
        "main.shipping": ("Shipping and COD Delivery | AURK", "Read AURK delivery estimates, free-shipping terms and cash-on-delivery coverage checks for serviceable addresses in India."),
        "main.returns": ("Returns and Exchanges | AURK", "Find out how to request an AURK return or exchange within five days of delivery, including eligibility and return-shipping information."),
        "main.refund_policy": ("Refund Policy | AURK", "Understand AURK refund requests, inspection and UPI or cash refunds for eligible cash-on-delivery purchases."),
        "main.privacy": ("Privacy and Cookies | AURK", "Learn how AURK uses account, order and delivery information, essential cookies, optional Google sign-in and submitted community photos."),
        "main.terms": ("Terms of Use and Sale | AURK", "Read AURK terms for using the store, placing cash-on-delivery orders, product availability, cancellations and customer support."),
        "community.gallery": ("Worn by You | AURK Community", "Explore customer photos shared with AURK. Published photos are reviewed, and customers can manage submissions from their account."),
    }
    title, description = pages.get(request.endpoint, (title, description))
    image = absolute("static", filename="images/brand/hero-small.webp")
    path = request.path
    private = request.blueprint in {"auth", "cart", "checkout", "orders", "admin", "api"}
    canonical = origin() + path
    data = []
    if product:
        title = product.seo_title or f"{product.name} | AURK"
        description = product.seo_description or summary(product.description) or f"Explore {product.name} from AURK. Choose your size and colour and check current availability."
        canonical = absolute("products.detail", slug=product.slug)
        if product.primary_image:
            image = absolute("products.product_image", image_id=product.primary_image.id)
        if origin():
            data = product_schema(product)
    elif request.endpoint in {"products.shop", "products.search"}:
        page = max(1, request.args.get("page", 1, type=int))
        args = {"category": category.slug} if category else {}
        if page > 1:
            args["page"] = page
        canonical = absolute("products.shop", **args)
        title = f"{category.name} | AURK" if category else "Shop Streetwear | AURK"
        if page > 1:
            title += f" - Page {page}"
        description = summary(category.description) if category and category.description else description
        private = bool(request.args.get("q")) or request.endpoint == "products.search" or bool(request.args.get("sort"))
    if request.endpoint == "main.home" and origin():
        data = [{"@context": "https://schema.org", "@type": "Organization", "@id": origin()+"/#organization",
                 "name": "AURK", "url": origin(), "logo": absolute("static", filename="images/brand/header-logo.png"),
                 "email": current_app.config["CUSTOMER_SUPPORT_EMAIL"]}]
    return dict(title=title, description=description, canonical=canonical if origin() and not private else "",
                image=image if origin() else "", structured=data,
                noindex=private or not current_app.config["SEARCH_INDEXING_ENABLED"], type="product" if product else "website")


def product_schema(product):
    canonical = absolute("products.detail", slug=product.slug)
    images = [absolute("products.product_image", image_id=i.id) for i in product.images if not i.mime_type.startswith("video/")]
    group = {"@context": "https://schema.org", "@type": "ProductGroup", "@id": canonical+"#product",
             "name": product.name, "description": product.description or product.name,
             "url": canonical, "productGroupID": str(product.id), "brand": {"@type": "Brand", "name": "AURK"},
             "variesBy": ["https://schema.org/size", "https://schema.org/color"], "hasVariant": []}
    if images:
        group["image"] = images
    for variant in product.variants:
        if not variant.is_active:
            continue
        url = absolute("products.detail", slug=product.slug, variant=variant.id)
        item = {"@type": "Product", "name": product.name, "sku": variant.sku, "url": url,
                "size": variant.size.name if variant.size else "One size",
                "color": variant.color.name if variant.color else "Default",
                "brand": {"@type": "Brand", "name": "AURK"}}
        if images:
            item["image"] = images
        price = variant.price_override if variant.price_override is not None else product.current_price
        if not product.hide_price and price is not None and price > 0 and product.product_status != "coming_soon":
            stocked = product.is_purchasable and variant.inventory and variant.inventory.quantity > variant.inventory.reserved_quantity
            item["offers"] = {"@type": "Offer", "url": url, "priceCurrency": "INR", "price": f"{price:.2f}",
                              "availability": "https://schema.org/InStock" if stocked else "https://schema.org/OutOfStock",
                              "itemCondition": "https://schema.org/NewCondition"}
        group["hasVariant"].append(item)
    breadcrumbs = [{"@type": "ListItem", "position": 1, "name": "Shop", "item": absolute("products.shop")},
                   {"@type": "ListItem", "position": 2, "name": product.name, "item": canonical}]
    return [group, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": breadcrumbs}]


def xml_response(root):
    response = Response(tostring(root, encoding="utf-8", xml_declaration=True), mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def require_public_origin():
    if not origin() or not current_app.config["SEARCH_INDEXING_ENABLED"]:
        abort(503)


@seo_bp.get("/robots.txt")
def robots():
    if not current_app.config["SEARCH_INDEXING_ENABLED"]:
        text = "User-agent: *\nDisallow: /\n"
    else:
        text = "User-agent: *\nAllow: /\n"
        if origin():
            text += "Sitemap: " + absolute("seo.sitemap") + "\n"
    return Response(text, mimetype="text/plain")


@seo_bp.get("/sitemap.xml")
def sitemap():
    require_public_origin()
    root = Element("sitemapindex", xmlns=SITEMAP_NS)
    urls = [absolute("seo.pages_sitemap")]
    urls += [absolute("seo.products_sitemap", page=p) for p in range(1, ceil(public_products().count()/1000)+1)]
    for url in urls:
        SubElement(SubElement(root, "sitemap"), "loc").text = url
    return xml_response(root)


@seo_bp.get("/sitemaps/pages.xml")
def pages_sitemap():
    require_public_origin()
    root = Element("urlset", xmlns=SITEMAP_NS)
    for endpoint in ["main.home", "main.about", "main.contact", "main.shipping", "main.returns", "main.refund_policy", "main.privacy", "main.terms", "community.gallery"]:
        SubElement(SubElement(root, "url"), "loc").text = absolute(endpoint)
    collections = [(None, public_products().count())] + [(c, public_products().filter_by(category_id=c.id).count()) for c in Category.query.filter_by(is_active=True)]
    for category, count in collections:
        for page in range(1, max(1, ceil(count/48))+1):
            args = {"category": category.slug} if category else {}
            if page > 1:
                args["page"] = page
            SubElement(SubElement(root, "url"), "loc").text = absolute("products.shop", **args)
    return xml_response(root)


@seo_bp.get("/sitemaps/products-<int:page>.xml")
def products_sitemap(page):
    require_public_origin()
    if page < 1:
        abort(404)
    products = public_products().order_by(Product.id).offset((page-1)*1000).limit(1000).all()
    if not products:
        abort(404)
    root = Element("urlset", xmlns=SITEMAP_NS)
    for product in products:
        node = SubElement(root, "url")
        SubElement(node, "loc").text = absolute("products.detail", slug=product.slug)
        if product.updated_at:
            SubElement(node, "lastmod").text = product.updated_at.date().isoformat()
    return xml_response(root)


@seo_bp.get("/merchant-feed.xml")
def merchant_feed():
    require_public_origin()
    root = Element("rss", version="2.0")
    channel = SubElement(root, "channel")
    for key,value in {"title":"AURK", "link":origin(), "description":"AURK streetwear catalogue"}.items():
        SubElement(channel,key).text=value
    products = public_products().filter(Product.product_status != "coming_soon", Product.hide_price.is_(False)).options(
        selectinload(Product.images), selectinload(Product.variants).selectinload(ProductVariant.inventory),
        selectinload(Product.variants).selectinload(ProductVariant.size), selectinload(Product.variants).selectinload(ProductVariant.color))
    for product in products:
        if not product.primary_image:
            continue
        for variant in product.variants:
            price = variant.price_override if variant.price_override is not None else product.current_price
            if not variant.is_active or price is None or price <= 0:
                continue
            item = SubElement(channel, "item")
            values = {"id": variant.sku, "item_group_id": str(product.id), "title": product.name,
                      "description": product.description or product.name, "link": absolute("products.detail", slug=product.slug, variant=variant.id),
                      "image_link": absolute("products.product_image", image_id=product.primary_image.id),
                      "price": f"{price:.2f} INR", "brand": "AURK", "condition": "new", "identifier_exists": "no",
                      "availability": "in_stock" if product.is_purchasable and variant.inventory and variant.inventory.quantity > variant.inventory.reserved_quantity else "out_of_stock",
                      "size": variant.size.name if variant.size else "One size", "color": variant.color.name if variant.color else "Default"}
            for key,value in values.items():
                SubElement(item, "{"+GOOGLE_NS+"}"+key).text = str(value)
    return xml_response(root)


def init_seo(app):
    import secrets
    from flask import g
    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(24)
    app.register_blueprint(seo_bp)
    from datetime import datetime, timezone
    app.context_processor(lambda: {"seo_metadata": metadata, "current_year": datetime.now(timezone.utc).year})
