import re
from unittest.mock import Mock

import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import User, Role
from app.auth import routes


@pytest.fixture
def recovery(app, monkeypatch):
    with app.app_context():
        db.session.add(User(email="admin@example.com", first_name="Store", last_name="Owner",
            password_hash=generate_password_hash("OriginalPassword123!"), roles=[Role(name="Admin")]))
        db.session.commit()
    sender = Mock()
    monkeypatch.setattr(routes, "send_email", sender)
    app.config["PUBLIC_BASE_URL"] = "https://store.example.com"
    return sender


def reset_path(client, sender):
    response = client.post("/auth/forgot-password?admin=1", data={"email": "admin@example.com"})
    assert b"Check your email" in response.data
    return re.search(r'/auth/reset-password/([^"< ]+)', sender.call_args.args[2]).group(0)


def test_admin_email_reset_and_single_use(client, recovery):
    page = client.get("/admin/login")
    assert b"/auth/forgot-password?admin=1" in page.data
    path = reset_path(client, recovery)
    assert "https://store.example.com" in recovery.call_args.args[3]
    page = client.get(path)
    assert page.status_code == 200
    assert page.headers["Referrer-Policy"] == "strict-origin"
    assert page.headers["Cache-Control"] == "no-store, private"
    assert b"confirm_password" in page.data
    response = client.post(path, data={"password": "NewAdminPassword123!", "confirm_password": "NewAdminPassword123!"})
    assert response.location == "/admin/login"
    assert client.get(path).status_code == 302
    response = client.post("/admin/login", data={"email": "admin@example.com", "password": "NewAdminPassword123!"})
    assert response.location == "/admin/dashboard"


@pytest.mark.parametrize("password,confirmation", [("short", "short"), ("NewPassword123!", "mismatch"), ("x" * 1025, "x" * 1025)])
def test_invalid_password_preserves_account(client, recovery, password, confirmation):
    path = reset_path(client, recovery)
    assert client.post(path, data={"password": password, "confirm_password": confirmation}).status_code == 200
    with client.application.app_context():
        assert check_password_hash(User.query.one().password_hash, "OriginalPassword123!")


def test_unknown_email_and_smtp_failure_show_same_confirmation(client, recovery):
    unknown = client.post("/auth/forgot-password?admin=1", data={"email": "unknown@example.com"})
    recovery.assert_not_called()
    recovery.side_effect = RuntimeError("SMTP unavailable")
    known = client.post("/auth/forgot-password?admin=1", data={"email": "admin@example.com"})
    assert unknown.data == known.data
    assert known.status_code == 200


def test_invalid_expired_token_and_csrf(client, recovery, monkeypatch):
    assert client.get("/auth/reset-password/tampered").location == "/auth/forgot-password"
    path = reset_path(client, recovery)
    monkeypatch.setattr(routes, "read_token", Mock(side_effect=ValueError("Expired")))
    assert client.get(path).location == "/auth/forgot-password"
    client.application.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/auth/forgot-password", data={"email": "admin@example.com"}).status_code == 400


def test_reset_url_uses_configured_domain(client, recovery):
    client.post("/auth/forgot-password", data={"email": "admin@example.com"}, headers={"Host": "attacker.example"})
    assert "attacker.example" not in recovery.call_args.args[3]
    assert "https://store.example.com" in recovery.call_args.args[3]


def test_customer_fresh_reset_link_and_login(client, qa_factory, monkeypatch):
    from urllib.parse import urlsplit
    user = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    client.post('/auth/forgot-password', data={'email': user.email})
    url = re.search(r'https://\S+/auth/reset-password/\S+', sender.call_args.args[3]).group(0)
    path = urlsplit(url).path
    # Opening/scanning the email link must not consume it.
    assert client.get(path).status_code == 200
    assert client.get(path).status_code == 200
    response = client.post(path, data={'password':'NewCustomerPassword123!', 'confirm_password':'NewCustomerPassword123!'})
    assert response.location == '/auth/login'
    assert client.get(path).location == '/auth/forgot-password'
    client.post('/auth/login', data={'email':user.email, 'password':'NewCustomerPassword123!'})
    assert client.get('/account/').status_code == 200


def test_customer_link_expires_after_thirty_minutes(client, qa_factory, monkeypatch):
    from urllib.parse import urlsplit
    from freezegun import freeze_time
    user = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    with freeze_time('2026-10-28 10:00:00'):
        client.post('/auth/forgot-password', data={'email':user.email})
        url = re.search(r'https://\S+/auth/reset-password/\S+', sender.call_args.args[3]).group(0)
        path = urlsplit(url).path
        assert client.get(path).status_code == 200
    with freeze_time('2026-10-28 10:31:00'):
        assert client.get(path).location == '/auth/forgot-password'


def test_customer_recovery_accepts_trailing_slashes(client, qa_factory, monkeypatch):
    from urllib.parse import urlsplit
    user = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    assert client.get('/auth/forgot-password/').status_code == 200
    response = client.post('/auth/forgot-password/', data={'email':user.email})
    assert response.status_code == 200
    sender.assert_called_once()
    path = urlsplit(re.search(r'https://\S+/auth/reset-password/\S+', sender.call_args.args[3]).group(0)).path
    assert client.get(path + '/').status_code == 200
    response = client.post(path + '/', data={'password':'TrailingSlashPassword123!', 'confirm_password':'TrailingSlashPassword123!'})
    assert response.location == '/auth/login'
    assert client.get(path).location == '/auth/forgot-password'


@pytest.mark.parametrize('expired', [False, True])
def test_recovery_csrf_rejection_refreshes_form_without_sending(client, qa_factory, monkeypatch, expired):
    from freezegun import freeze_time
    user = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    client.application.config['WTF_CSRF_ENABLED'] = True
    with freeze_time('2026-10-28 10:00:00'):
        original = client.get('/auth/forgot-password')
        token = re.search(r'name="csrf_token" value="([^"]+)"', original.data.decode()).group(1)
    with freeze_time('2026-10-28 11:01:00'):
        payload = {'email':user.email}
        if expired:
            payload['csrf_token'] = token
        response = client.post('/auth/forgot-password', data=payload)
        assert response.status_code == 400
        assert b'Your form session expired or changed' in response.data
        sender.assert_not_called()
        fresh = re.search(r'name="csrf_token" value="([^"]+)"', response.data.decode()).group(1)
        response = client.post('/auth/forgot-password', data={'email':user.email, 'csrf_token':fresh})
        assert response.status_code == 200
        assert b'Check your email' in response.data
        sender.assert_called_once()


def test_https_recovery_still_rejects_foreign_origin(client, qa_factory, monkeypatch):
    user = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    client.application.config.update(WTF_CSRF_ENABLED=True, WTF_CSRF_SSL_STRICT=True)
    response = client.get('/auth/forgot-password', base_url='https://localhost')
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.data.decode()).group(1)
    response = client.post('/auth/forgot-password', base_url='https://localhost',
        data={'email':user.email, 'csrf_token':token}, headers={'Referer':'https://untrusted.example/'})
    assert response.status_code == 400
    sender.assert_not_called()
