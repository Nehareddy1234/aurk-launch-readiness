"""Persistent owner alerts. Provider acceptance is not a delivery receipt."""
import json
import smtplib
import re
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import click
from flask import current_app, url_for
from flask.cli import with_appcontext

from app.extensions import db
from app.models import OrderNotification
from app.services.email import send_email


def queue_order_alerts(order):
    channels = ["email"]
    if current_app.config.get("ORDER_ALERT_WHATSAPP"):
        channels.append("whatsapp")
    for channel in channels:
        db.session.add(OrderNotification(order=order, channel=channel))


def order_review_url(order):
    base = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise RuntimeError("Configure PUBLIC_BASE_URL with the public HTTPS website address.")
    return base + url_for("admin.order_detail", order_number=order.order_number)


def alert_values(order):
    address = ", ".join(filter(None, [order.shipping_line1, order.shipping_line2,
        order.shipping_city, order.shipping_state, order.shipping_postal_code, order.shipping_country]))
    items = "; ".join(f"{i.product_name_snapshot} ({i.size_snapshot}, {i.color_snapshot}) x {i.quantity} - INR {i.line_total:.2f}" for i in order.items)
    return [order.order_number, order.shipping_name, order.shipping_phone,
            address, items, f"INR {order.total:.2f}", order_review_url(order)]


def send_whatsapp(values):
    config = current_app.config
    required = ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_API_VERSION",
                "WHATSAPP_ORDER_TEMPLATE", "ORDER_ALERT_WHATSAPP")
    if not all(config.get(key) for key in required):
        raise RuntimeError("WhatsApp sending is not configured.")
    version = config["WHATSAPP_API_VERSION"]
    phone_id = config["WHATSAPP_PHONE_NUMBER_ID"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+", version) or not phone_id.isdigit():
        raise RuntimeError("Invalid WhatsApp API configuration.")
    # Approved template parameters cannot contain tabs/newlines. Full details
    # are always available on the authenticated review page.
    parameters = [" ".join(value.split()) for value in values]
    parameters[4] = parameters[4][:350]
    payload = {"messaging_product": "whatsapp", "to": config["ORDER_ALERT_WHATSAPP"],
        "type": "template", "template": {"name": config["WHATSAPP_ORDER_TEMPLATE"],
        "language": {"code": config["WHATSAPP_TEMPLATE_LANGUAGE"]},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": value} for value in parameters]}]}}
    request = Request(f"https://graph.facebook.com/{version}/{phone_id}/messages",
        data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": "Bearer " + config["WHATSAPP_ACCESS_TOKEN"], "Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        result = json.load(response)
    if not result.get("messages"):
        raise RuntimeError("WhatsApp provider did not accept the message.")


def dispatch_order_alerts(order_id=None, batch_size=25):
    now = datetime.now(timezone.utc)
    eligible = OrderNotification.status.in_(["pending", "failed"])
    if order_id is None:
        eligible &= OrderNotification.attempts < 5
        eligible &= db.or_(OrderNotification.last_error.is_(None), ~OrderNotification.last_error.like("Delivery uncertain:%"))
        eligible &= db.or_(OrderNotification.next_attempt_at.is_(None), OrderNotification.next_attempt_at <= now)
    else:
        eligible &= OrderNotification.order_id == order_id
    ids = db.select(OrderNotification.id).where(eligible).order_by(OrderNotification.id).limit(batch_size)
    notification_ids = list(db.session.scalars(ids))
    for notification_id in notification_ids:
        notice = db.session.execute(db.select(OrderNotification).where(
            OrderNotification.id == notification_id, eligible).with_for_update()).scalar_one_or_none()
        if notice is None:
            db.session.commit()
            continue
        if notice.order.status == "Cancelled" or (
            notice.channel == "whatsapp" and not current_app.config.get("ORDER_ALERT_WHATSAPP")
        ):
            notice.status = "skipped"
            notice.last_error = None
            db.session.commit()
            continue
        notice.attempts += 1
        try:
            values = alert_values(notice.order)
            if notice.channel == "email":
                labels = ["Order", "Customer", "Phone", "Delivery address", "Items", "Cash on delivery total", "Review and confirm"]
                text = "New cash-on-delivery order awaiting your confirmation.\n\n" + "\n".join(f"{k}: {v}" for k, v in zip(labels, values))
                html = "<h1>New cash-on-delivery order</h1>" + "".join(f"<p><strong>{k}:</strong> {escape(v)}</p>" for k, v in zip(labels[:-1], values[:-1]))
                html += f'<p><a href="{escape(values[-1], quote=True)}">Review and confirm order</a></p><p>Sign in to your admin account to confirm.</p>'
                send_email(current_app.config["ORDER_ALERT_EMAIL"], f"New COD order {values[0]}", html, text)
            else:
                send_whatsapp(values)
            notice.next_attempt_at = None
            notice.status = "submitted"
            notice.submitted_at = datetime.now(timezone.utc)
            notice.last_error = None
        except Exception as exc:
            notice.status = "failed"
            delay_minutes = min(60, 2 ** min(notice.attempts - 1, 6))
            notice.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
            # Do not persist tokens, provider responses or customer details.
            notice.last_error = ("Delivery uncertain: check the provider/inbox before manually retrying."
                if isinstance(exc, (TimeoutError, ConnectionError, smtplib.SMTPServerDisconnected))
                else "Sending failed. Check channel settings and retry.")
            current_app.logger.warning("Order alert %s failed (%s)", notification_id, type(exc).__name__)
        db.session.commit()

    return len(notification_ids)


@click.command("send-order-alerts")
@with_appcontext
def send_order_alerts_command():
    """Retry pending or failed owner alerts (safe to schedule periodically)."""
    with current_app.test_request_context():
        dispatch_order_alerts()
    click.echo("Order alert processing completed; inspect status in Admin > Orders.")
