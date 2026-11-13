"""Transactional customer email outbox. Submitted means SMTP acceptance, not delivery."""
from datetime import datetime, timedelta, timezone
from email.utils import formataddr
from pathlib import Path
import smtplib
import click
from flask import current_app
from flask.cli import with_appcontext
from app.extensions import db
from app.models import CustomerEmail, User, ProductInterest
from app.services.email import send_email
from app.services.customer_email_templates import render_customer_order_email, render_customer_welcome_email, render_customer_interest_email


def queue_customer_email(kind, customer, order=None):
    if not current_app.config["CUSTOMER_EMAILS_ENABLED"]:
        return
    db.session.flush()
    key = f"{kind}:{order.id if order is not None else customer.id}"
    if db.session.scalar(db.select(CustomerEmail.id).where(CustomerEmail.event_key == key)) is None:
        db.session.add(CustomerEmail(event_key=key, kind=kind, user_id=customer.id,
            order_id=order.id if order else None, recipient=customer.email))


def send_rendered_email(recipient, rendered):
    send_email(recipient, rendered.subject, rendered.html, rendered.text,
        from_email=formataddr((rendered.from_name, rendered.from_email)), reply_to=rendered.reply_to,
        inline_images={"aurk-logo": (Path(current_app.static_folder) / "images/brand/email-logo.png").read_bytes()})


def queue_interest_acknowledgement(interest, customer):
    """Queue once per saved interest, atomically with the interest transaction.

    The event key prevents duplicate acknowledgements; no order is associated.
    """
    if not current_app.config["CUSTOMER_EMAILS_ENABLED"]:
        return
    key = f"notify_interest:{interest.id}"
    if db.session.scalar(db.select(CustomerEmail.id).where(CustomerEmail.event_key == key)) is None:
        db.session.add(CustomerEmail(event_key=key, kind="notify_interest", user_id=customer.id, interest_id=interest.id,
            recipient=customer.email))


def dispatch_customer_emails(limit=50):
    if not current_app.config["CUSTOMER_EMAILS_ENABLED"]:
        return 0
    now = datetime.now(timezone.utc)
    ids = list(db.session.scalars(db.select(CustomerEmail.id).where(
        CustomerEmail.status.in_(["pending", "failed"]), CustomerEmail.attempts < 5,
        db.or_(CustomerEmail.last_error.is_(None), ~CustomerEmail.last_error.like("Delivery uncertain:%")),
        CustomerEmail.next_attempt_at <= now).order_by(CustomerEmail.id).limit(limit)))
    processed = 0
    for email_id in ids:
        notice = db.session.scalar(db.select(CustomerEmail).where(CustomerEmail.id == email_id)
            .with_for_update().execution_options(populate_existing=True))
        if notice is None or notice.status not in {"pending", "failed"} or notice.attempts >= 5 or (notice.last_error or '').startswith('Delivery uncertain:'):
            db.session.commit()
            continue
        due = notice.next_attempt_at.replace(tzinfo=timezone.utc) if notice.next_attempt_at.tzinfo is None else notice.next_attempt_at
        if due > datetime.now(timezone.utc):
            db.session.commit()
            continue
        if not notice.customer.is_active or (notice.order_id and (
                notice.order is None or (notice.order.status == "Cancelled" and notice.kind != "order_cancelled"))):
            notice.status = "skipped"
            db.session.commit()
            continue
        expected_status = {"order_received":"Pending", "order_confirmed":"Confirmed", "order_shipped":"Shipped", "order_delivered":"Delivered", "order_cancelled":"Cancelled"}.get(notice.kind)
        if expected_status and notice.order and notice.order.status != expected_status:
            notice.status = "skipped"
            db.session.commit()
            continue
        notice.attempts += 1
        try:
            config = current_app.config
            if notice.kind in {"notify_interest", "product_available"}:
                interest = notice.interest
                if interest is None or interest.customer_id != notice.user_id or interest.product is None:
                    notice.status = "skipped"
                    db.session.commit()
                    continue
                if notice.kind == "product_available" and (not interest.product.is_purchasable or interest.product.hide_price or not any(v.is_active and v.inventory and v.inventory.quantity > v.inventory.reserved_quantity for v in interest.product.variants)):
                    notice.attempts -= 1
                    notice.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=30)
                    db.session.commit()
                    continue
                rendered = render_customer_interest_email(notice.customer, interest.product,
                    support_email=config["CUSTOMER_SUPPORT_EMAIL"], sender_email=config["CUSTOMER_NOREPLY_EMAIL"], available=notice.kind=="product_available")
            elif notice.kind == "welcome":
                rendered = render_customer_welcome_email(notice.customer,
                    support_email=config["CUSTOMER_SUPPORT_EMAIL"], sender_email=config["CUSTOMER_NOREPLY_EMAIL"])
            else:
                rendered = render_customer_order_email(notice.order, notice.kind, support_email=config["CUSTOMER_SUPPORT_EMAIL"])
            send_rendered_email(notice.recipient, rendered)
            notice.status = "submitted"
            notice.submitted_at = datetime.now(timezone.utc)
            notice.last_error = None
        except Exception as exc:
            notice.status = "failed"
            notice.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 60 * 2 ** notice.attempts))
            notice.last_error = ("Delivery uncertain: check the provider/inbox before manually retrying."
                if isinstance(exc, (TimeoutError, ConnectionError, smtplib.SMTPServerDisconnected))
                else "Sending failed. Check SMTP settings and sending approval.")
            current_app.logger.warning("Customer email %s failed (%s)", notice.id, type(exc).__name__)
        db.session.commit()
        processed += 1
    return processed


@click.command("send-customer-emails")
@click.option("--limit", default=50, type=click.IntRange(1, 500), show_default=True)
@with_appcontext
def send_customer_emails_command(limit):
    """Process due welcome/order emails; schedule from the project directory."""
    if not current_app.config["CUSTOMER_EMAILS_ENABLED"]:
        click.echo("Customer email automation is disabled. No messages sent.")
        return
    count = dispatch_customer_emails(limit)
    click.echo(f"Processed {count} customer email(s). Submitted means provider acceptance.")
    from app.services.product_interests import dispatch_interest_alerts
    sent = dispatch_interest_alerts(limit)
    click.echo(f"Submitted {sent} product interest alert(s) to the business inbox.")


@click.command("send-email-test")
@click.option("--to", "recipient", required=True, help="Your own controlled test inbox.")
@click.option("--kind", type=click.Choice(["welcome", "order_received", "order_confirmed", "notify_interest"]), default="welcome")
@with_appcontext
def send_email_test_command(recipient, kind):
    """Explicitly send one sample-only email to a selected test inbox."""
    from types import SimpleNamespace
    from app.security.validators import validate_email_address
    from scripts.preview_customer_emails import sample_order
    config = current_app.config
    try:
        recipient = validate_email_address(recipient)
        if kind == "notify_interest":
            rendered = render_customer_interest_email(SimpleNamespace(first_name="AURK test"),
                SimpleNamespace(name="AURK Upcoming Drop", slug="sample-drop"),
                support_email=config["CUSTOMER_SUPPORT_EMAIL"], sender_email=config["CUSTOMER_NOREPLY_EMAIL"])
        else:
            rendered = None
        rendered = rendered or (render_customer_welcome_email(SimpleNamespace(first_name="AURK test"),
            support_email=config["CUSTOMER_SUPPORT_EMAIL"], sender_email=config["CUSTOMER_NOREPLY_EMAIL"])
            if kind == "welcome" else render_customer_order_email(sample_order(), kind, support_email=config["CUSTOMER_SUPPORT_EMAIL"]))
        from dataclasses import replace
        rendered = replace(rendered, subject="[TEST] " + rendered.subject)
        send_rendered_email(recipient, rendered)
    except Exception as exc:
        current_app.logger.warning("Test email failed (%s)", type(exc).__name__)
        raise click.ClickException("Test email failed. Check SMTP credentials, domain/sender approval and connectivity.") from None
    click.echo("Test email accepted by SMTP. Check the inbox, spam folder and Reply-To behavior.")
