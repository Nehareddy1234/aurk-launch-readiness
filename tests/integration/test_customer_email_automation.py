from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User, Order, CustomerEmail
from app.services import customer_emails as emails
from app.services.order_status import change_status

@pytest.fixture
def mailer(client,monkeypatch):
    client.application.config.update(CUSTOMER_EMAILS_ENABLED=True,PUBLIC_BASE_URL="https://aurk.in")
    sender=Mock()
    monkeypatch.setattr(emails,"send_email",sender)
    with client.application.app_context():
        user=User(email="emailbuyer@example.com",first_name="Buyer",last_name="Test",password_hash=generate_password_hash("StrongPassword123!"))
        db.session.add(user);db.session.flush()
        order=Order(user_id=user.id,order_number="EMAIL-001",status="Pending",subtotal=999,total=999,
            shipping_name="Buyer Test",shipping_phone="9876543210",shipping_line1="1 Test Street",shipping_city="Mumbai",
            shipping_state="Maharashtra",shipping_postal_code="400001",shipping_country="India")
        db.session.add(order);db.session.commit()
        ids=user.id,order.id
    return ids,sender


def test_signup_queues_welcome_only_for_successful_registration(client,mailer):
    data=dict(email="newbuyer@example.com",first_name="New",last_name="Buyer",password="StrongPassword123!")
    assert client.post("/auth/register",data=data).status_code==302
    client.post("/auth/register",data=data)
    client.post("/auth/register",data={**data,"email":"bad@example.com","password":"short"})
    with client.application.app_context():
        notice=CustomerEmail.query.one()
        assert notice.kind=="welcome" and notice.status=="pending"
        assert notice.recipient=="newbuyer@example.com"
    mailer[1].assert_not_called()


def test_disabled_does_not_queue_or_send(client,mailer):
    client.application.config["CUSTOMER_EMAILS_ENABLED"]=False
    with client.application.app_context():
        emails.queue_customer_email("welcome",db.session.get(User,mailer[0][0]))
        db.session.commit()
        assert CustomerEmail.query.count()==0
        assert emails.dispatch_customer_emails()==0
    mailer[1].assert_not_called()


def test_customer_mail_senders_reply_to_and_no_deliberate_resend(client,mailer):
    ids,sender=mailer
    with client.application.app_context():
        user=db.session.get(User,ids[0]);order=db.session.get(Order,ids[1])
        emails.queue_customer_email("welcome",user)
        emails.queue_customer_email("welcome",user)
        emails.queue_customer_email("order_received",user,order)
        db.session.commit()
        assert CustomerEmail.query.count()==2
        assert emails.dispatch_customer_emails()==2
        assert emails.dispatch_customer_emails()==0
        assert {n.status for n in CustomerEmail.query.all()}=={"submitted"}
    assert sender.call_count==2
    welcome,receipt=sender.call_args_list
    assert welcome.kwargs["from_email"]=="AURK <no-reply@aurk.in>"
    assert welcome.kwargs["reply_to"]=="no-reply@aurk.in"
    assert receipt.kwargs["from_email"]=="AURK <support@aurk.in>"
    assert receipt.kwargs["reply_to"]=="support@aurk.in"


def test_confirmation_idempotency_and_cancellation(client,mailer):
    ids,sender=mailer
    with client.application.app_context(),client.application.test_request_context():
        assert change_status("EMAIL-001","Confirmed",ids[0])
        assert not change_status("EMAIL-001","Confirmed",ids[0])
        notice=CustomerEmail.query.one()
        assert notice.kind=="order_confirmed"
        assert change_status("EMAIL-001","Cancelled",ids[0],"Customer request")
        assert db.session.get(CustomerEmail,notice.id).status=="skipped"
        assert emails.dispatch_customer_emails()==1
        cancelled=CustomerEmail.query.filter_by(kind="order_cancelled").one()
        assert cancelled.status=="submitted"
    sender.assert_called_once()
    assert "cancelled" in sender.call_args.args[1]


def test_failure_backoff_and_limited_retry(client,mailer):
    ids,sender=mailer
    sender.side_effect=RuntimeError("SECRET PROVIDER RESPONSE")
    with client.application.app_context():
        emails.queue_customer_email("welcome",db.session.get(User,ids[0]));db.session.commit()
        assert emails.dispatch_customer_emails()==1
        notice=CustomerEmail.query.one()
        assert notice.status=="failed" and notice.attempts==1
        assert "SECRET" not in notice.last_error
        assert emails.dispatch_customer_emails()==0
        notice.next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.session.commit()
        sender.side_effect=None
        assert emails.dispatch_customer_emails()==1
        assert CustomerEmail.query.one().status=="submitted"


def test_cli_and_inactive_customer_skip(client,mailer):
    ids,sender=mailer
    with client.application.app_context():
        user=db.session.get(User,ids[0]);emails.queue_customer_email("welcome",user);user.is_active=False;db.session.commit()
    result=client.application.test_cli_runner().invoke(args=["send-customer-emails"])
    assert result.exit_code==0,result.output
    sender.assert_not_called()
    with client.application.app_context(): assert CustomerEmail.query.one().status=="skipped"


def test_explicit_sample_test_cli_uses_only_selected_inbox(client,mailer):
    result=client.application.test_cli_runner().invoke(args=["send-email-test","--to","controlled@example.com","--kind","order_received"])
    assert result.exit_code==0,result.output
    assert mailer[1].call_args.args[0]=="controlled@example.com"
    assert mailer[1].call_args.args[1].startswith("[TEST]")
    with client.application.app_context(): assert CustomerEmail.query.count()==0


def test_retry_exhaustion_is_not_resent(client,mailer):
    with client.application.app_context():
        emails.queue_customer_email("welcome",db.session.get(User,mailer[0][0]));db.session.flush()
        notice=CustomerEmail.query.one();notice.status="failed";notice.attempts=5
        notice.next_attempt_at=datetime.now(timezone.utc)-timedelta(days=1);db.session.commit()
        assert emails.dispatch_customer_emails()==0
    mailer[1].assert_not_called()


def test_transport_sets_reply_to_header(client,monkeypatch):
    from unittest.mock import MagicMock
    from app.services import email as transport
    smtp=MagicMock()
    smtp.send_message.return_value={}
    connection=MagicMock();connection.__enter__.return_value=smtp
    constructor=Mock(return_value=connection)
    monkeypatch.setattr(transport.smtplib,"SMTP",constructor)
    client.application.config.update(MAIL_SERVER="smtp-relay.brevo.com",MAIL_PORT=587,MAIL_USERNAME="smtp-login",MAIL_PASSWORD="sample-key",MAIL_USE_TLS=True,MAIL_USE_SSL=False)
    with client.application.app_context():
        transport.send_email("controlled@example.com","Test order","<p>Order</p>","Order",
            from_email="AURK <support@aurk.in>",reply_to="support@aurk.in")
    message=smtp.send_message.call_args.args[0]
    assert str(message["From"])=="AURK <support@aurk.in>"
    assert str(message["Reply-To"])=="support@aurk.in"
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("smtp-login","sample-key")


def test_inline_logo_embedded_in_html_part(client,monkeypatch):
    from unittest.mock import MagicMock
    from app.services import email as transport
    smtp=MagicMock();smtp.send_message.return_value={}
    connection=MagicMock();connection.__enter__.return_value=smtp
    monkeypatch.setattr(transport.smtplib,"SMTP",Mock(return_value=connection))
    client.application.config.update(MAIL_SERVER="smtp-relay.brevo.com",MAIL_PORT=587,MAIL_USE_TLS=True,MAIL_USE_SSL=False)
    logo=(__import__("pathlib").Path(client.application.static_folder)/"images/brand/email-logo.png").read_bytes()
    with client.application.app_context():
        transport.send_email("test@example.com","Logo","<img src=\"cid:aurk-logo\" alt=\"AURK\">","AURK",from_email="support@aurk.in",inline_images={"aurk-logo":logo})
    message=smtp.send_message.call_args.args[0]
    images=[part for part in message.walk() if part.get_content_type()=="image/png"]
    assert len(images)==1
    assert images[0]["Content-ID"]=="<aurk-logo>"
    assert images[0].get_payload(decode=True)==logo
