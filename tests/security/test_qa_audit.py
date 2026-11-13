"""Audit regressions: security and isolation guarantees that must remain enforced."""
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess

import pytest
from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models import User, Order, Cart, CartItem, Address


def login(client, user, admin=False, password="QaPassword123!"):
    return client.post("/admin/login" if admin else "/auth/login", data={"email": user.email, "password": password})


def route_path(rule):
    return re.sub(r"<(?:(?:int|path|float|uuid):)?([^>]+)>",
                  lambda m: "summary" if m[1] == "kind" else "unknown" if m[1] in {"action", "token", "slug", "key", "order_number"} else "999999", rule.rule)


def test_every_state_changing_route_requires_csrf(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    checked = []
    for rule in app.url_map.iter_rules():
        for method in sorted(rule.methods & {"POST", "PUT", "PATCH", "DELETE"}):
            response = client.open(route_path(rule), method=method)
            assert response.status_code == 400, (method, rule.rule, response.status_code)
            checked.append(f"{method} {rule.rule}")
    assert len(checked) >= 35
    Path("qa_artifacts").mkdir(exist_ok=True)
    Path("qa_artifacts/csrf-routes.json").write_text(json.dumps(checked, indent=2), encoding="utf-8")


@pytest.mark.parametrize("actor", ["anonymous", "customer", "limited_admin", "super_admin",
    "dashboard.view", "products.view", "products.create", "products.update", "products.delete", "orders.manage",
    "customers.manage", "inventory.manage", "coupons.manage", "reviews.manage", "analytics.view", "settings.manage"])
def test_admin_route_access_matrix(app, client, qa_factory, actor):
    if actor == "customer":
        login(client, qa_factory.customer())
    elif actor in {"limited_admin", "super_admin"}:
        user = qa_factory.admin(permissions=()) if actor == "limited_admin" else qa_factory.admin(super_admin=True)
        assert login(client, user, admin=True).status_code == 302
    elif actor != "anonymous":
        user = qa_factory.admin(permissions=(actor,))
        assert login(client, user, admin=True).status_code == 302
    results = []
    # No object is present at 999999: authorized requests can return 404/400;
    # this matrix specifically verifies authentication and permission gates.
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith("admin.") or rule.endpoint in {"admin.login", "admin.logout"}:
            continue
        source = inspect.getsource(app.view_functions[rule.endpoint])
        permission = re.search(r"permission_required\(['\"]([^'\"]+)", source)
        for method in sorted(rule.methods & {"GET", "POST"}):
            response = client.open(route_path(rule), method=method)
            if actor == "anonymous":
                assert response.status_code == 302 and "/admin/login" in response.location
            elif actor == "customer" or (permission and actor not in {"anonymous", "customer", "super_admin", permission[1]}):
                assert response.status_code == 403, (actor, method, rule.rule, response.status_code)
            elif actor == "super_admin" or (permission and actor == permission[1]):
                assert response.status_code not in {401, 403, 500}, (method, rule.rule, response.status_code)
            results.append([actor, method, rule.rule, response.status_code])
    Path("qa_artifacts").mkdir(exist_ok=True)
    Path(f"qa_artifacts/admin-matrix-{actor}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", r"/\evil.example", "javascript:alert(1)"])
def test_login_rejects_external_redirects(client, customer, target):
    response = client.post("/auth/login", query_string={"next": target}, data={"email": customer.email, "password": "QaPassword123!"})
    assert response.status_code == 302
    assert response.location == "/account/"


def test_QA_AUTH_001_mixed_case_signup_can_sign_in(app, client):
    response = client.post("/auth/register", data={"email": "MiXeD@example.com", "first_name": "QA", "last_name": "User", "password": "QaPassword123!"})
    assert response.status_code == 302
    with app.app_context():
        user = User.query.one()
        assert check_password_hash(user.password_hash, "QaPassword123!")
        assert user.password_hash != "QaPassword123!"
    client.post("/auth/login", data={"email": "mixed@example.com", "password": "QaPassword123!"})
    assert client.get("/account/").status_code == 200, "QA-AUTH-001: signup preserves case but login lowercases the email"


def test_QA_AUTH_002_password_reset_revokes_other_customer_session(app, customer, monkeypatch):
    from app.security.tokens import make_token
    from app.auth import routes
    old_session = app.test_client()
    reset_session = app.test_client()
    assert login(old_session, customer).status_code == 302
    assert old_session.get("/account/").status_code == 200
    with app.app_context():
        token = make_token(f"{customer.id}:{hashlib.sha256(customer.password_hash.encode()).hexdigest()}", "password-reset")
    response = reset_session.post("/auth/reset-password/" + token, data={"password": "ReplacementPassword123!", "confirm_password": "ReplacementPassword123!"})
    assert response.status_code == 302
    assert old_session.get("/account/").status_code == 302, "QA-AUTH-002: an existing customer session remains authenticated after password reset"


@pytest.mark.parametrize("route,threshold,payload", [
    ("/auth/login", 5, {"email": "missing@example.com", "password": "wrong"}),
    ("/auth/register", 5, {}),
    ("/auth/forgot-password", 3, {"email": "missing@example.com"}),
])
def test_public_auth_rate_limits(app, client, route, threshold, payload):
    app.config["RATELIMIT_ENABLED"] = True
    limiter.init_app(app)
    try:
        with app.app_context(): limiter.reset()
        responses = [client.post(route, data=payload) for _ in range(threshold + 1)]
        assert responses[-1].status_code == 429
        assert all(r.status_code != 429 for r in responses[:-1])
    finally:
        limiter.enabled = False


def test_cross_customer_order_cart_and_address_isolation(app, client, qa_factory, customer, second_customer):
    order = qa_factory.order(customer=second_customer)
    variant = qa_factory.variant()
    with app.app_context():
        cart = Cart(user_id=second_customer.id)
        item = CartItem(cart=cart, variant_id=variant.id, quantity=1)
        address = Address(user_id=second_customer.id, recipient_name="Private", phone="9876543210", line1="Private", city="Mumbai", state="Maharashtra", postal_code="400001", country="India")
        db.session.add_all([item,address]); db.session.commit(); item_id=item.id; address_id=address.id
    login(client, customer)
    for path in (f"/account/orders/{order.order_number}", f"/account/orders/{order.order_number}/status", f"/checkout/success/{order.order_number}"):
        assert client.get(path).status_code == 404
    assert client.post("/cart/update", data={"item_id":item_id,"quantity":2}).status_code == 403
    assert client.post("/cart/remove", data={"item_id":item_id}).status_code == 403
    client.post("/account/address", data={"id":address_id,"user_id":second_customer.id,"recipient_name":"QA","phone":"9876543210","line1":"QA Street","city":"Mumbai","state":"Maharashtra","postal_code":"400001","country":"India"})
    with app.app_context():
        assert db.session.get(Address,address_id).line1 == "Private"
        assert db.session.get(CartItem,item_id).quantity == 1


def test_production_like_headers_and_no_error_details(app, client):
    app.config.update(TESTING=False, DEBUG=False, SESSION_COOKIE_SECURE=True)
    for path in ("/", "/missing-page", "/auth/login"):
        response = client.get(path, base_url="https://localhost")
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert b"Traceback" not in response.data
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"])
    if cookie:
        assert cookie.secure and cookie.http_only and cookie.same_site == "Lax"


def test_QA_CONFIG_001_testing_email_automation_cannot_inherit_live_flag():
    source = Path("app/config.py").read_text()
    namespace = {"__file__":str(Path("app/config.py").resolve())}
    from unittest.mock import patch
    with patch.dict("os.environ", {"CUSTOMER_EMAILS_ENABLED":"true"}):
        exec(compile(source,"app/config.py","exec"),namespace)
    assert namespace["TestingConfig"].CUSTOMER_EMAILS_ENABLED is False, "QA-CONFIG-001: TestingConfig re-enables email automation from environment"


def test_QA_SECURITY_001_uploads_are_all_gitignored():
    result = subprocess.run(["git", "-c", f"safe.directory={Path.cwd().as_posix()}", "check-ignore", "--no-index", "instance/uploads/products/999/private.jpg"], capture_output=True, text=True)
    assert result.returncode == 0, "QA-SECURITY-001: product uploads are explicitly allowed into Git"
