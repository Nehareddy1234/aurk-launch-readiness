"""On-demand order bills built only from saved order/item/payment snapshots."""
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from flask import current_app, make_response, render_template
from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether


def bill_filename(order):
    number = re.sub(r"[^A-Za-z0-9_-]", "-", order.order_number)[:60]
    return f"AURK-bill-{number}.pdf"


def payment_label(order):
    paid = sum((p.amount for p in order.payments if p.status == "paid" and p.currency == order.currency), Decimal("0"))
    if order.status == "Cancelled":
        return "Order cancelled - no payment due"
    if paid >= order.total:
        return "Payment received" if order.total > 0 else "No payment due"
    if paid:
        return f"Payment recorded: {order.currency} {paid:,.2f}; balance pending"
    return "Payment pending - cash on delivery"


def render_order_bill(order):
    font_folder = Path(reportlab_file).parent / "fonts"
    if "AurkBill" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("AurkBill", str(font_folder / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("AurkBillBold", str(font_folder / "VeraBd.ttf")))
        pdfmetrics.registerFontFamily("AurkBill", normal="AurkBill", bold="AurkBillBold")
    body = ParagraphStyle("BillBody", fontName="AurkBill", fontSize=9, leading=14, wordWrap="CJK")
    small = ParagraphStyle("BillSmall", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#596168"))
    right = ParagraphStyle("BillRight", parent=body, alignment=TA_RIGHT)
    heading = ParagraphStyle("BillHeading", parent=body, fontName="AurkBillBold", fontSize=22, leading=28)
    white = ParagraphStyle("BillWhite", parent=body, textColor=colors.white, fontName="AurkBillBold")

    def p(value, style=body):
        return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), style)

    def money(value):
        return f"{order.currency} {Decimal(value or 0):,.2f}"

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                           topMargin=18*mm, bottomMargin=20*mm,
                           title=f"AURK order bill {order.order_number}", author="AURK")
    generated = datetime.now(timezone.utc)
    story = [p("AURK", heading), p("ORDER BILL", small), Spacer(1, 7*mm)]
    from app.services.store_settings import get_settings
    business = get_settings()
    for field in ("legal_name", "address"):
        if business.get(field):
            story.append(p(business[field], small))
    if business.get("gstin"):
        story.append(p("GSTIN: " + business["gstin"], small))
    story.append(p("Order summary; this document is not a GST tax invoice.", small))
    meta = Table([[p(f"Order: {order.order_number}"), p(f"Order date: {order.created_at.strftime('%d %b %Y')}", right)],
                  [p(f"Status: {order.status}"), p(f"Generated: {generated.strftime('%d %b %Y, %H:%M UTC')}", right)]],
                 colWidths=[87*mm, 87*mm])
    meta.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0),
                             ("RIGHTPADDING", (0,0), (-1,-1), 0)]))
    story += [meta, Spacer(1, 6*mm), p("DELIVERY DETAILS", small)]
    address = [order.shipping_name, order.shipping_line1, order.shipping_line2,
               f"{order.shipping_city}, {order.shipping_state} {order.shipping_postal_code}",
               order.shipping_country, f"Phone: {order.shipping_phone}"]
    story += [p("\n".join(value for value in address if value)), Spacer(1, 7*mm)]
    rows = [[p("Item / variant", white), p("Qty", white), p("Unit price", white), p("Line total", white)]]
    for item in order.items:
        description = "\n".join([item.product_name_snapshot,
                                 f"Size: {item.size_snapshot} | Colour: {item.color_snapshot}",
                                 f"SKU: {item.sku_snapshot}"])
        rows.append([p(description), p(item.quantity, right), p(money(item.unit_price), right), p(money(item.line_total), right)])
    table = Table(rows, colWidths=[87*mm, 13*mm, 37*mm, 37*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17191b")),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("TOPPADDING", (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 9), ("LINEBELOW", (0,1), (-1,-1), .4, colors.HexColor("#dce0e2")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f6f7")])]))
    story += [table, Spacer(1, 6*mm)]
    totals = Table([[p(label), p(value, right)] for label, value in (
        ("Subtotal", money(order.subtotal)), ("Discount", "- " + money(order.discount)),
        ("Delivery", money(order.shipping)), ("Tax (saved order amount)", money(order.tax)),
        ("ORDER TOTAL", money(order.total)))], colWidths=[117*mm, 57*mm])
    totals.setStyle(TableStyle([("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#e9edef")),
                              ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story += [KeepTogether([totals, Spacer(1, 5*mm), p(payment_label(order)),
                p("Line totals and discounts use the saved order amounts. Payment status reflects records at generation time.", small),
                Spacer(1, 4*mm), p(f"Questions? {current_app.config['CUSTOMER_SUPPORT_EMAIL']}", small)])]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("AurkBill", 8)
        canvas.setFillColor(colors.HexColor("#596168"))
        canvas.drawString(18*mm, 12*mm, "AURK / Order bill")
        canvas.drawRightString(A4[0]-18*mm, 12*mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def bill_download_response(order):
    response = make_response(render_order_bill(order))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{bill_filename(order)}"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def email_order_bill(order, recipient):
    from email.utils import formataddr
    from app.services.email import send_email
    support = current_app.config["CUSTOMER_SUPPORT_EMAIL"]
    text = (f"Your AURK order bill for {order.order_number} is attached as a PDF.\n"
            f"{payment_label(order)}.\nQuestions? {support}")
    send_email(recipient, f"Your AURK bill - {order.order_number}",
               render_template("emails/order_bill.html", order=order, payment_label=payment_label(order), support=support), text,
               from_email=formataddr(("AURK", support)), reply_to=support,
               attachments=[dict(data=render_order_bill(order), maintype="application", subtype="pdf", filename=bill_filename(order))])
