"""Date-filtered operational reports, with spreadsheet-safe CSV exports."""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from flask import abort, request, Response
from flask_login import current_user
from sqlalchemy import func
from app.extensions import db
from app.models import Order, Payment, Product, ProductVariant, Inventory, OrderItem
from app.security.decorators import permission_required

IST = timezone(timedelta(hours=5, minutes=30))

def period():
    today = datetime.now(IST).date()
    try:
        end = date.fromisoformat(request.args.get("end", today.isoformat()))
        start = date.fromisoformat(request.args.get("start", (end - timedelta(days=29)).isoformat()))
        if start > end or (end - start).days > 365:
            raise ValueError
        lower = datetime.combine(start, time.min, IST).astimezone(timezone.utc).replace(tzinfo=None)
        upper = datetime.combine(end + timedelta(days=1), time.min, IST).astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        abort(400, description="Choose a valid date range of up to 366 days.")
    return dict(start=start, end=end, lower=lower, upper=upper)

def bounds(column, dates):
    return (column >= dates["lower"], column < dates["upper"])

def overview(dates):
    orders = bounds(Order.created_at, dates)
    statuses = db.session.execute(db.select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(*orders).group_by(Order.status)).all()
    total = sum(row[1] for row in statuses)
    booked = sum((row[2] for row in statuses if row[0] != "Cancelled"), Decimal("0"))
    valid = sum(row[1] for row in statuses if row[0] != "Cancelled")
    received = db.session.scalar(db.select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid", *bounds(Payment.paid_at, dates)))
    best = db.session.execute(db.select(OrderItem.product_name_snapshot, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total)).join(Order).where(*orders, Order.status != "Cancelled").group_by(OrderItem.product_name_snapshot).order_by(func.sum(OrderItem.quantity).desc(), OrderItem.product_name_snapshot).limit(5)).all()
    return dict(orders=total, booked=booked, received=received, average=booked / valid if valid else Decimal("0"), statuses=statuses, best=best)

def local_stamp(value):
    if not value:
        return ""
    return value.replace(tzinfo=timezone.utc).astimezone(IST).isoformat()

def safe_cell(value):
    text = "" if value is None else str(value)
    if isinstance(value, str) and text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text

def register_reports(bp):
    @bp.context_processor
    def back_navigation():
        target, label = "main.home", "Back to store"
        if current_user.is_authenticated:
            for section, permission in [("products", "products.view"), ("categories", "products.update"), ("orders", "orders.manage"), ("customers", "customers.manage"), ("coupons", "coupons.manage"), ("inventory", "inventory.manage")]:
                if request.path.startswith(f"/admin/{section}/") and current_user.has_permission(permission):
                    target, label = f"admin.{section}", f"Back to {section}"
                    break
            else:
                if request.endpoint != "admin.dashboard" and current_user.has_permission("dashboard.view"):
                    target, label = "admin.dashboard", "Back to dashboard"
        return dict(admin_back_endpoint=target, admin_back_label=label)

    @bp.get("/reports/<kind>.csv")
    @permission_required("analytics.view")
    def export_report(kind):
        dates = period()
        if kind == "summary":
            info = overview(dates)
            headers = ["Metric", "Value", "Currency", "Start date (IST)", "End date (IST)"]
            rows = [[label, round(info[key], 2), currency, dates["start"], dates["end"]] for label, key, currency in [("Orders placed", "orders", ""), ("Order value excluding cancelled", "booked", "INR"), ("Cash recorded as received", "received", "INR"), ("Average non-cancelled order value", "average", "INR")]]
        elif kind == "orders":
            if not current_user.has_permission("orders.manage"):
                abort(403)
            headers = ["Order", "Placed at (IST)", "Status", "Subtotal", "Discount", "Shipping", "Tax", "Total", "Currency"]
            records = db.session.scalars(db.select(Order).where(*bounds(Order.created_at, dates)).order_by(Order.created_at, Order.id)).all()
            rows = ([o.order_number, local_stamp(o.created_at), o.status_label, o.subtotal, o.discount, o.shipping, o.tax, o.total, o.currency] for o in records)
        elif kind == "receipts":
            if not current_user.has_permission("orders.manage"):
                abort(403)
            headers = ["Order", "Received at (IST)", "Provider", "Amount", "Currency"]
            records = db.session.execute(db.select(Payment, Order.order_number).join(Order).where(Payment.status == "paid", *bounds(Payment.paid_at, dates)).order_by(Payment.paid_at, Payment.id)).all()
            rows = ([number, local_stamp(p.paid_at), p.provider, p.amount, p.currency] for p, number in records)
        elif kind == "inventory":
            if not current_user.has_permission("inventory.manage"):
                abort(403)
            headers = ["Product", "SKU", "Size", "Colour", "Quantity", "Reserved", "Available", "Low stock threshold", "Low stock", "Snapshot at (IST)"]
            records = db.session.scalars(db.select(ProductVariant).join(Product).where(Product.is_archived.is_(False)).order_by(Product.name, ProductVariant.id)).all()
            stamp = datetime.now(IST).isoformat()
            rows = ([v.product.name, v.sku, v.size.name, v.color.name, v.inventory.quantity if v.inventory else 0, v.inventory.reserved_quantity if v.inventory else 0, max(0, v.inventory.quantity-v.inventory.reserved_quantity) if v.inventory else 0, v.inventory.low_stock_threshold if v.inventory else 5, "Yes" if not v.inventory or v.inventory.quantity-v.inventory.reserved_quantity <= v.inventory.low_stock_threshold else "No", stamp] for v in records)
        else:
            abort(404)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows([safe_cell(cell) for cell in row] for row in rows)
        filename = f"ar-drips-{kind}-{dates['start']}-{dates['end']}.csv" if kind != "inventory" else f"ar-drips-inventory-{datetime.now(IST).date()}.csv"
        return Response("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
