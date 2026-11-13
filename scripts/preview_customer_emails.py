"""Create private, sample-only HTML/text previews without database access or sending."""
import argparse
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from app import create_app
from app.services.customer_email_templates import render_customer_order_email, render_customer_welcome_email, render_customer_interest_email


def sample_order():
    return SimpleNamespace(order_number="AURK-PREVIEW-001", currency="INR", created_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        shipping_name="Sample Customer", shipping_phone="0000000000", shipping_line1="Sample address - preview only",
        shipping_line2="", shipping_city="Mumbai", shipping_state="Maharashtra", shipping_postal_code="400001", shipping_country="India",
        subtotal=Decimal("2598"), discount=Decimal("200"), shipping=Decimal("0"), tax=Decimal("0"), total=Decimal("2398"),
        items=[SimpleNamespace(product_name_snapshot="AURK Everyday Tee",size_snapshot="M",color_snapshot="Vintage Black",quantity=1,line_total=Decimal("1299")),
               SimpleNamespace(product_name_snapshot="AURK Everyday Tee",size_snapshot="L",color_snapshot="Off White",quantity=1,line_total=Decimal("1299"))])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default="instance/email-previews")
    args=parser.parse_args()
    target=Path(args.output)
    target.mkdir(parents=True,exist_ok=True)
    app=create_app("testing")
    shutil.copyfile(Path(app.static_folder)/"images/brand/email-logo.png", target/"aurk-logo.png")
    with app.app_context():
        for kind in ("welcome", "order_received", "order_confirmed", "notify_interest"):
            email = (render_customer_welcome_email(SimpleNamespace(first_name="Sample"), public_base_url="https://aurk.in")
                     if kind == "welcome" else (render_customer_interest_email(SimpleNamespace(first_name="Sample"),
                         SimpleNamespace(name="AURK Upcoming Drop", slug="sample-drop"), public_base_url="https://aurk.in")
                         if kind == "notify_interest" else render_customer_order_email(sample_order(),kind,public_base_url="https://aurk.in")))
            (target/(kind+".html")).write_text(email.html.replace("cid:aurk-logo", "aurk-logo.png"),encoding="utf-8")
            (target/(kind+".txt")).write_text(email.text,encoding="utf-8")
            (target/(kind+"-headers.txt")).write_text(f"Subject: {email.subject}\nFrom: {email.from_name} <{email.from_email}>\nReply-To: {email.reply_to}\n",encoding="utf-8")
    (target/"index.html").write_text('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AURK email previews</title></head><body style="margin:0;padding:48px 24px;background:#000000;color:#ffffff;font-family:Arial,sans-serif"><main style="max-width:760px;margin:auto"><p style="letter-spacing:5px">AURK / EMAIL STUDIO</p><h1>AURK emails, ready to review.</h1><p>Sample data only. No email has been sent and no order has been placed.</p><p>Order email sender and reply address: <strong>support@aurk.in</strong></p><ul style="line-height:2.4"><li><a href="welcome.html">Welcome - HTML preview</a> | <a href="welcome.txt">Plain text</a></li><li><a href="order_received.html">Order received - HTML preview</a> | <a href="order_received.txt">Plain text</a></li><li><a href="order_confirmed.html">Order confirmed - HTML preview</a> | <a href="order_confirmed.txt">Plain text</a></li></ul><p>Welcome uses no-reply@aurk.in, with support@aurk.in listed for help. Open a preview in a browser and resize it to review the mobile layout. The order link points to a sample order that does not exist. Actual rendering in Gmail, Outlook and mobile mail apps will be checked during delivery testing.</p></main></body></html>''',encoding="utf-8")
    print("Created sample previews:",target.resolve()/"index.html")
    index = target / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("</ul>", '<li><a href="notify_interest.html">Notify me - HTML preview</a> | <a href="notify_interest.txt">Plain text</a></li></ul>'), encoding="utf-8")

if __name__=="__main__":
    main()
