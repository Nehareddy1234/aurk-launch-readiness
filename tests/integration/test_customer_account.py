from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User, Order, Address

PASSWORD = "StrongPassword123!"
DETAILS = dict(recipient_name="Account Buyer", phone="9876543210", line1="12 New Street", line2="",
               city="Mumbai", state="Maharashtra", postal_code="400001", country="India")

@pytest.fixture
def account(client):
    with client.application.app_context():
        password_hash = generate_password_hash(PASSWORD)
        buyer = User(email="account@example.com", first_name="Account", last_name="Buyer", password_hash=password_hash)
        other = User(email="other@example.com", first_name="Other", last_name="Buyer", password_hash=password_hash)
        db.session.add_all([buyer, other])
        db.session.commit()
        ids = buyer.id, other.id
    response = client.post("/auth/login", data={"email":"account@example.com", "password":PASSWORD})
    assert response.location.endswith("/account/")
    return ids

def add_order(user_id, number, status="Pending"):
    return Order(user_id=user_id, order_number=number, status=status, subtotal=Decimal("999"), total=Decimal("999"),
        shipping_name="Account Buyer", shipping_phone="9876543210", shipping_line1="Original Street",
        shipping_city="Mumbai", shipping_state="Maharashtra", shipping_postal_code="400001", shipping_country="India")

def test_account_requires_login(client):
    for path in ("/account", "/account/", "/account/orders"):
        assert "/auth/login" in client.get(path).location
    for path in ("/account/profile", "/account/address"):
        assert "/auth/login" in client.post(path).location

def test_dashboard_empty_and_private(client, account):
    page=client.get("/account/")
    assert page.status_code == 200
    assert b"Hey, Account." in page.data
    assert b"No orders yet" in page.data
    assert page.headers["Cache-Control"] == "no-store, private"
    assert page.headers["X-Robots-Tag"] == "noindex, nofollow"

def test_orders_scoped_and_paginated(client, account):
    buyer, other=account
    with client.application.app_context():
        db.session.add_all([add_order(buyer, f"OWN-{i:02}", "Delivered" if i==0 else "Confirmed") for i in range(15)])
        db.session.add(add_order(other,"PRIVATE-OTHER"))
        db.session.add(Address(user_id=other, **{**DETAILS,"line1":"Secret Other Address"}, is_default=True))
        db.session.commit()
    page=client.get("/account/")
    assert b"PRIVATE-OTHER" not in page.data and b"Secret Other Address" not in page.data
    assert page.data.count(b'class="account-order"') == 4
    assert b'OWN-14' in page.data
    assert b'OWN-00' not in page.data
    orders=client.get("/account/orders?page=2")
    assert orders.status_code == 200
    assert b"Page 2 of 2" in orders.data and b"OWN-00" in orders.data
    assert b"PRIVATE-OTHER" not in orders.data
    assert client.get("/account/orders/PRIVATE-OTHER").status_code == 404

def test_profile_updates_only_allowed_fields(client, account):
    buyer, other=account
    response=client.post("/account/profile",data=dict(first_name="New",last_name="Name",phone="+91 9876543210",
        email="hijack@example.com",user_id=other,is_active="0",roles="Admin"))
    assert response.location.endswith("#profile")
    with client.application.app_context():
        user=db.session.get(User,buyer)
        assert user.first_name=="New" and user.phone=="+91 9876543210"
        assert user.email=="account@example.com" and user.is_active and not user.roles
        assert db.session.get(User,other).first_name=="Other"
    client.post("/account/profile",data=dict(first_name="",last_name="Name",phone="bad"))
    with client.application.app_context():
        assert db.session.get(User,buyer).first_name=="New"

def test_address_scoped_and_preserves_order_snapshot(client, account):
    buyer, other=account
    with client.application.app_context():
        foreign=Address(user_id=other,**DETAILS,is_default=True)
        db.session.add_all([foreign,add_order(buyer,"OLD-ORDER")])
        db.session.commit()
        foreign_id=foreign.id
    assert client.post("/account/address",data={**DETAILS,"id":foreign_id,"user_id":other}).status_code==302
    client.post("/account/address",data={**DETAILS,"line1":"Updated Street"})
    with client.application.app_context():
        assert Address.query.filter_by(user_id=buyer).count()==1
        own=Address.query.filter_by(user_id=buyer).one()
        assert own.line1=="Updated Street" and own.is_default
        assert db.session.get(Address,foreign_id).line1=="12 New Street"
        assert Order.query.filter_by(order_number="OLD-ORDER").one().shipping_line1=="Original Street"

@pytest.mark.parametrize("overrides", [{"country":"USA"},{"postal_code":"123"},{"phone":"invalid"},{"line1":""}])
def test_address_validation(client, account, overrides):
    client.post("/account/address",data={**DETAILS,**overrides})
    with client.application.app_context():
        assert Address.query.filter_by(user_id=account[0]).count()==0

def test_account_forms_require_csrf(client, account):
    client.application.config["WTF_CSRF_ENABLED"]=True
    assert client.post("/account/profile",data=dict(first_name="Bad",last_name="Change")).status_code==400
    assert client.post("/account/address",data=DETAILS).status_code==400
    with client.application.app_context():
        assert db.session.get(User,account[0]).first_name=="Account"
        assert Address.query.count()==0
