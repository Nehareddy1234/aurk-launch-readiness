"""Render customer emails only. This module does not send or queue messages."""
from dataclasses import dataclass
from urllib.parse import urlsplit
from flask import current_app, url_for
from app.security.validators import validate_email_address

COPY = {
    "order_shipped": {"subject":"Your order is on its way | AURK", "eyebrow":"ORDER SHIPPED", "headline":"On its way to you.", "preheader":"Your order has been dispatched.", "introduction":"Your order has shipped. Open My orders for the tracking number and courier link."},
    "order_delivered": {"subject":"Your order was delivered | AURK", "eyebrow":"ORDER DELIVERED", "headline":"Your new fit has arrived.", "preheader":"Your order has been marked delivered.", "introduction":"Your order has been marked delivered. If you have not received it or need help, contact our support team."},
    "order_cancelled": {"subject":"Your order was cancelled | AURK", "eyebrow":"ORDER CANCELLED", "headline":"Your order is cancelled.", "preheader":"Your order has been cancelled. No delivery payment is due.", "introduction":"Your order has been cancelled. No delivery payment is due. Contact support if you have questions."},
    "order_received": {
        "subject": "We received your order | AURK",
        "eyebrow": "ORDER RECEIVED / AWAITING CONFIRMATION",
        "headline": "Your next fit starts here.",
        "preheader": "Order received. We will review it next. Pay when it arrives.",
        "introduction": "Thanks for choosing AURK. We have received your order and our team will review it. We will send another update once it is confirmed.",
    },
    "order_confirmed": {
        "subject": "Your order is confirmed | AURK",
        "eyebrow": "ORDER CONFIRMED / GETTING READY",
        "headline": "Confirmed. Your fit is next.",
        "preheader": "Your AURK order is confirmed. Our team will call you shortly.",
        "introduction": "Your order is confirmed. Our team will call you shortly to go over the details. Your order has not shipped yet; check My orders for its latest status.",
    },
}

@dataclass(frozen=True)
class RenderedCustomerEmail:
    subject: str
    html: str
    text: str
    from_name: str
    from_email: str
    reply_to: str


def render_customer_order_email(order, kind, *, public_base_url=None, support_email="support@aurk.in"):
    if kind not in COPY:
        raise ValueError("Choose order_received or order_confirmed.")
    base = _public_origin(public_base_url)
    support = validate_email_address(support_email)
    with current_app.test_request_context():
        order_url = base + url_for("orders.detail", order_number=order.order_number)
    values = {**COPY[kind], "order": order, "currency": order.currency or "INR",
              "website_url": base, "order_url": order_url, "support_email": support, "kind": kind}
    subject = COPY[kind]["subject"] + " | " + str(order.order_number)
    if "\r" in subject or "\n" in subject:
        raise ValueError("Invalid order number.")
    return RenderedCustomerEmail(subject=subject, html=current_app.jinja_env.get_template("emails/order.html").render(**{**values, "subject": subject}),
        text=current_app.jinja_env.get_template("emails/order.txt").render(**values), from_name="AURK", from_email=support, reply_to=support)


def _public_origin(public_base_url):
    base = (public_base_url if public_base_url is not None else current_app.config.get("PUBLIC_BASE_URL", "")).rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path):
        raise ValueError("Configure PUBLIC_BASE_URL as the public HTTPS website origin.")
    return base


def render_customer_welcome_email(customer, *, public_base_url=None, support_email="support@aurk.in", sender_email="no-reply@aurk.in"):
    base = _public_origin(public_base_url)
    support = validate_email_address(support_email)
    sender = validate_email_address(sender_email)
    with current_app.test_request_context():
        shop_url = base + url_for("products.shop")
        account_url = base + url_for("orders.dashboard")
    values = dict(first_name=customer.first_name, subject="Welcome to AURK. Make it yours.",
        website_url=base, shop_url=shop_url, account_url=account_url, support_email=support)
    return RenderedCustomerEmail(subject=values["subject"],
        html=current_app.jinja_env.get_template("emails/welcome.html").render(**values),
        text=current_app.jinja_env.get_template("emails/welcome.txt").render(**values),
        from_name="AURK", from_email=sender, reply_to=sender)


def render_customer_interest_email(customer, product, *, public_base_url=None,
                                   support_email="support@aurk.in", sender_email="no-reply@aurk.in", available=False):
    base = _public_origin(public_base_url)
    support = validate_email_address(support_email)
    sender = validate_email_address(sender_email)
    with current_app.test_request_context():
        product_url = base + url_for("products.detail", slug=product.slug)
    values = dict(first_name=customer.first_name, product_name=product.name,
        subject="You're on the list | AURK", preheader="Thanks for your interest. We will update you when the drop is live.",
        website_url=base, product_url=product_url, support_email=support)
    if available:
        values.update(subject="The drop is live | AURK", preheader=f"{product.name} is now available. Stock is not reserved.")
    template = "product_available" if available else "notify_interest"
    return RenderedCustomerEmail(subject=values["subject"],
        html=current_app.jinja_env.get_template(f"emails/{template}.html").render(**values),
        text=current_app.jinja_env.get_template(f"emails/{template}.txt").render(**values),
        from_name="AURK", from_email=sender, reply_to=sender)
