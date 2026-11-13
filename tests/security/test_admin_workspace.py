from datetime import timedelta
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, Role, Permission, Category, Product, ProductVariant, Size, Color, Inventory, InventoryMovement, Review, Coupon, AuditLog
from app.models.admin_session import AdminSession
from app.admin.security import ADMIN_PERMISSIONS, utcnow

PASSWORD = "AdminTestingPassword123!"
PAGES = ("dashboard", "products", "categories", "orders", "customers", "inventory", "coupons", "reviews", "analytics", "settings")


@pytest.fixture
def store(client):
    with client.application.app_context():
        role = Role(name="Super Admin", permissions=[Permission(name=name) for name in ADMIN_PERMISSIONS])
        admin = User(email="admin@example.com", first_name="Store", last_name="Admin", password_hash=generate_password_hash(PASSWORD), roles=[role])
        customer = User(email="customer@example.com", first_name="Customer", last_name="Test", password_hash=generate_password_hash(PASSWORD))
        category = Category(name="Shirts", slug="shirts")
        product = Product(name="Example Shirt", slug="example-shirt", base_price=Decimal("800"), category=category)
        variant = ProductVariant(product=product, size=Size(name="M"), color=Color(name="Black"), sku="SHIRT-M")
        variant.inventory = Inventory(quantity=5, reserved_quantity=2, low_stock_threshold=3)
        db.session.add_all([admin, customer, variant])
        db.session.flush()
        db.session.add(Review(user_id=customer.id, product_id=product.id, rating=5, body="<script>alert(1)</script>Nice shirt", is_approved=False))
        db.session.commit()
    return client


def sign_in(client, admin=True):
    client.post("/auth/logout")
    response = client.post("/admin/login" if admin else "/auth/login", data={"email": "admin@example.com" if admin else "customer@example.com", "password": PASSWORD})
    assert response.status_code == 302
    return response


def test_every_admin_page_blocks_guest_and_customer(store):
    for path in PAGES:
        response = store.get(f"/admin/{path}")
        assert response.status_code == 302 and "/admin/login" in response.location
    for path in ("/admin/products/create", "/admin/products/1/delete", "/admin/inventory/1", "/admin/customers/2", "/admin/reviews/1", "/admin/coupons/1/delete"):
        response = store.post(path, data={"isAdmin": "true", "role": "Super Admin"})
        assert response.status_code == 302 and "/admin/login" in response.location
    sign_in(store, admin=False)
    for path in PAGES:
        assert store.get(f"/admin/{path}").status_code == 403
    for path in ("/admin/products/1/delete", "/admin/inventory/1", "/admin/customers/2", "/admin/reviews/1"):
        assert store.post(path, data={"isAdmin": "true", "role": "Super Admin"}).status_code == 403
    # No unguarded parallel JSON API exists; these paths are not implemented.
    assert store.get("/api/admin/products").status_code == 404
    assert store.post("/api/admin/products").status_code == 404
    with store.application.app_context():
        assert Product.query.count() == 1
        assert not User.query.filter_by(email="customer@example.com").one().roles


def test_admin_pages_render_and_storefront_keeps_separate_design(store):
    response = sign_in(store)
    assert response.location == "/admin/dashboard"
    for path in PAGES:
        response = store.get(f"/admin/{path}")
        assert response.status_code == 200, path
        assert b"css/admin.css" in response.data
        assert b"css/premium.css" not in response.data
        assert response.headers["Cache-Control"] == "no-store, private"
    for path in ("/admin/products/create", "/admin/products/1/edit", "/admin/categories/create", "/admin/categories/1/edit", "/admin/customers/2", "/admin/coupons/create"):
        assert store.get(path).status_code == 200, path
    home = store.get("/")
    assert home.status_code == 200
    assert b"css/premium.css" in home.data
    assert b'href="/admin' not in home.data
    assert store.get("/shop").status_code == 200
    assert store.get("/admin").location == "/admin/dashboard"


def test_customer_login_does_not_elevate_even_an_admin(store):
    response = store.post("/auth/login", data={"email": "admin@example.com", "password": PASSWORD})
    assert response.status_code == 302
    response = store.get("/admin/dashboard")
    assert response.status_code == 302 and "/admin/login" in response.location


@pytest.mark.parametrize("email,password", [("customer@example.com", PASSWORD), ("missing@example.com", PASSWORD), ("admin@example.com", "wrong")])
def test_admin_login_errors_are_generic(store, email, password):
    response = store.post("/admin/login", data={"email": email, "password": password})
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    with store.application.app_context():
        assert AdminSession.query.count() == 0


def test_invalid_expired_and_revoked_sessions_are_blocked(store):
    sign_in(store)
    with store.session_transaction() as session:
        session["admin_token"] = "forged"
    assert store.get("/admin/dashboard").status_code == 302
    sign_in(store)
    with store.application.app_context():
        record = AdminSession.query.order_by(AdminSession.id.desc()).first()
        record.last_seen_at = utcnow() - timedelta(hours=1)
        db.session.commit()
    assert store.get("/admin/dashboard").status_code == 302
    sign_in(store)
    with store.application.app_context():
        record = AdminSession.query.order_by(AdminSession.id.desc()).first()
        record.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert store.get("/admin/dashboard").status_code == 302
    sign_in(store)
    old_cookie = store.get_cookie("ar_drips_session").value
    assert store.post("/admin/logout").location == "/admin/login"
    store.set_cookie("ar_drips_session", old_cookie)
    assert store.get("/admin/dashboard").status_code == 302


def test_role_and_permission_revocation_take_effect(store):
    sign_in(store)
    with store.application.app_context():
        role = Role.query.one()
        role.permissions = [p for p in role.permissions if p.name != "products.delete"]
        db.session.commit()
    assert store.post("/admin/products/1/delete").status_code == 403
    assert store.get("/admin/products").status_code == 200
    with store.application.app_context():
        user = User.query.filter_by(email="admin@example.com").one()
        user.roles.clear()
        db.session.commit()
    assert store.get("/admin/orders").status_code == 403


def test_disabled_admin_and_changed_password_invalidate_session(store):
    sign_in(store)
    with store.application.app_context():
        user = User.query.filter_by(email="admin@example.com").one()
        user.password_hash = generate_password_hash("ChangedPassword123!")
        db.session.commit()
    assert store.get("/admin/dashboard").status_code == 302
    store.post("/admin/login", data={"email": "admin@example.com", "password": "ChangedPassword123!"})
    with store.application.app_context():
        user = User.query.filter_by(email="admin@example.com").one()
        user.is_active = False
        db.session.commit()
    assert store.get("/admin/dashboard").status_code in (302, 403)


def test_customer_status_and_no_role_mass_assignment(store):
    sign_in(store)
    assert store.post("/admin/customers/2", data={"status": "disabled", "roles": "Super Admin", "isAdmin": "true"}).status_code == 302
    assert store.post("/admin/customers/1", data={"status": "disabled"}).status_code == 404
    with store.application.app_context():
        customer = db.session.get(User, 2)
        assert not customer.is_active and not customer.roles
    store.post("/admin/logout")
    response = store.post("/auth/login", data={"email": "customer@example.com", "password": PASSWORD})
    assert b"Invalid email, phone number or password" in response.data


def test_inventory_validation_and_audit(store):
    sign_in(store)
    assert store.post("/admin/inventory/1", data={"quantity": "1", "low_stock_threshold": "3"}).status_code == 400
    assert store.post("/admin/inventory/1", data={"quantity": "999999999999999", "low_stock_threshold": "3"}).status_code == 400
    assert store.post("/admin/inventory/1", data={"quantity": "12", "low_stock_threshold": "4"}).status_code == 302
    with store.application.app_context():
        assert Inventory.query.one().quantity == 12
        assert InventoryMovement.query.one().quantity_delta == 7
        assert InventoryMovement.query.one().created_by == 1
        assert AuditLog.query.filter_by(action="inventory.updated").count() == 1


def test_category_deletion_preserves_products(store):
    sign_in(store)
    assert store.post("/admin/categories/1/delete").status_code == 302
    with store.application.app_context():
        assert Category.query.count() == 0
        assert Product.query.one().category_id is None
    assert store.get("/product/example-shirt").status_code == 200


def test_coupon_crud_and_review_moderation(store):
    sign_in(store)
    data = dict(code="WELCOME10", discount_type="percentage", value="10", minimum_order="500", starts_at="2026-01-01T00:00", expires_at="2027-01-01T00:00", usage_limit="100", per_user_limit="1", is_active="1")
    assert store.post("/admin/coupons/create", data={**data, "value": "NaN"}).status_code == 400
    assert store.post("/admin/coupons/create", data={**data, "value": "101"}).status_code == 400
    assert store.post("/admin/coupons/create", data=data).status_code == 302
    assert store.get("/admin/coupons/1/edit").status_code == 200
    assert store.post("/admin/coupons/1/edit", data={**data, "value": "15"}).status_code == 302
    assert store.post("/admin/coupons/1/disable").status_code == 302
    with store.application.app_context():
        coupon = Coupon.query.one()
        assert coupon.value == Decimal("15") and not coupon.is_active
    assert store.post("/admin/coupons/1/delete").status_code == 302
    assert store.post("/admin/reviews/1", data={"action": "approve"}).status_code == 302
    with store.application.app_context():
        assert Review.query.one().is_approved
    page = store.get("/admin/reviews")
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;" in page.data
    assert store.post("/admin/reviews/1", data={"action": "reject"}).status_code == 302
    with store.application.app_context():
        assert not Review.query.one().is_approved


def test_password_change_requires_current_password_and_revokes_admin_sessions(store):
    sign_in(store)
    data = dict(first_name="Store", last_name="Admin", current_password="wrong", new_password="NewAdminPassword123!", confirm_password="NewAdminPassword123!")
    assert store.post("/admin/settings", data=data).status_code == 400
    assert store.post("/admin/settings", data={**data, "current_password": PASSWORD}).location == "/admin/login"
    with store.application.app_context():
        assert AdminSession.query.count() == 0
        assert check_password_hash(User.query.filter_by(email="admin@example.com").one().password_hash, data["new_password"])
    assert store.get("/admin/dashboard").status_code == 302


def test_csrf_errors_use_admin_layout(store):
    store.application.config["WTF_CSRF_ENABLED"] = True
    response = store.post("/admin/login", data={"email": "admin@example.com", "password": PASSWORD})
    assert response.status_code == 400
    assert b"css/admin.css" in response.data
    assert b"csrf" not in response.data.lower() or b"csrf_token" in response.data


def test_admin_headers_and_safe_redirect(store):
    response = store.post("/admin/login?next=//evil.example", data={"email": "admin@example.com", "password": PASSWORD})
    assert response.location == "/admin/dashboard"
    response = store.get("/admin/dashboard")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    cookie = store.get_cookie("ar_drips_session")
    assert cookie.http_only and cookie.same_site == "Lax"


def test_admin_login_is_rate_limited(store):
    from app.extensions import limiter
    store.application.config["RATELIMIT_ENABLED"] = True
    limiter.init_app(store.application)
    try:
        with store.application.app_context():
            limiter.reset()
        responses = [store.post("/admin/login", data={"email": "missing@example.com", "password": "wrong"}) for _ in range(6)]
        assert responses[0].status_code == 401
        assert responses[-1].status_code == 429
        assert b"Too many attempts" in responses[-1].data
    finally:
        limiter.enabled = False


def test_csrf_protects_authenticated_mutations(store):
    import re
    sign_in(store)
    store.application.config["WTF_CSRF_ENABLED"] = True
    response = store.post("/admin/inventory/1", data={"quantity": "20", "low_stock_threshold": "3"})
    assert response.status_code == 400
    page = store.get("/admin/inventory")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    response = store.post("/admin/inventory/1", data={"quantity": "20", "low_stock_threshold": "3", "csrf_token": token})
    assert response.status_code == 302
    with store.application.app_context():
        assert Inventory.query.one().quantity == 20


def test_registration_cannot_assign_roles_and_invalid_input_is_safe(store):
    response = store.post("/auth/register", data={"first_name": "New", "last_name": "Customer", "email": "new@example.com", "password": PASSWORD, "role": "Super Admin", "isAdmin": "true"})
    assert response.status_code == 302
    with store.application.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert not user.roles
    sign_in(store)
    assert store.get("/admin/customers?q=" + "x" * 121).status_code == 400
    assert store.get("/admin/missing-page").status_code == 404
    assert b"css/admin.css" in store.get("/admin/missing-page").data
    assert store.post("/admin/reviews/1", data={"action": "delete_everything"}).status_code == 400


def test_hidden_images_require_admin_session(store, tmp_path):
    import io
    from PIL import Image
    from app.models import ProductImage
    root = tmp_path / "uploads"
    root.mkdir(exist_ok=True)
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    (root / "sample.png").write_bytes(output.getvalue())
    store.application.config["UPLOAD_DIR"] = str(root)
    with store.application.app_context():
        product = Product.query.one()
        product.is_active = False
        image = ProductImage(product_id=product.id, storage_key="sample.png", mime_type="image/png", file_size=len(output.getvalue()), width=8, height=8, sort_order=0, is_primary=True)
        db.session.add(image)
        db.session.commit()
    assert store.get("/product-image/1").status_code == 404
    assert store.get("/admin/product-images/1").status_code == 302
    sign_in(store)
    assert store.get("/admin/product-images/1").status_code == 200
    assert b"/admin/product-images/1" in store.get("/admin/products/1/edit").data


def test_migration_preserves_users_and_grants_only_owner_role(store):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration = importlib.import_module("migrations.versions.34cd72ef5610_admin_workspace")
    with store.application.app_context():
        admin_role = Role.query.one()
        admin_role.permissions = [p for p in admin_role.permissions if p.name == "orders.manage"]
        limited = Role(name="Admin")
        db.session.add(limited)
        db.session.commit()
        before = {"users": User.query.count(), "products": Product.query.count()}
        AdminSession.__table__.drop(db.engine)
        with db.engine.begin() as connection:
            original = migration.op
            migration.op = Operations(MigrationContext.configure(connection))
            try:
                migration.upgrade()
            finally:
                migration.op = original
        db.session.expire_all()
        assert User.query.count() == before["users"]
        assert Product.query.count() == before["products"]
        assert set(p.name for p in admin_role.permissions) == set(ADMIN_PERMISSIONS)
        assert not limited.permissions
        assert AdminSession.query.count() == 0


def test_admin_option_creation_and_edits_share_inventory(store):
    sign_in(store)
    response = store.post("/admin/products/1/variants", data={"size_name": "L", "color_name": "Blue", "sku": "SHIRT-L-BLUE", "quantity": "9", "price_override": "850"})
    assert response.status_code == 302
    with store.application.app_context():
        variant = ProductVariant.query.filter_by(sku="SHIRT-L-BLUE").one()
        variant_id = variant.id
        assert variant.inventory.quantity == 9
        inventory_id = variant.inventory.id
    page = store.get("/admin/inventory?q=SHIRT-L-BLUE")
    assert page.status_code == 200 and b"SHIRT-L-BLUE" in page.data
    assert store.post(f"/admin/products/1/variants/{variant_id}", data={"quantity": "14", "is_active": "1"}).status_code == 302
    with store.application.app_context():
        stock = Inventory.query.filter_by(variant_id=variant_id).one()
        assert stock.id == inventory_id and stock.quantity == 14
        movements = InventoryMovement.query.filter_by(variant_id=variant_id).order_by(InventoryMovement.id).all()
        assert [movement.quantity_delta for movement in movements] == [9, 5]
    assert store.post(f"/admin/inventory/{variant_id}", data={"quantity": "11", "low_stock_threshold": "3"}).status_code == 302
    with store.application.app_context():
        stock = Inventory.query.filter_by(variant_id=variant_id).one()
        assert stock.id == inventory_id and stock.quantity == 11
    assert b'value="11"' in store.get("/admin/products/1/edit").data


def test_multiple_product_views_and_size_chart_upload(store, tmp_path):
    import io
    from PIL import Image
    from app.models import ProductImage
    sign_in(store)
    store.application.config["UPLOAD_DIR"] = str(tmp_path)
    uploads = []
    for name, dimensions in [("front.png", (120,150)), ("back.png", (120,150)), ("side.png", (120,150)), ("size-chart.png", (200,100))]:
        stream = io.BytesIO()
        Image.new("RGB", dimensions, "white").save(stream, format="PNG")
        stream.seek(0)
        uploads.append((stream, name))
    response = store.post("/admin/products/1/edit", data={"name":"Example Shirt", "slug":"example-shirt", "description":"Multiple views", "base_price":"800", "sale_price":"", "category_id":"1", "is_active":"1", "images":uploads}, content_type="multipart/form-data")
    assert response.status_code == 302
    with store.application.app_context():
        images = ProductImage.query.order_by(ProductImage.sort_order).all()
        assert len(images) == 4
        assert (images[-1].width, images[-1].height) == (200, 100)
        chart_id = images[-1].id
    response = store.get("/product/example-shirt")
    assert response.status_code == 200
    assert response.data.count(b'data-product-image=') == 4
    assert b'id="fullProductImage"' in response.data
    assert store.get(f"/product-image/{chart_id}").status_code == 200


def test_bulk_sizes_and_mixed_size_checkout(store):
    from app.models import Order
    sign_in(store)
    data = {"size_name":"S, L, XL", "color_name":"Blue", "sku":"SHIRT-BLUE", "quantity":"5"}
    assert store.post("/admin/products/1/variants", data=data).status_code == 302
    with store.application.app_context():
        variants = ProductVariant.query.filter(ProductVariant.sku.like("SHIRT-BLUE-%")).order_by(ProductVariant.id).all()
        assert len(variants) == 3
        assert all(v.inventory.quantity == 5 for v in variants)
        first, second = variants[0].id, variants[1].id
    # A duplicate halfway through a batch must roll back the entire batch.
    assert store.post("/admin/products/1/variants", data={**data, "size_name":"XXL, S", "sku":"SECOND"}).status_code == 400
    with store.application.app_context():
        assert ProductVariant.query.filter_by(sku="SECOND-XXL").first() is None
    store.post("/admin/logout")
    assert store.post("/cart/add", data={"variant_id":first,"quantity":2}).status_code == 302
    assert store.post("/cart/add", data={"variant_id":second,"quantity":3}).status_code == 302
    assert store.post("/auth/login", data={"email":"customer@example.com","password":PASSWORD}).status_code == 302
    response = store.post("/checkout", data={"recipient_name":"Customer Test","phone":"9876543210","line1":"1 Test Street","city":"Mumbai","state":"Maharashtra","postal_code":"400001","country":"India"})
    assert "/checkout/success/" in response.location
    with store.application.app_context():
        order = Order.query.one()
        assert sorted(item.quantity for item in order.items) == [2,3]
        assert len({item.size_snapshot for item in order.items}) == 2
        assert db.session.get(ProductVariant,first).inventory.quantity == 3
        assert db.session.get(ProductVariant,second).inventory.quantity == 2


def test_delete_stocked_product_removes_it_from_catalogue_but_keeps_history(store):
    sign_in(store)
    with store.application.app_context():
        db.session.add(InventoryMovement(variant_id=1,quantity_delta=5,reason="opening_stock"))
        db.session.commit()
    response = store.post("/admin/products/1/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"Example Shirt" not in response.data
    assert b"Example Shirt" not in store.get("/admin/inventory").data
    assert store.get("/product/example-shirt").status_code == 404
    assert store.get("/admin/products/1/edit").status_code == 404
    with store.application.app_context():
        product = db.session.get(Product,1)
        assert product.is_archived and not product.is_active
        assert InventoryMovement.query.count() == 1
        assert Inventory.query.count() == 1


def test_hidden_product_remains_editable_until_deleted(store):
    sign_in(store)
    with store.application.app_context():
        product = db.session.get(Product,1)
        product.is_active = False
        db.session.commit()
    assert b"Example Shirt" in store.get("/admin/products?status=hidden").data
    assert store.get("/admin/products/1/edit").status_code == 200


def test_clickable_sizes_generate_skus_without_manual_codes(store):
    sign_in(store)
    page = store.get("/admin/products/1/edit")
    assert b'name="sizes"' in page.data
    assert b'name="sku"' not in page.data
    response = store.post("/admin/products/1/variants", data={"sizes":["S","L","XL"], "color_name":"Blue", "quantity":"7", "sku":"UNTRUSTED"})
    assert response.status_code == 302
    with store.application.app_context():
        variants = ProductVariant.query.filter(ProductVariant.sku.like("ARD-1-%")).all()
        assert len(variants) == 3
        assert len({v.sku for v in variants}) == 3
        assert {v.size.name for v in variants} == {"S","L","XL"}
        assert all(v.inventory.quantity == 7 for v in variants)
    assert store.post("/admin/products/1/variants", data={"color_name":"Red","quantity":"4"}).status_code == 400
    assert store.post("/admin/products/1/variants", data={"sizes":["invalid"],"color_name":"Red","quantity":"4"}).status_code == 400
    assert store.post("/admin/products/1/variants", data={"custom_size":"32","color_name":"Red","quantity":"4"}).status_code == 302


def test_product_cards_allow_guest_purchase_without_detail_page(store):
    with store.application.app_context():
        product = Product.query.one()
        product.is_featured = True
        db.session.commit()
    for path in ("/", "/shop"):
        response = store.get(path)
        assert response.status_code == 200
        assert b'data-quick-add' in response.data
        assert b'Add to bag' in response.data
        assert b'action="/cart/add"' in response.data
    response = store.post("/cart/add", data={"variant_id":1,"quantity":2})
    assert response.location == "/cart"
    with store.session_transaction() as session:
        assert session["guest_cart"]["1"] == 2
    with store.application.app_context():
        inventory = Inventory.query.one()
        inventory.quantity = inventory.reserved_quantity
        db.session.commit()
    response = store.get("/shop")
    assert b'data-quick-add' not in response.data
    assert b'Currently out of stock' in response.data


def test_separate_colour_size_fields_without_option_prices(store):
    import re
    for path in ("/shop", "/product/example-shirt"):
        response = store.get(path)
        assert response.status_code == 200
        assert b'data-colour-select' in response.data
        assert b'data-size-select' in response.data
        assert b'name="variant_id"' in response.data
        options = re.findall(rb'<option[^>]*data-stock[^>]*>(.*?)</option>', response.data)
        assert options
        assert all(b"8377" not in text and b"800" not in text for text in options)


def test_one_step_listing_creates_stock_and_unique_links(store, tmp_path):
    import io
    from PIL import Image
    sign_in(store)
    store.application.config["UPLOAD_DIR"] = str(tmp_path)
    page = store.get("/admin/products/create")
    assert page.status_code == 200
    assert b'name="quick_listing"' in page.data
    assert b'name="slug"' not in page.data

    def submit(**changes):
        image = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        image.seek(0)
        data = dict(quick_listing="1", name="Easy Shirt", base_price="500",
                    category_id="1", sizes=["S", "M"], color_name="Blue",
                    quantity="6", is_active="1", images=(image, "front.png"))
        data.update(changes)
        return store.post("/admin/products/create", data=data)

    assert submit().location == "/admin/products"
    assert submit().location == "/admin/products"
    with store.application.app_context():
        products = Product.query.filter(Product.name == "Easy Shirt").all()
        assert {p.slug for p in products} == {"easy-shirt", "easy-shirt-2"}
        for product in products:
            assert len(product.images) == 1 and product.images[0].is_primary
            assert {v.size.name for v in product.variants} == {"S", "M"}
            assert all(v.inventory.quantity == 6 for v in product.variants)
        assert InventoryMovement.query.count() == 4
    files_before = set(tmp_path.rglob("*.png"))
    response = submit(quantity="-1", name="Keep my details")
    assert response.status_code == 400
    assert b'value="Keep my details"' in response.data
    assert set(tmp_path.rglob("*.png")) == files_before
    with store.application.app_context():
        assert Product.query.count() == 3
        assert InventoryMovement.query.count() == 4
    assert submit(sizes=[]).status_code == 400
    assert submit(category_id="9999").status_code == 400


def test_percentage_discount_multi_upload_and_store_prices(store, tmp_path):
    import io
    from types import SimpleNamespace
    from PIL import Image
    from app.services.pricing import calculate_subtotal
    sign_in(store)
    store.application.config["UPLOAD_DIR"] = str(tmp_path)
    uploads = []
    for name in ("front.png", "back.png"):
        stream = io.BytesIO()
        Image.new("RGB", (120, 150), "white").save(stream, format="PNG")
        stream.seek(0)
        uploads.append((stream, name))
    response = store.post("/admin/products/create", data=dict(
        quick_listing="1", name="Discount Shirt", base_price="999", discount_percent="10",
        category_id="1", sizes=["S", "M"], color_name="Blue", quantity="5",
        is_active="1", is_featured="1", images=uploads))
    assert response.status_code == 302
    with store.application.app_context():
        product = Product.query.filter_by(slug="discount-shirt").one()
        product_id = product.id
        assert product.base_price == Decimal("999.00")
        assert product.sale_price == Decimal("899.10")
        assert len(product.images) == 2
        assert calculate_subtotal([SimpleNamespace(variant=product.variants[0], quantity=2)]) == Decimal("1798.20")
    for path in ("/shop", "/", "/product/discount-shirt"):
        response = store.get(path)
        assert response.status_code == 200
        assert b"899.10" in response.data and b"999.00" in response.data
        assert b"<del" in response.data
    data = dict(name="Discount Shirt", slug="discount-shirt", base_price="99.99",
                discount_percent="12.5", category_id="1", is_active="1")
    assert store.post(f"/admin/products/{product_id}/edit", data=data).status_code == 302
    with store.application.app_context():
        assert db.session.get(Product, product_id).sale_price == Decimal("87.49")
    for invalid in ("101", "-1", "NaN", "Infinity", "abc"):
        assert store.post(f"/admin/products/{product_id}/edit", data={**data, "discount_percent":invalid}).status_code == 400
    assert store.post(f"/admin/products/{product_id}/edit", data={**data, "discount_percent":""}).status_code == 302
    with store.application.app_context():
        assert db.session.get(Product, product_id).sale_price is None


def test_dashboard_reports_dates_exports_and_back_navigation(store):
    import csv
    import io
    from datetime import datetime
    from app.models import Order, Payment
    with store.application.app_context():
        common = dict(user_id=2, subtotal=1000, discount=0, shipping=0, tax=0,
            total=1000, shipping_name="Customer", shipping_phone="9876543210",
            shipping_line1="Test", shipping_city="Mumbai", shipping_state="MH",
            shipping_postal_code="400001", shipping_country="India")
        included = Order(order_number="=FORMULA", status="Delivered", created_at=datetime(2026,10,10,18,30), **common)
        excluded = Order(order_number="BEFORE", status="Cancelled", created_at=datetime(2026,10,10,18,29,59), **common)
        db.session.add_all([included, excluded])
        db.session.flush()
        db.session.add(Payment(order_id=included.id, provider="cod", provider_order_id="test-receipt",
            status="paid", amount=1000, paid_at=datetime(2026,10,11,18,29,59)))
        product = Product.query.one()
        product.name = "=PRODUCT"
        db.session.commit()
    assert store.get("/admin/reports/summary.csv").status_code == 302
    sign_in(store, admin=False)
    assert store.get("/admin/reports/orders.csv").status_code == 403
    sign_in(store)
    query = "?start=2026-10-11&end=2026-10-11"
    dashboard = store.get("/admin/dashboard" + query)
    assert dashboard.status_code == 200
    assert b"Export reports" in dashboard.data
    assert b"1,000.00" in dashboard.data
    def report(kind):
        response = store.get(f"/admin/reports/{kind}.csv" + query)
        assert response.status_code == 200
        assert "attachment" in response.headers["Content-Disposition"]
        assert response.headers["Cache-Control"] == "no-store, private"
        return list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    summary = report("summary")
    values = {row[0]:row[1] for row in summary[1:]}
    assert values["Orders placed"] == "1"
    assert values["Order value excluding cancelled"] == "1000.00"
    assert values["Cash recorded as received"] == "1000.00"
    orders = report("orders")
    assert len(orders) == 2
    assert orders[1][0] == "'=FORMULA"
    assert orders[1][1].startswith("2026-10-11T00:00:00")
    assert len(report("receipts")) == 2
    inventory = report("inventory")
    assert inventory[1][0] == "'=PRODUCT"
    assert inventory[1][6] == "3"
    assert inventory[1][8] == "Yes"
    assert store.get("/admin/reports/unknown.csv").status_code == 404
    for path in ("/admin/dashboard", "/admin/reports/summary.csv"):
        assert store.get(path + "?start=2026-10-12&end=2026-10-11").status_code == 400
        assert store.get(path + "?start=bad").status_code == 400
        assert store.get(path + "?start=2020-01-01&end=2026-01-01").status_code == 400
    assert b'Back to products' in store.get("/admin/products/create").data
    assert b'Back to products' in store.get("/admin/products/1/edit").data
    assert b'Back to dashboard' in store.get("/admin/products").data
    with store.application.app_context():
        role = Role.query.one()
        role.permissions = [p for p in role.permissions if p.name not in ("orders.manage", "inventory.manage")]
        db.session.commit()
    assert store.get("/admin/reports/summary.csv" + query).status_code == 200
    assert store.get("/admin/reports/orders.csv" + query).status_code == 403
    assert store.get("/admin/reports/receipts.csv" + query).status_code == 403
    assert store.get("/admin/reports/inventory.csv" + query).status_code == 403
    with store.application.app_context():
        role = Role.query.one()
        role.permissions = [p for p in role.permissions if p.name != "analytics.view"]
        db.session.commit()
    assert store.get("/admin/reports/summary.csv" + query).status_code == 403
