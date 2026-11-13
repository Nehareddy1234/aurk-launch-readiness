"""Persist interest before SMTP delivery; failed notifications remain retryable."""
from datetime import datetime, timedelta, timezone
import smtplib
from html import escape

import click
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Product, ProductInterest
from app.services.email import send_email


def due_interest_filter():
    now = datetime.now(timezone.utc)
    return db.and_(ProductInterest.notified_at.is_(None), ProductInterest.notification_attempts < 5,
        db.or_(ProductInterest.notification_next_attempt_at.is_(None), ProductInterest.notification_next_attempt_at <= now),
        db.or_(ProductInterest.notification_last_error.is_(None), ~ProductInterest.notification_last_error.like("Delivery uncertain:%")))


def dispatch_interest_alerts(limit=100):
    ids = list(db.session.scalars(db.select(ProductInterest.id).where(due_interest_filter())
        .order_by(ProductInterest.id).limit(limit)))
    db.session.rollback()
    return sum(notify_interest(interest_id) for interest_id in ids)


def notify_interest(interest_id):
    try:
        interest = db.session.scalar(db.select(ProductInterest).where(ProductInterest.id == interest_id, due_interest_filter())
            .with_for_update().execution_options(populate_existing=True))
        if not interest:
            db.session.rollback()
            return False
        body = "\n\n".join([
            "Product Interest Notification", f"Product:\n{interest.product.name}",
            f"Product ID:\n{interest.product_id}", f"Status:\n{Product.STATUSES[interest.product_status]}",
            f"Customer:\n{interest.customer_name or 'Guest'}",
            f"Customer Email:\n{interest.customer_email or 'Not provided'}",
            f"Customer Phone:\n{interest.customer_phone or 'Not provided'}",
            f"Time:\n{interest.created_at:%Y-%m-%d %H:%M:%S} UTC",
        ])
        name = " ".join(interest.product.name.splitlines())
        support = current_app.config["CUSTOMER_SUPPORT_EMAIL"]
        interest.notification_attempts += 1
        try:
            send_email(current_app.config.get("INTEREST_NOTIFICATION_EMAIL") or support,
                f"New Product Interest - {name}", f"<pre>{escape(body)}</pre>", body,
                from_email=support, reply_to=interest.customer_email or support)
            interest.notified_at = datetime.now(timezone.utc)
            interest.notification_next_attempt_at = None
            interest.notification_last_error = None
            sent = True
        except Exception as exc:
            interest.notification_next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** (interest.notification_attempts - 1))
            interest.notification_last_error = (
                "Delivery uncertain: check the provider/inbox before manually retrying."
                if isinstance(exc, (TimeoutError, ConnectionError, smtplib.SMTPServerDisconnected))
                else "Sending failed. Check SMTP settings before retrying.")
            current_app.logger.warning("Product interest %s notification failed (%s).", interest_id, type(exc).__name__)
            sent = False
        db.session.commit()
        return sent
    except Exception:
        db.session.rollback()
        current_app.logger.warning("Product interest %s notification transaction failed; inspect provider before retry.", interest_id)
        return False


@click.command("send-interest-alerts")
@with_appcontext
def send_interest_alerts_command():
    """Retry up to 100 pending product interest emails (schedule periodically)."""
    sent = dispatch_interest_alerts()
    click.echo(f"Sent {sent} due product interest alert(s). Exhausted or uncertain deliveries need operator review.")


@click.command("retry-interest-alert")
@click.argument("interest_id", type=click.IntRange(1))
@click.option("--reviewed", is_flag=True, help="Confirm provider/inbox review and accept the risk of duplicate delivery.")
@with_appcontext
def retry_interest_alert_command(interest_id, reviewed):
    """Requeue one reviewed failed owner alert; sends nothing immediately."""
    if not reviewed:
        raise click.ClickException("Review the provider/inbox first, then pass --reviewed for this one alert.")
    interest = db.session.scalar(db.select(ProductInterest).where(ProductInterest.id == interest_id).with_for_update())
    if not interest or interest.notified_at or not interest.notification_last_error:
        db.session.rollback()
        raise click.ClickException("Only an existing failed, unsent alert can be requeued.")
    interest.notification_attempts = 0
    interest.notification_next_attempt_at = None
    interest.notification_last_error = None
    db.session.commit()
    click.echo(f"Requeued interest alert {interest_id}; the worker will process it. No email sent by this command.")
