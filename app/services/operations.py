"""Read-only operational signals for a scheduler/monitor, without customer data."""
from datetime import datetime, timedelta, timezone
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models import CustomerEmail, OrderNotification, ProductInterest, Order


@click.command("check-operations")
@click.option("--max-queue-age-minutes", default=15, type=click.IntRange(1, 1440))
@with_appcontext
def check_operations_command(max_queue_age_minutes):
    """Exit nonzero for stale, exhausted or uncertain notification queues."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_queue_age_minutes)
    failures = []
    queues = [
        ("customer emails", CustomerEmail, CustomerEmail.status.in_(["pending", "failed"]),
         CustomerEmail.attempts, CustomerEmail.next_attempt_at, CustomerEmail.last_error, CustomerEmail.created_at),
        ("order alerts", OrderNotification, OrderNotification.status.in_(["pending", "failed"]),
         OrderNotification.attempts, OrderNotification.next_attempt_at, OrderNotification.last_error, db.select(Order.created_at).where(Order.id == OrderNotification.order_id).scalar_subquery()),
        ("interest alerts", ProductInterest, ProductInterest.notified_at.is_(None),
         ProductInterest.notification_attempts, ProductInterest.notification_next_attempt_at,
         ProductInterest.notification_last_error, ProductInterest.created_at),
    ]
    try:
        for label, model, pending, attempts, due, error, created in queues:
            count = lambda condition: db.session.scalar(db.select(db.func.count()).select_from(model).where(pending, condition))
            exhausted = count(attempts >= 5)
            uncertain = count(error.like("Delivery uncertain:%"))
            stale = count(db.and_(created < cutoff, db.or_(due.is_(None), due <= now)))
            click.echo(f"{label}: stale={stale}, exhausted={exhausted}, uncertain={uncertain}")
            if stale or exhausted or uncertain:
                failures.append(label)
    finally:
        db.session.rollback()
    if failures:
        raise click.ClickException("Notification queues need operator review; no messages were sent or reset.")
    click.echo("Notification queues passed the age/retry checks.")
