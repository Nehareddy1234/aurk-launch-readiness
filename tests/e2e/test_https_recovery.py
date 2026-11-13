"""Exercise real HTTPS, referrer policy and CSRF; never send real email."""
import re
import threading
from unittest.mock import Mock
import pytest
from werkzeug.serving import make_server


@pytest.fixture
def secure_recovery_store(app, qa_factory, monkeypatch):
    from app.auth import routes
    customer = qa_factory.customer()
    sender = Mock()
    monkeypatch.setattr(routes, 'send_email', sender)
    app.config.update(WTF_CSRF_ENABLED=True, SESSION_COOKIE_SECURE=True,
                      WTF_CSRF_SSL_STRICT=True)
    server = make_server('127.0.0.1', 0, app, ssl_context='adhoc')
    base = f'https://127.0.0.1:{server.server_port}'
    app.config['PUBLIC_BASE_URL'] = base
    observed = []

    @app.before_request
    def record_origin_only():
        from flask import request
        if request.method == 'POST' and request.endpoint in {'auth.forgot_password', 'auth.reset_password'}:
            observed.append(request.referrer)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield dict(base=base, customer=customer, sender=sender, observed=observed)
    server.shutdown()
    thread.join(timeout=5)


def test_customer_https_password_recovery(secure_recovery_store):
    from playwright.sync_api import sync_playwright, expect
    from urllib.parse import urlsplit
    store = secure_recovery_store
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, reduced_motion='reduce')
        context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
        page = context.new_page()
        page.set_default_timeout(8000)
        page.goto(store['base'] + '/auth/forgot-password')
        page.locator('[name="email"]').fill(store['customer'].email)
        page.get_by_role('button', name='Email me a reset link').click()
        expect(page.get_by_role('heading', name='Check your email')).to_be_visible()
        store['sender'].assert_called_once()
        reset_url = re.search(r'https://\S+/auth/reset-password/\S+', store['sender'].call_args.args[3]).group(0)
        page.goto(reset_url)
        page.locator('[name="password"]').fill('SecureCustomerPassword123!')
        page.locator('[name="confirm_password"]').fill('SecureCustomerPassword123!')
        page.get_by_role('button', name='Save new password').click()
        page.wait_for_url('**/auth/login')
        expect(page.get_by_text('Password updated. Sign in with your new password.')).to_be_visible()
        assert store['observed'] == [store['base'] + '/', store['base'] + '/']
        page.locator('[name="email"]').fill(store['customer'].email)
        page.locator('[name="password"]').fill('SecureCustomerPassword123!')
        page.locator('form button').first.click()
        page.wait_for_url('**/account/')
        context.close()
        browser.close()
