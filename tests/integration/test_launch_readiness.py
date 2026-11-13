"""Launch regressions: public search data, operational controls and queued mail."""
import json
import re
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET
import pytest
from app.extensions import db
from app.models import Product, ProductImage, ProductInterest, CustomerEmail, Order, Payment, Shipment, CodSettlement, StoreSettings
from app.services.order_status import change_status, record_cod_received
from app.services.launch_notifications import queue_product_launches
from app.services.customer_emails import dispatch_customer_emails


def login_admin(client, admin):
    assert client.post('/admin/login', data={'email':admin.email,'password':'QaPassword123!'}).status_code == 302


def test_public_search_data_and_variant_price(app, client, qa_factory):
    product = qa_factory.product(name='Tee <script>unsafe</script>', seo_title='AURK custom title', seo_description='A precise description')
    variant = qa_factory.variant(product=product, price_override=Decimal('1250'))
    with app.app_context():
        db.session.add(ProductImage(product_id=product.id, storage_key='test.jpg', mime_type='image/jpeg', file_size=100, width=20, height=20, is_primary=True))
        db.session.commit()
    response = client.get(f'/product/{product.slug}?variant={variant.id}', headers={'Host':'attacker.example'})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<title>AURK custom title</title>' in html
    assert 'A precise description' in html
    assert f'href="https://aurk.test/product/{product.slug}"' in html
    assert 'attacker.example' not in html
    assert re.search(fr'value="{variant.id}"[^>]*selected', html)
    assert '1250.00' in html
    scripts = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',html)
    group = json.loads(scripts[0])
    assert group['hasVariant'][0]['offers']['price'] == '1250.00'
    assert group['hasVariant'][0]['offers']['availability'].endswith('InStock')
    assert '<script>unsafe</script>' not in scripts[0]
    assert client.get(f'/product/{product.slug}?variant=99999').status_code == 404
    feed=ET.fromstring(client.get('/merchant-feed.xml').data)
    item=feed.find('channel/item')
    assert item.find('{http://base.google.com/ns/1.0}price').text == '1250.00 INR'
    assert f'variant={variant.id}' in item.find('{http://base.google.com/ns/1.0}link').text


def test_sitemap_excludes_private_hidden_and_archived(app, client, qa_factory):
    public=qa_factory.product()
    hidden=qa_factory.product(is_active=False)
    archived=qa_factory.product(is_archived=True)
    xml=client.get('/sitemaps/products-1.xml').get_data(as_text=True)
    assert public.slug in xml and hidden.slug not in xml and archived.slug not in xml
    pages=client.get('/sitemaps/pages.xml')
    assert pages.status_code==200 and b'/account' not in pages.data and b'/admin' not in pages.data
    index=client.get('/sitemap.xml')
    assert index.status_code==200 and b'https://aurk.test/sitemaps/' in index.data
    assert b'Sitemap: https://aurk.test/sitemap.xml' in client.get('/robots.txt').data
    assert 'noindex' in client.get('/shop?q=tee').headers['X-Robots-Tag']
    app.config['SEARCH_INDEXING_ENABLED']=False
    assert b'Disallow: /' in client.get('/robots.txt').data
    assert client.get('/sitemap.xml').status_code==503
    assert 'noindex' in client.get('/').headers['X-Robots-Tag']


def test_teasers_have_no_offers_or_feed_item(app,client,qa_factory):
    p=qa_factory.product(product_status='coming_soon',hide_price=True,base_price=0)
    qa_factory.variant(product=p)
    html=client.get('/product/'+p.slug).get_data(as_text=True)
    assert '"offers"' not in html
    assert b'<item>' not in client.get('/merchant-feed.xml').data


def test_business_settings_permissions_validation_and_escaping(app,client,qa_factory):
    assert client.post('/admin/launch-settings',data={'legal_name':'forged'}).status_code==302
    admin=qa_factory.admin(); login_admin(client,admin)
    response=client.post('/admin/launch-settings',data={'legal_name':'<script>Example</script>','coverage_mode':'allowlist','cod_pincodes':'400001, 400002'},follow_redirects=True)
    assert response.status_code==200
    assert b'Business and delivery settings saved' in response.data
    html=client.get('/contact').data
    assert b'&lt;script&gt;Example&lt;/script&gt;' in html
    assert b'<script>Example</script>' not in html
    client.post('/admin/launch-settings',data={'coverage_mode':'allowlist','cod_pincodes':'wrong'})
    with app.app_context():
        assert db.session.get(StoreSettings,1).values['cod_pincodes']==['400001','400002']


def test_coverage_and_awb_required_before_dispatch(app,qa_factory):
    order=qa_factory.order();app.config['COD_SERVICEABILITY_REQUIRED']=True
    with app.app_context():
        with pytest.raises(ValueError,match='Verify DTDC'):
            change_status(order.order_number,'Confirmed',order.user_id)
        db.session.rollback()
        db.session.add(Shipment(order_id=order.id,serviceability_confirmed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
        db.session.commit()
        assert change_status(order.order_number,'Confirmed',order.user_id)
        with pytest.raises(ValueError,match='tracking number'):
            change_status(order.order_number,'Shipped',order.user_id)
        db.session.rollback()
        db.session.get(Order,order.id).shipment.awb='DTDC12345';db.session.commit()
        assert change_status(order.order_number,'Shipped',order.user_id)
        assert db.session.get(Order,order.id).shipment.status=='In transit'
        db.session.get(Order,order.id).shipment.status='Returned';db.session.commit()
        with pytest.raises(ValueError,match='Resolve'):
            change_status(order.order_number,'Delivered',order.user_id)


def test_partial_cod_settlements_cannot_double_count(app,client,qa_factory):
    admin=qa_factory.admin();order=qa_factory.order(status='Delivered',total=1000)
    with app.app_context():
        db.session.add(Payment(order_id=order.id,provider='cash_on_delivery',provider_order_id='cod-test',status='pending',amount=1000,currency='INR'))
        db.session.commit()
    login_admin(client,admin)
    path=f'/admin/orders/{order.order_number}/settlements'
    values=dict(reference='REMIT-001',net_amount='400',fees='50',received_on=date.today().isoformat(),received='yes')
    client.post(path,data=values)
    client.post(path,data=values)
    with app.app_context():
        assert CodSettlement.query.count()==1
        assert Payment.query.one().status=='pending'
        with pytest.raises(ValueError,match='Partial settlements'):
            record_cod_received(order.order_number,admin.id,True)
    client.post(path,data={**values,'reference':'OVERPAY','net_amount':'1000'})
    with app.app_context(): assert CodSettlement.query.count()==1
    client.post(path,data={**values,'reference':'REMIT-002','net_amount':'500'})
    with app.app_context():
        assert CodSettlement.query.count()==2 and Payment.query.one().status=='paid'


def test_availability_notices_deduplicate_and_recheck_stock(app,qa_factory,mocked_smtp):
    app.config['CUSTOMER_EMAILS_ENABLED']=True
    user=qa_factory.customer();product=qa_factory.product();variant=qa_factory.variant(product=product)
    with app.app_context():
        interest=ProductInterest(product_id=product.id,customer_id=user.id,identity_key=f'user:{user.id}',product_status='coming_soon')
        db.session.add(interest);db.session.commit()
        assert queue_product_launches()==1
        assert queue_product_launches()==0
        p=db.session.get(Product,product.id);p.product_status='out_of_stock';db.session.commit()
        assert dispatch_customer_emails()==0
        assert CustomerEmail.query.one().attempts==0
        p.product_status='available'
        from datetime import datetime,timezone,timedelta
        CustomerEmail.query.one().next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.session.commit()
        assert dispatch_customer_emails()==1
        assert dispatch_customer_emails()==0
    mocked_smtp.assert_called_once()
    assert 'The drop is live' in mocked_smtp.call_args.args[2]
    assert 'does not reserve' in mocked_smtp.call_args.args[2]


def test_worker_command_and_database_readiness(app,client,mocked_smtp):
    assert client.get('/api/ready').json=={'status':'ready'}
    result=app.test_cli_runner().invoke(args=['process-notifications'])
    assert result.exit_code==0,result.output
    assert 'Queued 0' in result.output


def test_mysql_uses_utc_and_launch_workers_deduplicate(app,qa_factory):
    with app.app_context():
        if db.engine.dialect.name != 'mysql': pytest.skip('Requires MySQL row locking')
        assert db.session.execute(db.text('SELECT @@session.time_zone')).scalar() == '+00:00'
    app.config['CUSTOMER_EMAILS_ENABLED']=True
    user=qa_factory.customer();product=qa_factory.product();qa_factory.variant(product=product)
    with app.app_context():
        db.session.add(ProductInterest(product_id=product.id,customer_id=user.id,identity_key=f'user:{user.id}',product_status='coming_soon'))
        db.session.commit()
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    def worker():
        with app.app_context():
            barrier.wait(timeout=5)
            return queue_product_launches()
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts=list(pool.map(lambda _:worker(),range(2)))
    assert sum(counts)==1
    with app.app_context(): assert CustomerEmail.query.filter_by(kind='product_available').count()==1
