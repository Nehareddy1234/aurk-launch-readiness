"""Queue one availability notice per registered customer's product request."""
from flask import current_app
from app.extensions import db
from app.models import Product, ProductVariant, ProductInterest, CustomerEmail, Inventory, User


def queue_product_launches(limit=500):
    if not current_app.config["CUSTOMER_EMAILS_ENABLED"]:
        return 0
    ready = db.select(Product.id).join(ProductVariant).join(Inventory).where(
        Product.is_active.is_(True), Product.is_archived.is_(False), Product.product_status=="available",
        Product.hide_price.is_(False), ProductVariant.is_active.is_(True), Inventory.quantity>Inventory.reserved_quantity,
        db.func.coalesce(ProductVariant.price_override, Product.sale_price, Product.base_price)>0).distinct()
    queued = 0
    # Lock each product while creating events; concurrent workers serialize here.
    product_ids = list(db.session.scalars(ready))
    # End the discovery snapshot before locking, so concurrent workers see committed events.
    db.session.commit()
    for product_id in product_ids:
        product = db.session.scalar(db.select(Product).where(Product.id==product_id).with_for_update().execution_options(populate_existing=True))
        if not product or not product.is_purchasable or product.hide_price:
            db.session.commit()
            continue
        interests = db.session.scalars(db.select(ProductInterest).join(User,User.id==ProductInterest.customer_id).where(
            ProductInterest.product_id==product_id, User.is_active.is_(True),
            ~db.exists().where(CustomerEmail.interest_id==ProductInterest.id, CustomerEmail.kind=="product_available"))
            .order_by(ProductInterest.id).limit(limit-queued)).all()
        for interest in interests:
            customer = db.session.get(User, interest.customer_id)
            db.session.add(CustomerEmail(event_key=f"product_available:{interest.id}", kind="product_available", user_id=customer.id, interest_id=interest.id, recipient=customer.email))
            queued += 1
        db.session.commit()
        if queued >= limit:
            break
    return queued


import click
from flask.cli import with_appcontext


@click.command("process-notifications")
@click.option("--limit", default=50, type=click.IntRange(1, 500))
@with_appcontext
def process_notifications_command(limit):
    """Process due customer and owner notifications from a single scheduled worker."""
    from app.services.customer_emails import dispatch_customer_emails
    from app.services.order_notifications import dispatch_order_alerts
    from app.services.product_interests import dispatch_interest_alerts
    queued = queue_product_launches(limit)
    customer = dispatch_customer_emails(limit)
    with current_app.test_request_context():
        owner = dispatch_order_alerts(batch_size=limit)
    interests = dispatch_interest_alerts(limit)
    click.echo(f"Queued {queued} availability notices; processed {customer} customer emails, {owner} order alerts and {interests} interest alerts.")
