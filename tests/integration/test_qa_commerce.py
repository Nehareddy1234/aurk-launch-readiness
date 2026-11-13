from decimal import Decimal
from pathlib import Path
import json
import time

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import Cart, CartItem, Order, OrderItem, Payment, Inventory, InventoryMovement, CustomerEmail, AuditLog, Product

ADDRESS = dict(recipient_name="QA Buyer", phone="9876543210", line1="1 QA Street", line2="", city="Mumbai", state="Maharashtra", postal_code="400001", country="India")


@pytest.fixture
def purchase(app, client, qa_factory, customer, mocked_smtp):
    product = qa_factory.product()
    variant = qa_factory.variant(product=product, stock=5)
    app.config.update(CUSTOMER_EMAILS_ENABLED=True, PUBLIC_BASE_URL="https://aurk.test")
    client.post("/auth/login", data={"email":customer.email,"password":"QaPassword123!"})
    client.post("/cart/add", data={"variant_id":variant.id,"quantity":2})
    return product, variant, customer


@pytest.mark.parametrize("value", ["0","-1","not-a-number","9999999999999999999","6"])
def test_guest_quantity_rejection(app,client,qa_factory,value):
    variant=qa_factory.variant(stock=5)
    client.post("/cart/add",data={"variant_id":variant.id,"quantity":value,"price":"0.01","total":"0.01"})
    with client.session_transaction() as session:
        assert not session.get("guest_cart")
    with app.app_context(): assert CartItem.query.count()==0


def test_checkout_snapshots_totals_and_double_submission(app,client,purchase):
    product,variant,user=purchase
    response=client.post("/checkout",data={**ADDRESS,"total":"0.01","price":"0.01","quantity":999,"is_paid":"true"})
    assert response.status_code==302
    assert "/checkout/success/" in response.location
    with app.app_context():
        order=Order.query.one(); item=OrderItem.query.one(); payment=Payment.query.one()
        assert order.subtotal==order.total==Decimal("1998.00")
        assert item.product_name_snapshot==product.name
        assert item.sku_snapshot==variant.sku
        assert item.quantity==2 and item.unit_price==Decimal("999.00")
        assert payment.provider=="cash_on_delivery" and payment.status=="pending"
        assert Inventory.query.filter_by(variant_id=variant.id).one().quantity==3
        assert InventoryMovement.query.one().quantity_delta==-2
        assert CartItem.query.count()==0
        assert CustomerEmail.query.filter_by(kind="order_received").count()==1
        name=item.product_name_snapshot;price=item.unit_price
        live=db.session.get(Product,product.id);live.name="Changed after order";live.base_price=2000;db.session.commit()
        assert OrderItem.query.one().product_name_snapshot==name
        assert OrderItem.query.one().unit_price==price
    client.post("/checkout",data=ADDRESS)
    with app.app_context(): assert Order.query.count()==1


def test_checkout_mid_transaction_failure_rolls_back_everything(app,client,purchase,monkeypatch):
    from app.services import customer_emails
    def fail(*args,**kwargs): raise RuntimeError("QA forced failure after order and inventory updates")
    monkeypatch.setattr(customer_emails,"queue_customer_email",fail)
    with pytest.raises(RuntimeError,match="QA forced failure"):
        client.post("/checkout",data=ADDRESS)
    with app.app_context():
        assert Order.query.count()==OrderItem.query.count()==Payment.query.count()==InventoryMovement.query.count()==CustomerEmail.query.count()==0
        assert Inventory.query.filter_by(variant_id=purchase[1].id).one().quantity==5
        assert CartItem.query.one().quantity==2


@pytest.mark.parametrize("change", ["inactive_product","archived","coming_soon","inactive_variant","reduced_stock"])
def test_checkout_revalidates_changes_since_cart(app,client,purchase,change):
    from app.models import ProductVariant
    with app.app_context():
        product=db.session.get(Product,purchase[0].id)
        variant=db.session.get(ProductVariant,purchase[1].id)
        if change=="inactive_product": product.is_active=False
        elif change=="archived": product.is_archived=True
        elif change=="coming_soon": product.product_status="coming_soon"
        elif change=="inactive_variant": variant.is_active=False
        else: variant.inventory.quantity=1
        db.session.commit()
    assert client.post("/checkout",data=ADDRESS).status_code==200
    with app.app_context():
        assert Order.query.count()==0
        assert CartItem.query.count()==1


def test_checkout_uses_updated_catalog_price(app,client,purchase):
    with app.app_context():
        db.session.get(Product,purchase[0].id).base_price=1200;db.session.commit()
    assert client.post("/checkout",data=ADDRESS).status_code==302
    with app.app_context():
        assert Order.query.one().total==Decimal("2400.00")


@pytest.mark.parametrize("overrides", [
    {"recipient_name":""},{"phone":"abc"},{"postal_code":"000000"},{"country":"USA"},
    {"line1":"x"*256},{"city":"x"*101},{"phone":"1"*31},
])
def test_checkout_delivery_validation_preserves_stock(app,client,purchase,overrides):
    client.post("/checkout",data={**ADDRESS,**overrides})
    with app.app_context():
        assert Order.query.count()==0
        assert Inventory.query.filter_by(variant_id=purchase[1].id).one().quantity==5


def test_unicode_address_is_escaped_in_order_pages(app,client,purchase):
    payload='<script>alert("qa")</script>'
    response=client.post("/checkout",data={**ADDRESS,"line1":"தமிழ் "+payload})
    assert response.status_code==302
    with app.app_context(): number=Order.query.one().order_number
    response=client.get(f"/account/orders/{number}")
    assert payload.encode() not in response.data
    assert b"&lt;script&gt;" in response.data


@pytest.mark.parametrize("path", ["/shop?q=","/shop?q=no-match-zzzz","/search?q=%27%20OR%201=1--","/shop?q=%3Cscript%3E","/shop?q=%25_","/shop?q="+"x"*3000,"/shop?sort=unknown","/shop?page=-1"])
def test_catalog_search_fuzz(client,qa_factory,path):
    qa_factory.variant()
    response=client.get(path)
    assert response.status_code==200
    assert b"Traceback" not in response.data
    assert b"<script>" not in response.data


def test_QA_CATALOG_001_archived_products_not_public(app,client,qa_factory):
    product=qa_factory.product(is_archived=True,is_active=True,is_featured=True)
    qa_factory.variant(product=product)
    assert client.get(f"/product/{product.slug}").status_code==404, "QA-CATALOG-001: archived product still has a public detail page"


def test_order_invalid_transition_matrix(app,qa_factory,customer):
    from app.services.order_status import change_status, TRANSITIONS
    with app.app_context(),app.test_request_context():
        for source in ("Pending","Confirmed","Shipped","Delivered","Cancelled"):
            for target in ("Pending","Confirmed","Shipped","Delivered","Cancelled","unknown"):
                if target==source or target in TRANSITIONS.get(source,set()): continue
                order=qa_factory.order(customer=customer,status=source)
                with pytest.raises(ValueError): change_status(order.order_number,target,customer.id,"QA cancellation")
                db.session.rollback()
                assert db.session.get(Order,order.id).status==source
        assert AuditLog.query.count()==0


def test_catalog_query_growth_and_route_timings(app,client,qa_factory):
    records=[]
    with app.app_context():
        engine=db.engine
    def measure(count):
        queries=[]
        def before(*args): queries.append(args[2])
        event.listen(engine,"before_cursor_execute",before)
        start=time.perf_counter()
        try: response=client.get("/shop")
        finally: event.remove(engine,"before_cursor_execute",before)
        assert response.status_code==200
        records.append(dict(products=count,queries=len(queries),seconds=time.perf_counter()-start))
    qa_factory.variant();measure(1)
    for _ in range(9): qa_factory.variant()
    measure(10)
    Path("qa_artifacts").mkdir(exist_ok=True)
    Path("qa_artifacts/catalog-performance.json").write_text(json.dumps(records,indent=2),encoding="utf-8")
    assert records[1]["queries"]<=records[0]["queries"]+5, records
    assert all(r["seconds"]<1 for r in records),records


def test_public_internal_links_assets_and_route_times(app,client,qa_factory):
    from html.parser import HTMLParser
    from urllib.parse import urlsplit
    class Links(HTMLParser):
        def __init__(self): super().__init__();self.urls=set()
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in {"href","src"} and value and value.startswith("/") and not value.startswith("//"):
                    self.urls.add(value)
    timings=[];links=set()
    for path in ("/","/shop","/search","/cart","/auth/login","/auth/register","/worn-by-you","/about","/contact","/shipping","/returns","/refund-policy","/privacy","/terms"):
        start=time.perf_counter();response=client.get(path);duration=time.perf_counter()-start
        assert response.status_code==200,(path,response.status_code)
        parser=Links();parser.feed(response.get_data(as_text=True));links.update(parser.urls)
        timings.append({"path":path,"seconds":duration})
    for link in sorted(links):
        response=client.get(link)
        assert response.status_code in {200,206,302,308},(link,response.status_code)
    Path("qa_artifacts/public-route-timings.json").write_text(json.dumps(timings,indent=2),encoding="utf-8")
    assert all(row["seconds"]<1 for row in timings),timings


def test_mysql_last_unit_concurrency(app,qa_factory,mocked_smtp):
    with app.app_context():
        if db.engine.dialect.name!="mysql":
            pytest.skip("Dedicated MySQL TEST_DATABASE_URL not provided; SQLite cannot prove row locking")
    from concurrent.futures import ThreadPoolExecutor
    import threading
    variant=qa_factory.variant(stock=1)
    buyers=[qa_factory.customer(),qa_factory.customer()]
    clients=[app.test_client(),app.test_client()]
    for client,buyer in zip(clients,buyers):
        client.post("/auth/login",data={"email":buyer.email,"password":"QaPassword123!"})
        client.post("/cart/add",data={"variant_id":variant.id,"quantity":1})
    barrier=threading.Barrier(2)
    def checkout(client):
        barrier.wait(timeout=10)
        return client.post("/checkout",data=ADDRESS).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(checkout,clients))
    with app.app_context():
        assert Order.query.count()==1,results
        assert Inventory.query.filter_by(variant_id=variant.id).one().quantity==0


def test_mysql_overlapping_workers_send_once(app,qa_factory,customer,monkeypatch):
    with app.app_context():
        if db.engine.dialect.name!="mysql":
            pytest.skip("Dedicated MySQL required for concurrent outbox row-lock verification")
        app.config.update(CUSTOMER_EMAILS_ENABLED=True,PUBLIC_BASE_URL="https://aurk.test")
        from app.services import customer_emails
        customer_emails.queue_customer_email("welcome",db.session.get(__import__('app.models',fromlist=['User']).User,customer.id));db.session.commit()
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import Mock
    import threading
    sender=Mock();monkeypatch.setattr(customer_emails,"send_email",sender)
    barrier=threading.Barrier(2)
    def dispatch(_):
        with app.app_context():
            barrier.wait(timeout=10)
            return customer_emails.dispatch_customer_emails()
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(dispatch,range(2)))
    assert sender.call_count==1
