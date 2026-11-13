"""Generate a sample-only order bill; no database reads or email sending."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from app import create_app
from app.services.order_bills import render_order_bill


def sample_order(item_count=3):
    items = [SimpleNamespace(product_name_snapshot="AURK Everyday Oversized Tee" + (" - Limited Edition Cotton Collection" if i % 2 else ""),
        sku_snapshot=f"AURK-QA-{i+1:03}", size_snapshot="M", color_snapshot="Vintage Black", quantity=1,
        unit_price=Decimal("1299.00"), line_total=Decimal("1299.00")) for i in range(item_count)]
    subtotal = sum((item.line_total for item in items), Decimal("0"))
    return SimpleNamespace(order_number="AURK-SAMPLE-001", status="Confirmed", currency="INR",
        created_at=datetime(2026, 10, 28, 8, 30, tzinfo=timezone.utc), items=items, payments=[],
        shipping_name="Sample Customer", shipping_phone="0000000000", shipping_line1="12 Sample Street",
        shipping_line2="Apartment 4B", shipping_city="Mumbai", shipping_state="Maharashtra",
        shipping_postal_code="400001", shipping_country="India", subtotal=subtotal, discount=Decimal("200.00"),
        shipping=Decimal("0"), tax=Decimal("0"), total=subtotal-Decimal("200.00"))


if __name__ == "__main__":
    app = create_app("testing")
    path = Path("output/pdf/aurk-sample-bill.pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        path.write_bytes(render_order_bill(sample_order()))
    print("Sample bill:", path.resolve())
