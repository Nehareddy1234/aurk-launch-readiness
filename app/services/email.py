import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, html_body, text_body=None, *, from_email=None, reply_to=None, inline_images=None, attachments=None):
    config = current_app.config
    sender = from_email or config.get("MAIL_FROM") or config.get("MAIL_USERNAME")
    if not config.get("MAIL_SERVER") or not sender or not to:
        raise RuntimeError("Email sending is not configured.")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body or "Please view this message in an HTML-capable email client.")
    message.add_alternative(html_body, subtype="html")
    for image_id, image_data in (inline_images or {}).items():
        message.get_payload()[-1].add_related(image_data, maintype="image", subtype="png",
            cid=f"<{image_id}>", filename=f"{image_id}.png", disposition="inline")
    for attachment in attachments or ():
        message.add_attachment(attachment["data"], maintype=attachment["maintype"],
            subtype=attachment["subtype"], filename=attachment["filename"])
    context = ssl.create_default_context()
    if config["MAIL_USE_SSL"]:
        connection = smtplib.SMTP_SSL(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10, context=context)
    else:
        connection = smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10)
    with connection as smtp:
        if config["MAIL_USE_TLS"] and not config["MAIL_USE_SSL"]:
            smtp.starttls(context=context)
        if config.get("MAIL_USERNAME"):
            smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
        refused = smtp.send_message(message)
        if refused:
            raise RuntimeError("Email provider refused the recipient.")
