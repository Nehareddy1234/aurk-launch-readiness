from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Cart, Category, Color, Inventory, Product, ProductVariant, Role, Size, User

PASSWORD = "customer-password-123"


def customer(app, **overrides):
    with app.app_context():
        values = dict(email="customer@gmail.com", first_name="Test", last_name="Customer",
                      password_hash=generate_password_hash(PASSWORD), login_phone="+919876543210")
        values.update(overrides)
        user = User(**values)
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.mark.parametrize("identity", ["customer@gmail.com", "9876543210", "+91 98765 43210"])
def test_email_and_phone_preserve_checkout(app, client, identity, monkeypatch):
    user_id = customer(app)
    merge = Mock()
    monkeypatch.setattr("app.services.guest_cart.merge_into_account", merge)
    response = client.post("/auth/login?next=/checkout", data={"email": identity, "password": PASSWORD})
    assert response.location == "/checkout"
    assert merge.call_args.args[0].id == user_id
    with client.session_transaction() as session:
        assert session["_user_id"] == str(user_id)


def test_contact_phone_is_not_a_login_credential(app, client):
    customer(app, login_phone=None, phone="9876543210")
    response = client.post("/auth/login", data={"email": "9876543210", "password": PASSWORD})
    assert b"Invalid email, phone number or password" in response.data


@pytest.mark.parametrize("active,password", [(False, PASSWORD), (True, "wrong")])
def test_reject_bad_credentials(app, client, active, password):
    customer(app, is_active=active)
    client.post("/auth/login", data={"email": "9876543210", "password": password})
    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_register_normalizes_and_rejects_duplicate_phone(app, client):
    data = dict(first_name="New", last_name="Customer", email="new@example.com", password=PASSWORD, phone="9876543210")
    assert client.post("/auth/register?next=/checkout", data=data).status_code == 302
    with app.app_context():
        assert User.query.filter_by(email=data["email"]).one().login_phone == "+919876543210"
    data["email"] = "other@example.com"
    assert b"Unable to create account" in client.post("/auth/register", data=data).data


def test_manage_phone_requires_password(app, client):
    customer(app)
    client.post("/auth/login", data={"email": "customer@gmail.com", "password": PASSWORD})
    client.post("/auth/login-phone", data={"phone": "9123456789", "password": "wrong"})
    with app.app_context():
        assert User.query.one().login_phone == "+919876543210"
    assert client.post("/auth/login-phone", data={"phone": "9123456789", "password": PASSWORD}).status_code == 302
    with app.app_context():
        assert User.query.one().login_phone == "+919123456789"


@pytest.fixture
def google(app):
    app.config.update(GOOGLE_CLIENT_ID="test", GOOGLE_CLIENT_SECRET="test", GOOGLE_REDIRECT_URI="http://localhost/auth/google/callback")
    provider = Mock()
    app.extensions["customer_oauth"] = SimpleNamespace(google=provider)
    provider.authorize_access_token.return_value = {"userinfo": {"sub": "google-sub", "email": "customer@gmail.com", "email_verified": True, "given_name": "Test"}}
    return provider


def test_google_signin_creates_customer_and_merges_bag(app, client, google):
    with app.app_context():
        category = Category(name="Tees", slug="tees")
        size, color = Size(name="M"), Color(name="Black")
        db.session.add_all([category, size, color])
        db.session.flush()
        product = Product(name="Test Tee", slug="test-tee", base_price=Decimal("500"), category_id=category.id)
        db.session.add(product)
        db.session.flush()
        variant = ProductVariant(product_id=product.id, size_id=size.id, color_id=color.id, sku="TEST-M")
        db.session.add(variant)
        db.session.flush()
        db.session.add(Inventory(variant_id=variant.id, quantity=3, reserved_quantity=0))
        variant_id = variant.id
        db.session.commit()

    with client.session_transaction() as session:
        session["guest_cart"] = {str(variant_id): 2}
    login_page = client.get("/auth/login?next=/checkout")
    assert "form-action 'self' https://accounts.google.com" in login_page.headers["Content-Security-Policy"]
    google.authorize_redirect.return_value = app.redirect("https://accounts.google.com/")
    assert client.post("/auth/google?next=/checkout").location == "https://accounts.google.com/"
    google.authorize_redirect.assert_called_once_with("http://localhost/auth/google/callback")
    assert client.get("/auth/google/callback").location == "/checkout"
    assert client.get("/checkout").status_code == 200
    with app.app_context():
        user = User.query.one()
        assert user.google_sub == "google-sub"
        assert not user.roles
        cart = Cart.query.filter_by(user_id=user.id).one()
        assert [(item.variant_id, item.quantity) for item in cart.items] == [(variant_id, 2)]
    with client.session_transaction() as session:
        assert "guest_cart" not in session


@pytest.mark.parametrize("case", ["unverified", "state", "inactive", "staff", "thirdparty"])
def test_google_rejects_unsafe_identities(app, client, google, case):
    if case == "unverified":
        google.authorize_access_token.return_value["userinfo"]["email_verified"] = False
    elif case == "state":
        google.authorize_access_token.side_effect = ValueError("invalid state or nonce")
    elif case == "thirdparty":
        customer(app, email="customer@example.com")
        google.authorize_access_token.return_value["userinfo"]["email"] = "customer@example.com"
    elif case == "inactive":
        customer(app, is_active=False)
    else:
        user_id = customer(app)
        with app.app_context():
            user = db.session.get(User, user_id)
            user.roles.append(Role(name="Admin"))
            db.session.commit()
    assert "/auth/login" in client.get("/auth/google/callback").location
    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_google_disabled_and_safe_redirect(app, client):
    app.config.update(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="", GOOGLE_REDIRECT_URI="")
    assert b'disabled>Continue with Google' in client.get("/auth/login").data
    customer(app)
    response = client.post("/auth/login?next=//evil.example", data={"email": "customer@gmail.com", "password": PASSWORD})
    assert response.location == "/account/"

