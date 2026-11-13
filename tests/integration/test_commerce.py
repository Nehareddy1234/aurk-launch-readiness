from decimal import Decimal

from app.extensions import db
from app.models import Cart, CartItem, Category, Color, Inventory, Order, Product, ProductVariant, Size, User
from werkzeug.security import generate_password_hash


def _customer():
    customer = User(
        email="buyer@example.com",
        first_name="Buyer",
        last_name="Test",
        password_hash=generate_password_hash("StrongPassword123!"),
    )
    db.session.add(customer)
    db.session.flush()
    return customer


def _variant(product, size, color, sku, quantity):
    variant = ProductVariant(product_id=product.id, size_id=size.id, color_id=color.id, sku=sku)
    db.session.add(variant)
    db.session.flush()
    db.session.add(Inventory(variant_id=variant.id, quantity=quantity, reserved_quantity=0))
    return variant


def _sign_in(client, user_id):
    user = db.session.get(User, user_id)
    response = client.post("/auth/login", data={
        "email": user.email,
        "password": "StrongPassword123!",
    })
    assert response.status_code == 302
    assert response.headers["Location"] == "/account/"


def test_cart_adds_the_submitted_variant_not_a_matching_variant(client):
    with client.application.app_context():
        customer = _customer()
        category = Category(name="Tees", slug="tees")
        size = Size(name="M")
        color = Color(name="Black")
        db.session.add_all([category, size, color])
        db.session.flush()
        first = Product(name="First", slug="first", base_price=Decimal("100"), category_id=category.id)
        second = Product(name="Second", slug="second", base_price=Decimal("200"), category_id=category.id)
        db.session.add_all([first, second])
        db.session.flush()
        _variant(first, size, color, "FIRST-M-BLK", 3)
        second_variant = _variant(second, size, color, "SECOND-M-BLK", 3)
        customer_id = customer.id
        second_variant_id = second_variant.id
        db.session.commit()
        _sign_in(client, customer_id)

    response = client.post("/cart/add", data={"variant_id": second_variant_id, "quantity": 1})
    assert response.status_code == 302
    with client.application.app_context():
        cart = Cart.query.filter_by(user_id=customer_id).one()
        assert cart.items[0].variant_id == second_variant_id


def test_checkout_creates_an_order_and_reduces_stock(client):
    with client.application.app_context():
        customer = _customer()
        category = Category(name="Hoodies", slug="hoodies")
        size = Size(name="L")
        color = Color(name="Blue")
        db.session.add_all([category, size, color])
        db.session.flush()
        product = Product(name="Hoodie", slug="hoodie", base_price=Decimal("799"), category_id=category.id)
        db.session.add(product)
        db.session.flush()
        variant = _variant(product, size, color, "HOODIE-L-BLU", 4)
        cart = Cart(user_id=customer.id)
        db.session.add(cart)
        db.session.flush()
        db.session.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=2))
        db.session.flush()
        customer_id = customer.id
        inventory_id = variant.inventory.id
        db.session.commit()
        _sign_in(client, customer_id)

    response = client.post("/checkout", data={
        "recipient_name": "Buyer Test",
        "phone": "9876543210",
        "line1": "1 Test Street",
        "line2": "",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "country": "India",
    })
    assert response.status_code == 302
    with client.application.app_context():
        order = Order.query.filter_by(user_id=customer_id).one()
        assert order.total == Decimal("1598.00")
        assert db.session.get(Inventory, inventory_id).quantity == 2
        assert Cart.query.filter_by(user_id=customer_id).one().items == []
