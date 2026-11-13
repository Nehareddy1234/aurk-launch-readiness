"""Shared delivery validation for checkout and the customer account."""
import re
from app.security.validators import safe_text


def validate_shipping_details(values):
    """Validate the minimum address data needed to fulfil an order."""
    fields = {
        "recipient_name": safe_text(values.get("recipient_name"), 200),
        "phone": safe_text(values.get("phone"), 30),
        "line1": safe_text(values.get("line1"), 255),
        "line2": safe_text(values.get("line2"), 255),
        "city": safe_text(values.get("city"), 100),
        "state": safe_text(values.get("state"), 100),
        "postal_code": safe_text(values.get("postal_code"), 20),
        "country": safe_text(values.get("country"), 100) or "India",
    }
    for name in ("recipient_name", "phone", "line1", "city", "state", "postal_code"):
        if not fields[name]:
            raise ValueError("Please complete all required delivery details.")
    if fields["country"].lower() != "india":
        raise ValueError("Delivery is currently available only within India.")
    fields["country"] = "India"
    phone = re.sub(r"[\s()+-]", "", fields["phone"])
    if not phone.isdigit() or not 10 <= len(phone) <= 15:
        raise ValueError("Enter a valid phone number with 10 to 15 digits.")
    if fields["country"].lower() == "india" and not re.fullmatch(r"[1-9][0-9]{5}", fields["postal_code"]):
        raise ValueError("Enter a valid 6-digit Indian PIN code.")
    return fields

