from io import BytesIO
from decimal import Decimal
from unittest.mock import Mock
import pytest
from pypdf import PdfReader
from app.extensions import db
from app.models import OrderItem, AuditLog, Order
from app.services.order_bills import render_order_bill, payment_label
from scripts.preview_order_bill import sample_order


def login(client, user, admin=False):
    client.post('/admin/logout' if admin else '/auth/logout')
    response = client.post('/admin/login' if admin else '/auth/login', data={
        'email':user.email, 'password':'QaPassword123!'})
    assert response.status_code == 302
    if admin:
        assert response.location == '/admin/dashboard'


@pytest.fixture
def purchase(app, qa_factory):
    customer = qa_factory.customer()
    product = qa_factory.product(name='Renamed live product')
    variant = qa_factory.variant(product=product)
    order = qa_factory.order(customer=customer)
    with app.app_context():
        db.session.add(OrderItem(order_id=order.id, variant_id=variant.id, product_name_snapshot='Saved purchase name',
            sku_snapshot='SAVED-SKU', size_snapshot='M', color_snapshot='Black', unit_price=999,
            quantity=1, line_total=999))
        db.session.commit()
    return customer, order


def test_customer_bill_ownership_and_snapshot(app, client, purchase, qa_factory):
    customer, order = purchase
    url = f'/account/orders/{order.order_number}/bill.pdf'
    assert client.get(url).status_code == 302
    login(client, qa_factory.customer())
    assert client.get(url).status_code == 404
    client.post('/auth/logout')
    login(client, customer)
    response = client.get(url)
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert 'attachment;' in response.headers['Content-Disposition']
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.data)).pages)
    assert 'Saved purchase name' in text and 'Renamed live product' not in text
    assert 'INR 999.00' in text
    assert 'Payment pending' in text


def test_admin_bill_permissions_and_email_attachment(app, client, purchase, qa_factory, monkeypatch):
    customer, order = purchase
    pdf_url = f'/admin/orders/{order.order_number}/bill.pdf'
    send_url = f'/admin/orders/{order.order_number}/email-bill'
    login(client, qa_factory.admin(permissions=('products.view',)), admin=True)
    assert client.get(pdf_url).status_code == 403
    assert client.post(send_url).status_code == 403
    login(client, qa_factory.admin(permissions=('orders.manage',)), admin=True)
    sender = Mock()
    monkeypatch.setattr('app.services.email.send_email', sender)
    assert client.get(pdf_url).status_code == 200
    assert client.post(send_url).status_code == 302
    args, kwargs = sender.call_args
    assert args[0] == customer.email
    assert kwargs['attachments'][0]['data'].startswith(b'%PDF-')
    assert kwargs['attachments'][0]['subtype'] == 'pdf'
    with app.app_context():
        assert db.session.scalar(db.select(AuditLog).where(AuditLog.action == 'order.bill_emailed'))
        assert db.session.get(Order, order.id).status == 'Pending'
    app.config['WTF_CSRF_ENABLED'] = True
    assert client.post(send_url).status_code == 400
    assert sender.call_count == 1


def test_failed_email_does_not_change_order(app, client, purchase, qa_factory, monkeypatch):
    _, order = purchase
    login(client, qa_factory.admin(permissions=('orders.manage',)), admin=True)
    monkeypatch.setattr('app.services.email.send_email', Mock(side_effect=RuntimeError('simulated SMTP failure')))
    response = client.post(f'/admin/orders/{order.order_number}/email-bill', follow_redirects=True)
    assert b'could not be confirmed as sent' in response.data
    with app.app_context():
        assert db.session.get(Order, order.id).status == 'Pending'
        assert not db.session.scalar(db.select(AuditLog).where(AuditLog.action == 'order.bill_emailed'))


def test_multipage_bill_and_payment_status(app):
    order = sample_order(item_count=40)
    with app.app_context():
        reader = PdfReader(BytesIO(render_order_bill(order)))
    assert len(reader.pages) > 1
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert 'AURK-QA-040' in text and f'{order.total:,.2f}' in text
    order.status = 'Delivered'
    assert 'pending' in payment_label(order)
    from types import SimpleNamespace
    order.payments = [SimpleNamespace(amount=order.total, currency='INR', status='paid')]
    assert payment_label(order) == 'Payment received'
    order.status = 'Cancelled'
    assert 'no payment due' in payment_label(order)


def test_smtp_message_contains_pdf_attachment(app, monkeypatch):
    from unittest.mock import MagicMock
    from app.services.email import send_email
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.return_value = {}
    monkeypatch.setattr('app.services.email.smtplib.SMTP', Mock(return_value=smtp))
    app.config.update(MAIL_SERVER='mock.local', MAIL_PORT=587, MAIL_USE_TLS=False,
                      MAIL_USE_SSL=False, MAIL_USERNAME='', MAIL_FROM='support@example.com')
    with app.app_context():
        data = render_order_bill(sample_order())
        send_email('qa@example.com', 'QA bill', '<p>Attached</p>', 'Attached',
                   attachments=[dict(data=data, maintype='application', subtype='pdf', filename='bill.pdf')])
    message = smtp.send_message.call_args.args[0]
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == 'application/pdf'
    assert attachments[0].get_payload(decode=True) == data
