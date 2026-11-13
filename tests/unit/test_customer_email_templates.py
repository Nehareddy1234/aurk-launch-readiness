import pytest
from scripts.preview_customer_emails import sample_order
from app.services.customer_email_templates import render_customer_order_email


def test_notify_uses_shared_branding_and_escapes_product_name(app):
    from types import SimpleNamespace
    from app.services.customer_email_templates import render_customer_interest_email
    with app.app_context():
        result = render_customer_interest_email(SimpleNamespace(first_name="Buyer"),
            SimpleNamespace(name='<script>alert("x")</script>', slug="launch"), public_base_url="https://aurk.in")
    assert '<script>' not in result.html
    assert '&lt;script&gt;' in result.html
    assert 'bgcolor="#000000"' in result.html
    assert 'cid:aurk-logo' in result.html
    assert 'https://aurk.in/product/launch' in result.html
    assert result.from_email == result.reply_to == "no-reply@aurk.in"
    assert "We will update you when the drop is live" in result.text

@pytest.mark.parametrize("kind",["order_received","order_confirmed"])
def test_order_email_content_and_reply_address(app,kind,monkeypatch):
    def unexpected_send(*args,**kwargs):
        raise AssertionError("Rendering must not send email")
    monkeypatch.setattr("smtplib.SMTP",unexpected_send)
    monkeypatch.setattr("smtplib.SMTP_SSL",unexpected_send)
    with app.app_context():
        result=render_customer_order_email(sample_order(),kind,public_base_url="https://aurk.in")
    assert result.from_email==result.reply_to=="support@aurk.in"
    assert result.from_name=="AURK"
    for body in [result.html,result.text]:
        assert "2398.00" in body and "2598.00" in body and "200.00" in body
        assert "Sample Customer" in body and "Vintage Black" in body and "Off White" in body
        assert "https://aurk.in/account/orders/AURK-PREVIEW-001" in body
        assert "support@aurk.in" in body
        assert "not a payment receipt" in body
    if kind=="order_received":
        assert "AWAITING CONFIRMATION" in result.html
        assert "once it is confirmed" in result.text
    else:
        assert "Your order is confirmed" in result.text
        assert "has not shipped yet" in result.text


def test_order_email_escaping_and_optional_fields(app):
    order=sample_order()
    order.shipping_name='<script>alert("bad")</script>'
    order.items[0].product_name_snapshot='<img src=x onerror=bad>'
    with app.app_context():
        email=render_customer_order_email(order,"order_received",public_base_url="https://aurk.in")
    assert "<script>" not in email.html
    assert "&lt;script&gt;" in email.html
    assert '<img src=x' not in email.html
    assert 'None' not in email.html
    assert "Delivery: Free" in email.text

@pytest.mark.parametrize("origin",["http://aurk.in","https://aurk.in@evil.example","https://aurk.in/?x=1","https://aurk.in/#x","javascript:alert(1)",""])
def test_order_email_requires_clean_https_origin(app,origin):
    with app.app_context(),pytest.raises(ValueError):
        render_customer_order_email(sample_order(),"order_received",public_base_url=origin)


def test_order_email_rejects_unknown_template_and_header_injection(app):
    with app.app_context():
        with pytest.raises(ValueError):
            render_customer_order_email(sample_order(),"unknown",public_base_url="https://aurk.in")
        order=sample_order();order.order_number="TEST\nBcc:other@example.com"
        with pytest.raises(ValueError):
            render_customer_order_email(order,"order_received",public_base_url="https://aurk.in")


def test_welcome_template_is_personalized_and_has_no_secrets(app,monkeypatch):
    from types import SimpleNamespace
    from app.services.customer_email_templates import render_customer_welcome_email
    def unexpected_send(*args,**kwargs):
        raise AssertionError("Preview rendering must not send emails")
    monkeypatch.setattr("smtplib.SMTP",unexpected_send)
    monkeypatch.setattr("smtplib.SMTP_SSL",unexpected_send)
    with app.app_context():
        email=render_customer_welcome_email(SimpleNamespace(first_name="Alex",password_hash="SECRET-HASH",email="private@example.com"),public_base_url="https://aurk.in")
    assert email.from_email==email.reply_to=="no-reply@aurk.in"
    for body in (email.html,email.text):
        assert "Alex" in body and "support@aurk.in" in body
        assert "https://aurk.in/shop" in body and "https://aurk.in/account/" in body
        assert "SECRET-HASH" not in body and "private@example.com" not in body
        assert "unmonitored" in body
    assert "confirmed" not in email.subject.lower()


def test_welcome_escapes_name_and_validates_origin(app):
    from types import SimpleNamespace
    from app.services.customer_email_templates import render_customer_welcome_email
    user=SimpleNamespace(first_name="<script>bad()</script>")
    with app.app_context():
        email=render_customer_welcome_email(user,public_base_url="https://aurk.in")
        assert "<script>" not in email.html and "&lt;script&gt;" in email.html
        with pytest.raises(ValueError):
            render_customer_welcome_email(user,public_base_url="http://aurk.in")


@pytest.mark.parametrize("kind",["welcome","order_received","order_confirmed"])
def test_black_white_branding_with_uploaded_logo(app,kind):
    from types import SimpleNamespace
    from app.services.customer_email_templates import render_customer_welcome_email
    with app.app_context():
        rendered=(render_customer_welcome_email(SimpleNamespace(first_name="Alex"),public_base_url="https://aurk.in")
                  if kind=="welcome" else render_customer_order_email(sample_order(),kind,public_base_url="https://aurk.in"))
    assert 'src="cid:aurk-logo"' in rendered.html
    assert "#132337" not in rendered.html and "#eeece6" not in rendered.html
    assert "color:#ffffff" in rendered.html
    assert "background:#000000" in rendered.html or "background-color:#000000" in rendered.html


@pytest.mark.parametrize("kind",["welcome","order_received","order_confirmed"])
def test_all_emails_use_shared_dark_background(app,kind):
    from types import SimpleNamespace
    from app.services.customer_email_templates import render_customer_welcome_email
    with app.app_context():
        result=(render_customer_welcome_email(SimpleNamespace(first_name="Alex"),public_base_url="https://aurk.in")
                if kind=="welcome" else render_customer_order_email(sample_order(),kind,public_base_url="https://aurk.in"))
    assert 'name="color-scheme" content="dark"' in result.html
    assert 'class="email-shell aurk-background"' in result.html
    assert 'background-image:linear-gradient(#000000,#000000)' in result.html
    assert 'bgcolor="#000000"' in result.html
