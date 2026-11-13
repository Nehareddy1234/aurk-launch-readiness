from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (Product, ProductInterest, ProductVariant, Inventory, Size, Color,
                        User, Cart, CartItem, Order, Role, Permission, Category)
from app.services import product_interests as alerts


@pytest.fixture
def catalog(app):
    with app.app_context():
        category = Category(name="Tees", slug="tees")
        product = Product(name="Launch Tee", slug="launch", base_price=999, product_status="coming_soon", category=category)
        variant = ProductVariant(product=product, size=Size(name="M"), color=Color(name="Black"), sku="LAUNCH-M")
        variant.inventory = Inventory(quantity=5, reserved_quantity=0)
        user = User(email="buyer@example.com", first_name="Buyer", last_name="Test", phone="9876543210",
                    password_hash=generate_password_hash("StrongPassword123!"))
        db.session.add_all([product, variant, user])
        db.session.commit()
        return product.id, variant.id, user.id


def login(client):
    client.post("/auth/login", data={"email": "buyer@example.com", "password": "StrongPassword123!"})


def interest(client, product_id):
    return client.post(f"/products/{product_id}/interest", headers={"Accept": "application/json"})


def test_notify_login_return_and_subscription(client, catalog, monkeypatch):
    pid, _, uid = catalog
    monkeypatch.setattr(alerts, "send_email", Mock())
    response = client.post(f"/products/{pid}/interest")
    assert response.status_code == 302
    login_url = response.location
    assert "/auth/login?next=" in login_url
    page = client.get(login_url)
    assert b"Create an account" in page.data
    assert b"next=/product/launch" in page.data
    response = client.post(login_url, data={"email": "buyer@example.com", "password": "StrongPassword123!"})
    assert response.location == "/product/launch"
    assert interest(client, pid).status_code == 200
    assert interest(client, pid).status_code == 200
    with client.application.app_context():
        row = ProductInterest.query.one()
        assert row.customer_id == uid
        assert row.customer_email == "buyer@example.com"


def test_notify_acknowledgement_queued_once_and_retried(client, catalog, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.models import CustomerEmail
    from app.services import customer_emails
    client.application.config.update(CUSTOMER_EMAILS_ENABLED=True, PUBLIC_BASE_URL="https://aurk.in")
    owner = Mock()
    customer = Mock(side_effect=RuntimeError("SMTP down"))
    monkeypatch.setattr(alerts, "send_email", owner)
    monkeypatch.setattr(customer_emails, "send_email", customer)
    login(client)
    assert interest(client, catalog[0]).status_code == 200
    assert interest(client, catalog[0]).status_code == 200
    with client.application.app_context():
        notice = CustomerEmail.query.one()
        assert notice.kind == "notify_interest"
        assert notice.recipient == "buyer@example.com"
        assert notice.interest_id == ProductInterest.query.one().id
        assert notice.status == "pending"
        assert customer_emails.dispatch_customer_emails() == 1
        assert notice.status == "failed"
        assert customer_emails.dispatch_customer_emails() == 0
        notice.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        customer.side_effect = None
        assert customer_emails.dispatch_customer_emails() == 1
        assert notice.status == "submitted"
        assert customer_emails.dispatch_customer_emails() == 0
    assert owner.call_count == 1
    assert owner.call_args.args[0] == "support@aurk.in"
    assert owner.call_args.kwargs["reply_to"] == "buyer@example.com"
    assert owner.call_args.kwargs["from_email"] == "support@aurk.in"
    assert customer.call_args.args[0] == "buyer@example.com"
    assert "We will update you when the drop is live" in customer.call_args.args[3]
    assert 'cid:aurk-logo' in customer.call_args.args[2]


def test_business_notify_failure_retried_by_existing_worker(client, catalog, monkeypatch):
    from app.services import customer_emails
    owner = Mock(side_effect=RuntimeError("SMTP down"))
    monkeypatch.setattr(alerts, "send_email", owner)
    monkeypatch.setattr(customer_emails, "send_email", Mock())
    client.application.config.update(CUSTOMER_EMAILS_ENABLED=True, PUBLIC_BASE_URL="https://aurk.in")
    login(client)
    assert interest(client, catalog[0]).status_code == 200
    with client.application.app_context():
        assert ProductInterest.query.one().notified_at is None
        from datetime import datetime, timedelta, timezone
        ProductInterest.query.one().notification_next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
    owner.side_effect = None
    result = client.application.test_cli_runner().invoke(args=["send-customer-emails"])
    assert result.exit_code == 0, result.output
    assert owner.call_count == 2
    with client.application.app_context():
        assert ProductInterest.query.one().notified_at is not None


def test_notify_sample_cli(client, catalog, monkeypatch):
    from app.services import customer_emails
    from app.models import CustomerEmail
    sender = Mock()
    monkeypatch.setattr(customer_emails, "send_email", sender)
    client.application.config["PUBLIC_BASE_URL"] = "https://aurk.in"
    result = client.application.test_cli_runner().invoke(args=["send-email-test", "--to", "controlled@example.com", "--kind", "notify_interest"])
    assert result.exit_code == 0, result.output
    assert sender.call_args.args[0] == "controlled@example.com"
    assert sender.call_args.args[1].startswith("[TEST]")
    with client.application.app_context():
        assert CustomerEmail.query.count() == 0


@pytest.mark.parametrize("status", ["coming_soon", "out_of_stock"])
def test_unavailable_visible_and_blocked(client, catalog, status):
    pid, vid, uid = catalog
    with client.application.app_context():
        db.session.get(Product, pid).product_status = status
        db.session.commit()
    for path in ("/", "/shop", "/product/launch"):
        page = client.get(path)
        assert page.status_code == 200
        assert b"availability-visual" in page.data
        assert status.replace("_", " ").upper().encode() in page.data
        assert (b"Notify me" if status == "coming_soon" else b"I&#39;m Interested") in page.data
        assert b'action="/cart/add"' not in page.data
    client.post("/cart/add", data={"variant_id": vid})
    with client.session_transaction() as session:
        assert not session.get("guest_cart")
    login(client)
    client.post("/cart/add", data={"variant_id": vid})
    with client.application.app_context():
        assert CartItem.query.count() == 0
        cart = Cart(user_id=uid, items=[CartItem(variant_id=vid, quantity=1)])
        db.session.add(cart)
        db.session.commit()
    client.post("/checkout", data=dict(recipient_name="Buyer", phone="9876543210", line1="Street 1",
        city="Mumbai", state="Maharashtra", postal_code="400001", country="India"))
    with client.application.app_context():
        assert Order.query.count() == 0
        assert Inventory.query.one().quantity == 5


@pytest.mark.parametrize("authenticated", [True, False])
@pytest.mark.parametrize("status", ["coming_soon", "out_of_stock"])
def test_registration_duplicate_email_and_reload(client, catalog, monkeypatch, authenticated, status):
    pid, _, uid = catalog
    with client.application.app_context():
        db.session.get(Product, pid).product_status = status
        db.session.commit()
    sender = Mock()
    monkeypatch.setattr(alerts, "send_email", sender)
    client.application.config["INTEREST_NOTIFICATION_EMAIL"] = "owner@example.com"
    if authenticated:
        login(client)
    client.get("/product/launch")
    if status == "coming_soon" and not authenticated:
        response = interest(client, pid)
        assert response.status_code == 401
        assert "/auth/login?next=" in response.json["login_url"]
        with client.application.app_context():
            assert ProductInterest.query.count() == 0
        assert sender.call_count == 0
        return
    assert interest(client, pid).status_code == 200
    assert interest(client, pid).status_code == 200
    assert sender.call_count == 1
    args = sender.call_args.args
    assert args[0] == "owner@example.com"
    assert args[1] == "New Product Interest - Launch Tee"
    assert Product.STATUSES[status] in args[3]
    with client.application.app_context():
        row = ProductInterest.query.one()
        assert row.customer_id == (uid if authenticated else None)
        assert row.customer_email == ("buyer@example.com" if authenticated else None)
        assert row.notified_at
    assert (b"on the list" if status == "coming_soon" else b"Interest Registered") in client.get("/product/launch").data


def test_email_failure_saved_and_retryable(client, catalog, monkeypatch):
    login(client)
    pid, _, _ = catalog
    sender = Mock(side_effect=RuntimeError("SMTP down"))
    monkeypatch.setattr(alerts, "send_email", sender)
    client.get("/shop")
    assert interest(client, pid).status_code == 200
    with client.application.app_context():
        assert ProductInterest.query.one().notified_at is None
    with client.application.app_context():
        from datetime import datetime, timedelta, timezone
        ProductInterest.query.one().notification_next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
    sender.side_effect = None
    result = client.application.test_cli_runner().invoke(args=["send-interest-alerts"])
    assert result.exit_code == 0
    assert "Sent 1" in result.output
    client.application.test_cli_runner().invoke(args=["send-interest-alerts"])
    assert sender.call_count == 2


def test_status_transition_and_invalid_product(client, catalog, monkeypatch):
    pid, vid, _ = catalog
    monkeypatch.setattr(alerts, "send_email", Mock())
    client.get("/shop")
    assert interest(client, 99999).status_code == 404
    login(client)
    assert interest(client, pid).status_code == 200
    client.post("/auth/logout")
    with client.application.app_context():
        db.session.get(Product, pid).product_status = "available"
        db.session.commit()
    page = client.get("/product/launch")
    assert b"data-interest-form" not in page.data
    assert b'action="/cart/add"' in page.data
    assert interest(client, pid).status_code == 409
    client.post("/cart/add", data={"variant_id": vid})
    with client.session_transaction() as session:
        assert session["guest_cart"][str(vid)] == 1


def test_database_failure_allows_retry(client, catalog, monkeypatch):
    login(client)
    client.get("/shop")
    original = db.session.commit
    monkeypatch.setattr(db.session, "commit", Mock(side_effect=SQLAlchemyError("database failed")))
    assert interest(client, catalog[0]).status_code == 503
    monkeypatch.setattr(db.session, "commit", original)
    monkeypatch.setattr(alerts, "send_email", Mock())
    assert interest(client, catalog[0]).status_code == 200
    with client.application.app_context():
        assert ProductInterest.query.count() == 1


def test_csrf_and_product_deletion(client, catalog, monkeypatch):
    pid, _, _ = catalog
    client.application.config["WTF_CSRF_ENABLED"] = True
    assert interest(client, pid).status_code == 400
    client.application.config["WTF_CSRF_ENABLED"] = False
    login(client)
    monkeypatch.setattr(alerts, "send_email", Mock())
    client.get("/shop")
    interest(client, pid)
    with client.application.app_context():
        db.session.delete(db.session.get(Product, pid))
        db.session.commit()
        assert ProductInterest.query.count() == 0


def test_admin_status_and_interest_permissions(client, catalog):
    pid, _, uid = catalog
    assert client.get("/admin/interests").status_code == 302
    login(client)
    assert client.get("/admin/interests").status_code == 403
    client.post("/auth/logout")
    with client.application.app_context():
        user = db.session.get(User, uid)
        user.roles.append(Role(name="Admin", permissions=[Permission(name="products.update"), Permission(name="customers.manage")]))
        db.session.commit()
    client.post("/admin/login", data={"email": "buyer@example.com", "password": "StrongPassword123!"})
    assert client.get("/admin/interests").status_code == 200
    with client.application.app_context():
        category_id = db.session.get(Product, pid).category_id
    form = dict(name="Launch Tee", slug="launch", base_price="999", category_id=category_id, is_active="1")
    for status in ("out_of_stock", "available", "coming_soon"):
        assert client.post(f"/admin/products/{pid}/edit", data={**form, "product_status": status}).status_code == 302
        with client.application.app_context():
            assert db.session.get(Product, pid).product_status == status
    assert client.post(f"/admin/products/{pid}/edit", data={**form, "product_status": "invalid"}).status_code == 400


def test_coming_soon_optional_price(client, catalog):
    pid, _, uid = catalog
    with client.application.app_context():
        user = db.session.get(User, uid)
        user.roles.append(Role(name="Admin", permissions=[Permission(name="products.update"), Permission(name="products.create")]))
        category_id = db.session.get(Product, pid).category_id
        db.session.commit()
    assert client.post("/admin/login", data={"email": "buyer@example.com", "password": "StrongPassword123!"}).status_code == 302
    form = dict(name="Launch Tee", slug="launch", category_id=category_id, is_active="1",
                product_status="coming_soon", hide_price="1", base_price="")
    assert client.post(f"/admin/products/{pid}/edit", data=form).status_code == 302
    with client.application.app_context():
        product = db.session.get(Product, pid)
        assert product.hide_price and not product.show_price
    for path in ("/", "/shop", "/product/launch"):
        page = client.get(path)
        assert page.status_code == 200
        assert b"sale-price" not in page.data
        assert b"data-variant-price" not in page.data
        assert b"&#8377;0.00" not in page.data
    # New coming-soon listings can also be saved without announcing a price.
    import io
    from PIL import Image
    image = io.BytesIO()
    Image.new("RGB", (32, 40), "black").save(image, format="PNG")
    image.seek(0)
    created = client.post("/admin/products/create", data={**form, "name": "Next Tee", "slug": "next-tee",
        "images": (image, "front.png")}, content_type="multipart/form-data")
    assert created.status_code == 302
    with client.application.app_context():
        new_product = Product.query.filter_by(slug="next-tee").one()
        assert new_product.hide_price and not new_product.show_price
    assert b"&#8377;0.00" not in client.get("/product/next-tee").data
    # Even a crafted request cannot skip pricing on an available product.
    response = client.post(f"/admin/products/{pid}/edit", data={**form, "product_status": "available"})
    assert response.status_code == 400
    with client.application.app_context():
        assert db.session.get(Product, pid).product_status == "coming_soon"
    # An announced coming-soon price is still supported.
    assert client.post(f"/admin/products/{pid}/edit", data={**form, "hide_price": "", "base_price": "1299"}).status_code == 302
    for path in ("/", "/shop", "/product/launch"):
        assert b"1299.00" in client.get(path).data


def test_gallery_controls_only_visible_on_product_page(client, catalog):
    from html.parser import HTMLParser
    from app.models import ProductImage
    pid, _, _ = catalog
    with client.application.app_context():
        product = db.session.get(Product, pid)
        product.images = [ProductImage(storage_key=f"test/{i}.jpg", mime_type="image/jpeg", file_size=10,
            width=100, height=100, sort_order=i, is_primary=i == 0) for i in range(2)]
        db.session.commit()
    class Visibility(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hidden_depth = 0
            self.visible_controls = 0
            self.controls = 0
        def handle_starttag(self, tag, attrs):
            if tag != "div":
                return
            attrs = dict(attrs)
            if self.hidden_depth or "hidden" in attrs:
                self.hidden_depth += 1
            if "data-photo-controls" in attrs:
                self.controls += 1
                if not self.hidden_depth:
                    self.visible_controls += 1
        def handle_endtag(self, tag):
            if tag == "div" and self.hidden_depth:
                self.hidden_depth -= 1
    for path in ("/", "/shop", "/product/launch"):
        parser = Visibility()
        parser.feed(client.get(path).data.decode())
        assert parser.controls > 0
        assert parser.visible_controls == (1 if path == "/product/launch" else 0)
