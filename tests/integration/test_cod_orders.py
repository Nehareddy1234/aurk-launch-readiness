from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (User, Role, Permission, Category, Size, Color, Product,
    ProductVariant, Inventory, Cart, CartItem, Order, Payment, AuditLog, OrderNotification)
from app.services import order_notifications as alerts

PASSWORD = "StrongPassword123!"
DETAILS = dict(recipient_name="Buyer Test", phone="9876543210", line1="1 Test Street",
               line2="", city="Mumbai", state="Maharashtra", postal_code="400001", country="India")


@pytest.fixture
def seeded(client):
    with client.application.app_context():
        customer = User(email="buyer@example.com", first_name="Buyer", last_name="Test", password_hash=generate_password_hash(PASSWORD))
        owner = User(email="owner@example.com", first_name="Owner", last_name="Test", password_hash=generate_password_hash(PASSWORD))
        role = Role(name="Super Admin", permissions=[Permission(name="orders.manage")])
        owner.roles.append(role)
        category = Category(name="Tees", slug="tees")
        size, color = Size(name="M"), Color(name="Black")
        db.session.add_all([customer, owner, category, size, color])
        db.session.flush()
        product = Product(name="Everyday Tee", slug="everyday", base_price=Decimal("799"), category_id=category.id)
        db.session.add(product)
        db.session.flush()
        variant = ProductVariant(product_id=product.id, size_id=size.id, color_id=color.id, sku="TEE-M-BLK")
        db.session.add(variant)
        db.session.flush()
        inventory = Inventory(variant_id=variant.id, quantity=3, reserved_quantity=0)
        cart = Cart(user_id=customer.id)
        db.session.add_all([inventory, cart])
        db.session.flush()
        cart.items.append(CartItem(variant_id=variant.id, quantity=1))
        db.session.commit()
    login(client, "buyer@example.com")
    return client


def login(client, email):
    client.post("/auth/logout")
    response = client.post("/admin/login" if email == "owner@example.com" else "/auth/login", data={"email": email, "password": PASSWORD})
    assert response.status_code == 302


def place(client):
    response = client.post("/checkout", data=DETAILS)
    assert "/checkout/success/" in response.location
    return response.location.rsplit("/", 1)[1]


def test_pending_then_owner_confirms_and_customer_sees_status(seeded):
    number = place(seeded)
    response = seeded.get(f"/checkout/success/{number}")
    assert response.status_code == 200
    assert b"Awaiting confirmation" in response.data
    assert b"your order is confirmed" not in response.data
    assert seeded.post(f"/admin/orders/{number}/confirm").status_code == 403
    login(seeded, "owner@example.com")
    assert seeded.get("/admin/orders").status_code == 200
    assert seeded.get(f"/admin/orders/{number}").status_code == 200
    assert seeded.get(f"/admin/orders/{number}/confirm").status_code == 405
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"
    for _ in range(2):
        assert seeded.post(f"/admin/orders/{number}/confirm").status_code == 302
    with seeded.application.app_context():
        assert Order.query.one().status == "Confirmed"
        assert AuditLog.query.filter_by(action="order.confirmed").count() == 1
        assert Inventory.query.one().quantity == 2
        assert Payment.query.one().status == "pending"
    login(seeded, "buyer@example.com")
    state = seeded.get(f"/account/orders/{number}/status")
    assert state.json["label"] == "Order confirmed"
    assert "you will receive a call shortly" in state.json["message"]
    assert state.headers["Cache-Control"] == "no-store, private"


def test_other_customer_cannot_read_order_or_status(seeded):
    number = place(seeded)
    login(seeded, "owner@example.com")
    assert seeded.get(f"/account/orders/{number}").status_code == 404
    assert seeded.get(f"/account/orders/{number}/status").status_code == 404
    assert seeded.get(f"/checkout/success/{number}").status_code == 404


def test_invalid_delivery_preserves_fields_and_does_not_place_order(seeded):
    for field, value in [("phone", "abc"), ("postal_code", "123"), ("line1", "")]:
        response = seeded.post("/checkout", data={**DETAILS, field: value})
        assert response.status_code == 200
        assert b'value="Buyer Test"' in response.data
        with seeded.application.app_context():
            assert Order.query.count() == 0
            assert Inventory.query.one().quantity == 3


def test_checkout_uses_price_read_under_product_lock(seeded):
    price_changed = False

    def change_price_before_lock(query):
        nonlocal price_changed
        statement = query.statement
        if (query.is_select and statement.column_descriptions[0]["entity"] is Product
                and statement._for_update_arg is not None and not price_changed):
            price_changed = True
            query.session.execute(db.update(Product).values(base_price=Decimal("899.00"))
                                  .execution_options(synchronize_session=False))

    event.listen(Session, "do_orm_execute", change_price_before_lock)
    try:
        place(seeded)
    finally:
        event.remove(Session, "do_orm_execute", change_price_before_lock)

    assert price_changed
    with seeded.application.app_context():
        order = Order.query.one()
        assert order.items[0].line_total == order.subtotal == order.total == Payment.query.one().amount == Decimal("899.00")


def test_repeated_checkout_does_not_duplicate_order(seeded):
    place(seeded)
    seeded.post("/checkout", data=DETAILS)
    with seeded.application.app_context():
        assert Order.query.count() == 1
        assert Inventory.query.one().quantity == 2
        assert OrderNotification.query.count() == 1
        assert OrderNotification.query.one().channel == "email"


def test_out_of_stock_does_not_place_order(seeded):
    with seeded.application.app_context():
        Inventory.query.one().quantity = 0
        db.session.commit()
    response = seeded.post("/checkout", data=DETAILS)
    assert b"no longer has enough stock" in response.data
    with seeded.application.app_context():
        assert Order.query.count() == 0
        assert OrderNotification.query.count() == 0


def test_alert_failure_keeps_order_and_retry_skips_submitted_channel(seeded, monkeypatch):
    seeded.application.config.update(PUBLIC_BASE_URL="https://shop.example.com", ORDER_ALERT_EMAIL="owner@example.com", ORDER_ALERT_WHATSAPP="919999999999")
    email = Mock()
    whatsapp = Mock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(alerts, "send_email", email)
    monkeypatch.setattr(alerts, "send_whatsapp", whatsapp)
    number = place(seeded)
    email.assert_not_called()
    whatsapp.assert_not_called()
    runner = seeded.application.test_cli_runner()
    assert runner.invoke(args=["send-order-alerts"]).exit_code == 0
    assert runner.invoke(args=["send-order-alerts"]).exit_code == 0
    assert whatsapp.call_count == 1
    assert email.call_count == 1
    assert f"https://shop.example.com/admin/orders/{number}" in email.call_args.args[2]
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"
        assert {n.channel: n.status for n in OrderNotification.query.all()} == {"email": "submitted", "whatsapp": "failed"}
    whatsapp.side_effect = None
    login(seeded, "owner@example.com")
    seeded.post(f"/admin/orders/{number}/retry-alerts")
    seeded.post(f"/admin/orders/{number}/retry-alerts")
    assert email.call_count == 1
    assert whatsapp.call_count == 2
    with seeded.application.app_context():
        assert all(n.status == "submitted" for n in OrderNotification.query.all())


def test_disabled_whatsapp_skips_previously_queued_alert(seeded, monkeypatch):
    seeded.application.config["ORDER_ALERT_WHATSAPP"] = ""
    whatsapp = Mock()
    monkeypatch.setattr(alerts, "send_whatsapp", whatsapp)
    place(seeded)
    with seeded.application.app_context():
        order = Order.query.one()
        notice = OrderNotification(order=order, channel="whatsapp")
        db.session.add(notice)
        db.session.commit()
        with seeded.application.test_request_context():
            alerts.dispatch_order_alerts(order.id)
        assert notice.status == "skipped"
        assert notice.attempts == 0
    whatsapp.assert_not_called()


def test_confirmation_requires_csrf(seeded):
    number = place(seeded)
    login(seeded, "owner@example.com")
    seeded.application.config["WTF_CSRF_ENABLED"] = True
    assert seeded.post(f"/admin/orders/{number}/confirm").status_code == 400
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"


def test_whatsapp_template_request_uses_seven_parameters(app, monkeypatch):
    app.config.update(WHATSAPP_ACCESS_TOKEN="test-token", WHATSAPP_PHONE_NUMBER_ID="12345",
        WHATSAPP_API_VERSION="v99.0", WHATSAPP_ORDER_TEMPLATE="owner_order", ORDER_ALERT_WHATSAPP="919999999999")
    import io, json
    opener = Mock(return_value=io.BytesIO(b'{"messages":[{"id":"mock-id"}]}'))
    monkeypatch.setattr(alerts, "urlopen", opener)
    with app.app_context():
        alerts.send_whatsapp(["ARD-1", "Buyer", "9999999999", "Test address", "Tee x 1", "INR 799.00", "https://shop.example.com/admin/orders/ARD-1"])
    request = opener.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["type"] == "template"
    assert len(payload["template"]["components"][0]["parameters"]) == 7
    assert request.full_url == "https://graph.facebook.com/v99.0/12345/messages"


def test_alert_cli_runs_in_app_context(app):
    result = app.test_cli_runner().invoke(args=["send-order-alerts"])
    assert result.exit_code == 0


def test_smtp_uses_tls_and_sends_complete_message(app, monkeypatch):
    from app.services import email as mail
    smtp = Mock()
    connection = Mock()
    connection.__enter__ = Mock(return_value=smtp)
    connection.__exit__ = Mock(return_value=False)
    smtp.send_message.return_value = {}
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(mail.smtplib, "SMTP", constructor)
    app.config.update(MAIL_SERVER="smtp.example.com", MAIL_PORT=587,
        MAIL_USERNAME="sender@example.com", MAIL_PASSWORD="test-password",
        MAIL_FROM="sender@example.com", MAIL_USE_TLS=True, MAIL_USE_SSL=False)
    with app.app_context():
        mail.send_email("owner@example.com", "New COD order", "<p>Review order</p>", "Review order")
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sender@example.com", "test-password")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "owner@example.com"
    assert "Review order" in message.get_body(preferencelist=("plain",)).get_content()


def test_checkout_renders_cod_and_saved_address(seeded):
    response = seeded.get("/checkout")
    assert response.status_code == 200
    assert b"Pay when it arrives" in response.data
    assert b"Place COD order" in response.data
    assert b"payment gateway" not in response.data
    assert b'value="Buyer Test"' in response.data
    seeded.post("/checkout", data={**DETAILS, "save_address": "1", "make_default": "1"})
    with seeded.application.app_context():
        from app.models import Address
        address = Address.query.one()
        assert address.is_default
        assert address.line1 == DETAILS["line1"]


def test_product_displays_variant_price_and_stock(seeded):
    with seeded.application.app_context():
        ProductVariant.query.one().price_override = Decimal("999")
        Inventory.query.one().quantity = 2
        db.session.commit()
    response = seeded.get("/product/everyday")
    assert response.status_code == 200
    assert b'data-price="999.00"' in response.data
    assert b'data-stock="2"' in response.data
    assert b"999.00" in response.data
    assert b'data-variant-form' in response.data


def test_sold_out_product_has_no_purchase_form(seeded):
    with seeded.application.app_context():
        Inventory.query.one().quantity = 0
        db.session.commit()
    response = seeded.get("/product/everyday")
    assert b"OUT OF STOCK" in response.data
    assert b"data-variant-form" not in response.data


def test_guest_shops_then_signs_in_at_checkout(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    page = seeded.get("/product/everyday")
    assert b"data-variant-form" in page.data
    assert b"Sign in to shop" not in page.data
    response = seeded.post("/cart/add", data={"variant_id": variant_id, "quantity": 1})
    assert response.location == "/cart"
    assert b"Everyday Tee" in seeded.get("/cart").data
    checkout = seeded.get("/checkout")
    assert "/auth/login?next=" in checkout.location
    login_page = seeded.get(checkout.location)
    assert b"Sign in to checkout" in login_page.data
    response = seeded.post(checkout.location, data={"email":"buyer@example.com", "password":PASSWORD})
    assert response.location == "/checkout"
    assert seeded.get(response.location).status_code == 200
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 2
    with seeded.session_transaction() as session:
        assert "guest_cart" not in session
    # Repeated login must not merge the same bag twice.
    seeded.post("/auth/logout")
    seeded.post("/auth/login", data={"email":"buyer@example.com", "password":PASSWORD})
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 2


def test_cart_warns_when_stock_changes(seeded):
    with seeded.application.app_context():
        CartItem.query.one().quantity = 3
        Inventory.query.one().quantity = 2
        db.session.commit()
    response = seeded.get("/cart")
    assert response.status_code == 200
    assert b"Only 2 available" in response.data
    assert b"Continue to checkout" not in response.data
    with seeded.application.app_context():
        item_id = CartItem.query.one().id
    seeded.post("/cart/update", data={"item_id":item_id, "quantity":2})
    assert b"Continue to checkout" in seeded.get("/cart").data


def test_inactive_cart_item_can_be_removed_but_not_updated(seeded):
    with seeded.application.app_context():
        Product.query.one().is_active = False
        item_id = CartItem.query.one().id
        db.session.commit()
    page = seeded.get("/cart")
    assert b"No longer available" in page.data
    assert b"Continue to checkout" not in page.data
    seeded.post("/cart/update", data={"item_id":item_id, "quantity":2})
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 1
    seeded.post("/cart/remove", data={"item_id":item_id})
    assert b"Your bag is empty" in seeded.get("/cart").data


@pytest.mark.parametrize("quantity", ["abc", "0", "-1", "100"])
def test_invalid_cart_quantity_is_not_added(seeded, quantity):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/cart/add", data={"variant_id":variant_id, "quantity":quantity}, headers={"Referer":"https://untrusted.example"})
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 1


def test_shop_sort_and_filter_controls_render_without_inline_scripts(seeded):
    response = seeded.get("/shop?category=tees&q=Everyday&sort=price_asc")
    assert response.status_code == 200
    assert b"Apply sort" in response.data
    assert b"onchange=" not in response.data
    assert b'name="category" value="tees"' in response.data
    assert b'category-pill active' in response.data


def test_guest_cart_update_remove_and_session_isolation(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    other_guest = seeded.application.test_client()
    assert guest.get("/cart").status_code == 200
    guest.post("/cart/add", data={"variant_id":variant_id, "quantity":1})
    assert b"Your bag is empty" in other_guest.get("/cart").data
    assert other_guest.post("/cart/update", data={"item_id":variant_id, "quantity":2}).status_code == 404
    guest.post("/cart/update", data={"item_id":variant_id, "quantity":2})
    with guest.session_transaction() as session:
        assert session["guest_cart"][str(variant_id)] == 2
    guest.post("/cart/remove", data={"item_id":variant_id})
    assert b"Your bag is empty" in guest.get("/cart").data
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 1


def test_failed_login_preserves_guest_bag(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    guest.post("/cart/add", data={"variant_id":variant_id, "quantity":1})
    guest.post("/auth/login?next=/checkout", data={"email":"buyer@example.com", "password":"incorrect"})
    with guest.session_transaction() as session:
        assert session["guest_cart"][str(variant_id)] == 1
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 1


def test_registration_keeps_guest_bag_and_checkout_destination(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    guest.post("/cart/add", data={"variant_id":variant_id, "quantity":1})
    response = guest.post("/auth/register?next=/checkout", data={"email":"new@example.com", "password":PASSWORD, "first_name":"New", "last_name":"Buyer"})
    assert response.location == "/auth/login?next=/checkout"
    response = guest.post(response.location, data={"email":"new@example.com", "password":PASSWORD})
    assert response.location == "/checkout"
    assert b"Everyday Tee" in guest.get("/checkout").data
    with seeded.application.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert Cart.query.filter_by(user_id=user.id).one().items[0].quantity == 1


def test_guest_add_respects_stock_and_csrf(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    guest.post("/cart/add", data={"variant_id":variant_id, "quantity":4})
    with guest.session_transaction() as session:
        assert not session.get("guest_cart")
    seeded.application.config["WTF_CSRF_ENABLED"] = True
    assert guest.post("/cart/add", data={"variant_id":variant_id, "quantity":1}).status_code == 400


def test_guest_merge_keeps_changed_stock_visible(seeded):
    with seeded.application.app_context():
        variant_id = ProductVariant.query.one().id
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    guest.post("/cart/add", data={"variant_id":variant_id, "quantity":2})
    with seeded.application.app_context():
        Inventory.query.one().quantity = 1
        db.session.commit()
    guest.post("/auth/login?next=/checkout", data={"email":"buyer@example.com", "password":PASSWORD})
    assert b"Only 1 available" in guest.get("/cart").data
    with seeded.application.app_context():
        assert CartItem.query.one().quantity == 3


def test_registration_rejects_external_next_url(seeded):
    seeded.post("/auth/logout")
    guest = seeded.application.test_client()
    response = guest.post("/auth/register?next=//untrusted.example", data={"email":"safe@example.com", "password":PASSWORD, "first_name":"Safe", "last_name":"Buyer"})
    assert response.location == "/auth/login"


def test_homepage_uses_live_catalogue_and_hides_inactive_products(seeded):
    with seeded.application.app_context():
        product = Product.query.one()
        product.is_new_arrival = True
        ProductVariant.query.one().price_override = Decimal("999")
        db.session.add(Product(name="Hidden draft", slug="hidden-draft", base_price=Decimal("100"), is_active=False))
        db.session.commit()
    page = seeded.get("/")
    assert page.status_code == 200
    assert b"Everyday Tee" in page.data
    assert b"999.00" in page.data
    assert b"Fresh fits. New energy." in page.data
    assert b"Hidden draft" not in page.data
    assert b"No featured products yet" not in page.data


def test_owner_fulfils_order_without_marking_payment_paid(seeded):
    number = place(seeded)
    assert seeded.post(f"/admin/orders/{number}/status", data={"status":"Shipped"}).status_code == 403
    login(seeded, "owner@example.com")
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Shipped"})
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"
    seeded.post(f"/admin/orders/{number}/confirm")
    assert b"Mark as shipped" in seeded.get(f"/admin/orders/{number}").data
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Shipped"})
    assert b"Mark as delivered" in seeded.get(f"/admin/orders/{number}").data
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Delivered"})
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Delivered"})
    with seeded.application.app_context():
        assert Order.query.one().status == "Delivered"
        assert Payment.query.one().status == "pending"
        assert AuditLog.query.filter_by(action="order.delivered").count() == 1
        assert Inventory.query.one().quantity == 2
    login(seeded, "buyer@example.com")
    assert seeded.get(f"/account/orders/{number}/status").json["label"] == "Order delivered"
    assert b"has been delivered" in seeded.get(f"/account/orders/{number}").data


@pytest.mark.parametrize("confirm_first", [False, True])
def test_cancellation_restores_stock_once_and_stops_alerts(seeded, confirm_first):
    number = place(seeded)
    login(seeded, "owner@example.com")
    if confirm_first:
        seeded.post(f"/admin/orders/{number}/confirm")
    for _ in range(2):
        seeded.post(f"/admin/orders/{number}/status", data={"status":"Cancelled", "reason":"Customer requested cancellation"})
    with seeded.application.app_context():
        from app.models import InventoryMovement
        assert Order.query.one().status == "Cancelled"
        assert Inventory.query.one().quantity == 3
        assert Payment.query.one().status == "cancelled"
        assert InventoryMovement.query.filter_by(reason="order_cancelled").count() == 1
        assert AuditLog.query.filter_by(action="order.cancelled").count() == 1
        assert all(n.status == "skipped" for n in OrderNotification.query.all())
    seeded.post(f"/admin/orders/{number}/retry-alerts")
    login(seeded, "buyer@example.com")
    state = seeded.get(f"/account/orders/{number}/status").json
    assert state["label"] == "Order cancelled"
    assert "No delivery payment is due" in state["message"]
    assert b"payable on delivery" not in seeded.get(f"/account/orders/{number}").data


def test_cancellation_requires_reason_and_rejects_shipped_orders(seeded):
    number = place(seeded)
    login(seeded, "owner@example.com")
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Cancelled", "reason":""})
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"
        assert Inventory.query.one().quantity == 2
    seeded.post(f"/admin/orders/{number}/confirm")
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Shipped"})
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Cancelled", "reason":"Too late"})
    with seeded.application.app_context():
        assert Order.query.one().status == "Shipped"
        assert Inventory.query.one().quantity == 2


def test_status_updates_require_post_and_csrf(seeded):
    number = place(seeded)
    login(seeded, "owner@example.com")
    assert seeded.get(f"/admin/orders/{number}/status").status_code == 405
    assert seeded.post(f"/admin/orders/{number}/status", data={"status":"Unknown"}).status_code == 400
    seeded.application.config["WTF_CSRF_ENABLED"] = True
    assert seeded.post(f"/admin/orders/{number}/status", data={"status":"Cancelled", "reason":"Test reason"}).status_code == 400


def test_admin_order_filters_and_search(seeded):
    number = place(seeded)
    login(seeded, "owner@example.com")
    assert number.encode() in seeded.get("/admin/orders?status=Pending&q=Buyer").data
    assert number.encode() not in seeded.get("/admin/orders?status=Delivered").data
    assert number.encode() not in seeded.get("/admin/orders?q=unknown").data
    assert seeded.get("/admin/orders?status=invalid").status_code == 400


def test_cancellation_does_not_restore_stock_for_paid_order(seeded):
    number = place(seeded)
    with seeded.application.app_context():
        Payment.query.one().status = "paid"
        db.session.commit()
    login(seeded, "owner@example.com")
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Cancelled", "reason":"Customer requested"})
    with seeded.application.app_context():
        assert Order.query.one().status == "Pending"
        assert Inventory.query.one().quantity == 2
        assert Payment.query.one().status == "paid"
        assert AuditLog.query.filter_by(action="order.cancelled").count() == 0


def test_cod_receipt_requires_delivery_and_records_once(seeded):
    number = place(seeded)
    endpoint = f"/admin/orders/{number}/payment-received"
    assert seeded.post(endpoint, data={"received":"yes"}).status_code == 403
    login(seeded, "owner@example.com")
    seeded.post(endpoint, data={"received":"yes"})
    with seeded.application.app_context():
        assert Payment.query.one().status == "pending"
    seeded.post(f"/admin/orders/{number}/confirm")
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Shipped"})
    seeded.post(f"/admin/orders/{number}/status", data={"status":"Delivered"})
    assert b"Record payment received" in seeded.get(f"/admin/orders/{number}").data
    seeded.post(endpoint)
    with seeded.application.app_context():
        assert Payment.query.one().status == "pending"
    for _ in range(2):
        seeded.post(endpoint, data={"received":"yes"})
    with seeded.application.app_context():
        assert Payment.query.one().status == "paid"
        assert Payment.query.one().paid_at is not None
        assert AuditLog.query.filter_by(action="order.payment_received").count() == 1
        assert Inventory.query.one().quantity == 2
        assert Order.query.one().status == "Delivered"
    page = seeded.get(f"/admin/orders/{number}")
    assert b"Payment received" in page.data
    assert b"Record payment received" not in page.data


def test_cod_receipt_rejects_mismatched_amount_and_requires_csrf(seeded):
    number = place(seeded)
    with seeded.application.app_context():
        Order.query.one().status = "Delivered"
        Payment.query.one().amount = Decimal("1")
        db.session.commit()
    login(seeded, "owner@example.com")
    endpoint = f"/admin/orders/{number}/payment-received"
    seeded.post(endpoint, data={"received":"yes"})
    with seeded.application.app_context():
        assert Payment.query.one().status == "pending"
        assert AuditLog.query.filter_by(action="order.payment_received").count() == 0
    assert seeded.get(endpoint).status_code == 405
    seeded.application.config["WTF_CSRF_ENABLED"] = True
    assert seeded.post(endpoint, data={"received":"yes"}).status_code == 400


def collection_owner(client):
    with client.application.app_context():
        owner = User.query.filter_by(email="owner@example.com").one()
        owner.roles[0].permissions.append(Permission(name="products.update"))
        db.session.commit()
    login(client, "owner@example.com")


def test_collection_create_edit_visibility_and_product_assignment(seeded):
    collection_owner(seeded)
    assert seeded.get("/admin/categories").status_code == 200
    assert seeded.get("/admin/categories/create").status_code == 200
    response = seeded.post("/admin/categories/create", data={"name":"Oversized Tees", "slug":"", "description":"Room to move.", "sort_order":"1", "is_active":"1"})
    assert response.location == "/admin/categories"
    with seeded.application.app_context():
        category = Category.query.filter_by(slug="oversized-tees").one()
        category_id = category.id
        Product.query.one().category_id = category.id
        db.session.commit()
    assert b"Room to move." in seeded.get("/shop?category=oversized-tees").data
    assert b"Oversized Tees" in seeded.get("/").data
    response = seeded.post(f"/admin/categories/{category_id}/edit", data={"name":"Relaxed Tees", "slug":"oversized-tees", "description":"", "sort_order":"0"})
    assert response.location == "/admin/categories"
    assert seeded.get("/shop?category=oversized-tees").status_code == 404
    assert b'href="/shop?category=oversized-tees"' not in seeded.get("/product/everyday").data
    assert b"Everyday Tee" in seeded.get("/shop").data
    with seeded.application.app_context():
        assert Product.query.one().category_id == category_id
        assert Category.query.filter_by(id=category_id).one().name == "Relaxed Tees"


def test_collection_rejects_duplicates_and_invalid_sort(seeded):
    collection_owner(seeded)
    for data in [{"name":"Duplicate", "slug":"tees", "sort_order":"0"}, {"name":"New", "slug":"new", "sort_order":"-1"}, {"name":"", "sort_order":"1"}]:
        assert seeded.post("/admin/categories/create", data=data).status_code == 200
    with seeded.application.app_context():
        assert Category.query.count() == 1
    assert seeded.get("/admin/categories/99999/edit").status_code == 404


def test_collection_mutations_require_permission_and_csrf(seeded):
    assert seeded.get("/admin/categories").status_code == 403
    assert seeded.post("/admin/categories/create", data={"name":"Test", "sort_order":"0"}).status_code == 403
    collection_owner(seeded)
    seeded.application.config["WTF_CSRF_ENABLED"] = True
    assert seeded.post("/admin/categories/create", data={"name":"Test", "sort_order":"0"}).status_code == 400


def test_checkout_rejects_overseas_address(seeded):
    response = seeded.post("/checkout", data={**DETAILS, "country":"USA", "postal_code":"12345"})
    assert b"only within India" in response.data
    with seeded.application.app_context():
        assert Order.query.count() == 0


def test_storefront_sort_matches_available_option_price(seeded):
    with seeded.application.app_context():
        ProductVariant.query.one().price_override = Decimal("1200")
        db.session.add(Product(name="Second style", slug="second-style", base_price=Decimal("1000")))
        db.session.commit()
    page = seeded.get("/shop?sort=price_asc")
    assert page.status_code == 200
    assert page.data.index(b"Second style") < page.data.index(b"Everyday Tee")
    assert b"1200.00" in page.data
    reverse = seeded.get("/shop?sort=price_desc")
    assert reverse.data.index(b"Everyday Tee") < reverse.data.index(b"Second style")


def test_public_pages_render_and_have_no_business_placeholders(seeded):
    seeded.post("/auth/logout")
    for path in ["/", "/shop", "/about", "/contact", "/shipping", "/returns", "/refund-policy", "/privacy", "/terms", "/cart", "/auth/login", "/auth/register", "/auth/forgot-password"]:
        page = seeded.get(path)
        assert page.status_code == 200, path
        assert b"ready for AR Drips business content" not in page.data
        assert b'href="/privacy"' in page.data
        assert b'href="/terms"' in page.data
    with seeded.application.app_context():
        for template in seeded.application.jinja_env.list_templates():
            seeded.application.jinja_env.get_template(template)


def test_admin_can_create_sellable_product_and_images_are_private_when_hidden(seeded, tmp_path):
    from io import BytesIO
    from PIL import Image
    from app.models import ProductImage
    seeded.application.config["UPLOAD_DIR"] = str(tmp_path)
    with seeded.application.app_context():
        owner = User.query.filter_by(email="owner@example.com").one()
        owner.roles[0].permissions.extend(Permission(name=name) for name in ["products.create", "products.update", "products.view"])
        category_id = Category.query.one().id
        db.session.commit()
    login(seeded, "owner@example.com")
    picture = BytesIO()
    Image.new("RGB", (20,20), "blue").save(picture, format="PNG")
    picture.seek(0)
    response = seeded.post("/admin/products/create", data={"name":"New hoodie", "slug":"new-hoodie", "description":"A test hoodie", "base_price":"1500", "category_id":category_id, "is_active":"1", "images":(picture,"hoodie.png")}, content_type="multipart/form-data")
    assert response.status_code == 302
    with seeded.application.app_context():
        product_id = Product.query.filter_by(slug="new-hoodie").one().id
        photo = ProductImage.query.filter_by(product_id=product_id).one()
        photo_id, key = photo.id, photo.storage_key
    response = seeded.post(f"/admin/products/{product_id}/variants", data={"size_name":"XL", "color_name":"Navy", "sku":"NEW-HOODIE-XL", "quantity":"5"})
    assert response.status_code == 302
    assert b"NEW-HOODIE-XL" in seeded.get(f"/admin/products/{product_id}/edit").data
    assert seeded.get(f"/product-image/{photo_id}").status_code == 200
    assert seeded.get(f"/media/{key}").status_code == 200
    with seeded.application.app_context():
        Product.query.filter_by(id=product_id).one().is_active = False
        db.session.commit()
    assert seeded.get(f"/product-image/{photo_id}").status_code == 404
    assert seeded.get(f"/media/{key}").status_code == 404


def test_password_reset_link_cannot_be_reused(seeded, monkeypatch):
    import re
    from app.auth import routes as auth
    sender = Mock()
    monkeypatch.setattr(auth, "send_email", sender)
    seeded.post("/auth/logout")
    seeded.post("/auth/forgot-password", data={"email":"buyer@example.com"})
    token = re.search(r"/auth/reset-password/([^\"]+)", sender.call_args.args[2]).group(1)
    path = "/auth/reset-password/" + token
    assert seeded.get(path).status_code == 200
    response = seeded.post(path, data={"password":"ReplacementPassword123!", "confirm_password":"ReplacementPassword123!"})
    assert response.status_code == 302
    assert seeded.get(path).status_code == 302
    response = seeded.post("/auth/login", data={"email":"buyer@example.com", "password":"ReplacementPassword123!"})
    assert response.status_code == 302
