from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.extensions import db
from app.models import User, CustomerEmail, ProductInterest
from app.services import customer_emails


def test_new_email_is_due_even_with_second_precision_mysql(app, customer, monkeypatch):
    from freezegun import freeze_time
    app.config.update(CUSTOMER_EMAILS_ENABLED=True, PUBLIC_BASE_URL='https://aurk.test')
    sender = Mock()
    monkeypatch.setattr(customer_emails, 'send_email', sender)
    with freeze_time('2026-10-28 10:00:00.900000'), app.app_context():
        customer_emails.queue_customer_email('welcome', db.session.get(User, customer.id))
        db.session.commit()
        notice = CustomerEmail.query.one()
        due = notice.next_attempt_at.replace(tzinfo=timezone.utc)
        assert due <= datetime.now(timezone.utc)
        assert customer_emails.dispatch_customer_emails() == 1
    sender.assert_called_once()


def test_QA_EMAIL_001_provider_acceptance_then_timeout_can_duplicate(app,customer,monkeypatch):
    """Fake SMTP accepts the message but loses its acknowledgement.

    No real SMTP is contacted. An ambiguous send is retained for operator
    review and must not be retried automatically after a lost acknowledgement.
    """
    app.config.update(CUSTOMER_EMAILS_ENABLED=True,PUBLIC_BASE_URL="https://aurk.test")
    accepted=[]
    def accepted_then_timeout(*args,**kwargs):
        accepted.append(args[0])
        raise TimeoutError("QA lost acknowledgement after provider accepted email")
    monkeypatch.setattr(customer_emails,"send_email",accepted_then_timeout)
    with app.app_context():
        customer_emails.queue_customer_email("welcome",db.session.get(User,customer.id));db.session.commit()
        assert customer_emails.dispatch_customer_emails()==1
        notice=CustomerEmail.query.one()
        assert notice.status=="failed" and notice.attempts==1
        notice.next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.session.commit()
        customer_emails.dispatch_customer_emails()
    assert len(accepted)==1, "QA-EMAIL-001: provider acceptance followed by SMTP timeout causes a duplicate on retry"


def test_deleted_interest_acknowledgement_is_skipped(app,customer,qa_factory,monkeypatch):
    product=qa_factory.product(product_status="coming_soon")
    app.config.update(CUSTOMER_EMAILS_ENABLED=True,PUBLIC_BASE_URL="https://aurk.test")
    sender=Mock();monkeypatch.setattr(customer_emails,"send_email",sender)
    with app.app_context():
        interest=ProductInterest(product_id=product.id,customer_id=customer.id,identity_key=f"user:{customer.id}",product_status="coming_soon")
        db.session.add(interest);db.session.flush()
        customer_emails.queue_interest_acknowledgement(interest,db.session.get(User,customer.id));db.session.commit()
        # Explicitly emulate MySQL ON DELETE SET NULL on SQLite.
        notice=CustomerEmail.query.one();notice.interest_id=None;db.session.delete(interest);db.session.commit()
        customer_emails.dispatch_customer_emails()
        assert notice.status=="skipped"
    sender.assert_not_called()
