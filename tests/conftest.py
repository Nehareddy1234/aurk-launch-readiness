"""Isolated QA fixtures: never use the application database or real SMTP."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# Resolve this before importing app.config, which reads environment on import.
test_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL") or "sqlite:///:memory:"
url = make_url(test_url)
if url.get_backend_name() == "mysql":
    if url.host not in {"localhost", "127.0.0.1", "::1", "mysql"} or not url.database or not any(word in url.database.lower() for word in ("test", "qa")):
        raise RuntimeError("Refusing a non-local or non-test MySQL database")
elif test_url != "sqlite:///:memory:":
    raise RuntimeError("QA requires an in-memory SQLite or dedicated local MySQL test database")
os.environ["TEST_DATABASE_URL"] = test_url
os.environ["CUSTOMER_EMAILS_ENABLED"] = "false"
os.environ["MAIL_SERVER"] = ""
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""

from app import create_app
from app.extensions import db


@pytest.fixture(autouse=True)
def _push_request_context():
    """Override pytest-flask's implicit context: requests must be independent.

    A test-wide context caches Flask-Login users and SQLAlchemy objects across
    requests, hiding stale-session and catalog-change defects. Tests needing
    a context must explicitly enter app.app_context()/test_request_context().
    """
    yield


@pytest.fixture(autouse=True)
def block_external_effects(monkeypatch):
    import smtplib
    import socket
    from PIL import Image
    # Admin image validation changes Pillow's process-wide pixel limit.
    # Restore it after each test so execution order cannot change assertions.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", Image.MAX_IMAGE_PIXELS)
    def blocked_smtp(*args, **kwargs):
        raise AssertionError("QA forbids real SMTP; patch the email sender in this test")
    monkeypatch.setattr(smtplib, "SMTP", blocked_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked_smtp)
    original = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "localhost", "::1", "mysql"}:
            raise AssertionError("QA forbids non-local network connections")
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", local_only)


@pytest.fixture
def app(tmp_path, monkeypatch):
    from app.config import TestingConfig
    monkeypatch.setattr(TestingConfig, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(TestingConfig, "CUSTOMER_EMAILS_ENABLED", False)
    monkeypatch.setattr(TestingConfig, "SESSION_COOKIE_SECURE", False)
    app = create_app("testing")
    app.config.update(MAIL_SERVER="", MAIL_USERNAME="", MAIL_PASSWORD="", MAIL_FROM="",
                      ORDER_ALERT_EMAIL="", ORDER_ALERT_WHATSAPP="", INTEREST_NOTIFICATION_EMAIL="",
                      WHATSAPP_ACCESS_TOKEN="", CUSTOMER_EMAILS_ENABLED=False,
                      PUBLIC_BASE_URL="https://aurk.test")

    with app.app_context():
        if db.engine.dialect.name == "mysql":
            # MySQL persists Alembic's bookkeeping across fixtures; SQLite's
            # in-memory engine disappears when disposed. Reset test-only state.
            db.session.execute(db.text("DROP TABLE IF EXISTS alembic_version"))
            db.session.commit()
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def qa_factory(app):
    """Factories commit deliberately to exercise real request transaction boundaries.

    The app fixture recreates only the isolated test schema for each test.
    """
    from werkzeug.security import generate_password_hash
    from app.models import User, Role, Permission, Product, ProductVariant, Inventory, Category, Size, Color, Order
    from app.admin.security import ADMIN_PERMISSIONS
    from flask import has_app_context
    from functools import wraps
    def in_context(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            if has_app_context():
                return fn(*args, **kwargs)
            with app.app_context():
                item = fn(*args, **kwargs)
                db.session.refresh(item)
                # Return immutable scalar snapshots, not ORM objects that a
                # later factory commit may expire or reattach accidentally.
                return SimpleNamespace(**{column.key: getattr(item, column.key) for column in item.__mapper__.column_attrs})
        return call
    sequence = iter(range(1, 100000))
    @in_context
    def customer(**values):
        n = next(sequence)
        user = User(email=f"qa{n}@example.com", first_name="QA", last_name="Customer",
                    password_hash=generate_password_hash("QaPassword123!"), **values)
        db.session.add(user); db.session.commit()
        return user
    @in_context
    def admin(permissions=ADMIN_PERMISSIONS, super_admin=False):
        user = customer()
        role_name = "Super Admin" if super_admin else "Admin"
        role = Role.query.filter_by(name=role_name).first() or Role(name=role_name)
        for name in permissions:
            permission = Permission.query.filter_by(name=name).first() or Permission(name=name)
            if permission not in role.permissions: role.permissions.append(permission)
        user.roles.append(role); db.session.commit()
        return user
    @in_context
    def product(**values):
        n = next(sequence)
        category = Category(name=f"QA Category {n}", slug=f"qa-category-{n}")
        defaults = dict(name=f"QA Tee {n}", slug=f"qa-tee-{n}", base_price=999, category=category)
        defaults.update(values)
        item = Product(**defaults); db.session.add(item); db.session.commit(); return item
    @in_context
    def variant(product=None, stock=5, **values):
        n = next(sequence)
        product = product or factories.product()
        if not isinstance(product, Product):
            product = db.session.get(Product, product.id)
        defaults = dict(product=product, sku=f"QA-SKU-{n}", size=Size(name=f"Q{n}"), color=Color(name=f"QA{n}"))
        defaults.update(values)
        item = ProductVariant(**defaults); item.inventory = Inventory(quantity=stock, reserved_quantity=0)
        db.session.add(item); db.session.commit(); return item
    @in_context
    def order(customer=None, **values):
        customer = customer or factories.customer()
        n = next(sequence)
        defaults = dict(user_id=customer.id, order_number=f"QA-ORDER-{n}", status="Pending", subtotal=999, total=999,
                        shipping_name="QA Customer", shipping_phone="9876543210", shipping_line1="QA Street",
                        shipping_city="Mumbai", shipping_state="Maharashtra", shipping_postal_code="400001", shipping_country="India")
        defaults.update(values)
        item = Order(**defaults); db.session.add(item); db.session.commit(); return item
    factories = SimpleNamespace(customer=customer, admin=admin, product=product, variant=variant, order=order)
    return factories


@pytest.fixture
def customer(qa_factory):
    return qa_factory.customer()


@pytest.fixture
def second_customer(qa_factory):
    return qa_factory.customer()


@pytest.fixture
def product_factory(qa_factory):
    return qa_factory.product


@pytest.fixture
def variant_factory(qa_factory):
    return qa_factory.variant


@pytest.fixture
def order_factory(qa_factory):
    return qa_factory.order


@pytest.fixture
def db_session(app):
    with app.app_context():
        try:
            yield db.session
        finally:
            db.session.rollback()
            db.session.remove()


@pytest.fixture
def admin(qa_factory):
    return qa_factory.admin()


@pytest.fixture
def mocked_smtp(monkeypatch):
    from app.services import customer_emails, product_interests, order_notifications
    sender = Mock()
    for module in (customer_emails, product_interests, order_notifications):
        monkeypatch.setattr(module, "send_email", sender)
    return sender


@pytest.fixture
def frozen_time():
    from freezegun import freeze_time
    with freeze_time("2026-10-19 12:00:00") as frozen:
        yield frozen
