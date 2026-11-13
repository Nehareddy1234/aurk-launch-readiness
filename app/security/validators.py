import re
from decimal import Decimal, InvalidOperation
from email_validator import EmailNotValidError, validate_email
from werkzeug.utils import secure_filename


def validate_email_address(value):
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


def validate_positive_quantity(value):
    if not isinstance(value, int) or value < 1:
        raise ValueError("Quantity must be a positive integer.")
    return value


def validate_money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99") or amount.as_tuple().exponent < -2:
            raise ValueError("Invalid monetary amount.")
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid monetary amount.") from None



def safe_text(value, max_length=5000):
    value = (value or "").strip()
    if len(value) > max_length:
        raise ValueError("Input is too long.")
    return value


def safe_slug(value):
    value = secure_filename(value or "").lower().replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value).strip("-")
    if not value:
        raise ValueError("Invalid slug.")
    return value
