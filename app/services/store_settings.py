import re
from flask import current_app, g, has_request_context
from app.extensions import db
from app.models import StoreSettings

BUSINESS_FIELDS = ("legal_name", "address", "return_address", "grievance_name", "grievance_email", "gstin")


def get_settings():
    if has_request_context() and hasattr(g, "store_settings"):
        return g.store_settings
    values = {key: current_app.config.get("BUSINESS_"+key.upper(), "") for key in BUSINESS_FIELDS}
    values.update(cod_pincodes=[], coverage_mode="manual")
    record = db.session.get(StoreSettings, 1)
    if record:
        values.update(record.values)
    if has_request_context():
        g.store_settings = values
    return values


def validate_settings(form):
    values = {}
    for key in BUSINESS_FIELDS:
        value = form.get(key, "").strip()
        if len(value) > (1500 if "address" in key else 200):
            raise ValueError("Business information is too long.")
        values[key] = value
    if values["grievance_email"]:
        from app.security.validators import validate_email_address
        values["grievance_email"] = validate_email_address(values["grievance_email"])
    if values["gstin"] and not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]", values["gstin"]):
        raise ValueError("Enter a valid GSTIN, or leave it blank until confirmed.")
    pins = sorted(set(re.split(r"[\s,;]+", form.get("cod_pincodes", "").strip())) - {""})
    if len(pins) > 30000 or any(not re.fullmatch(r"[1-9][0-9]{5}", p) for p in pins):
        raise ValueError("Enter six-digit COD PIN codes separated by commas or newlines.")
    mode = form.get("coverage_mode", "manual")
    if mode not in {"manual", "allowlist"} or (mode == "allowlist" and not pins):
        raise ValueError("An approved PIN-code list is required before enabling coverage restrictions.")
    values.update(cod_pincodes=pins, coverage_mode=mode)
    return values


def check_cod_coverage(pin):
    settings = get_settings()
    if settings["coverage_mode"] == "allowlist" and pin not in settings["cod_pincodes"]:
        raise ValueError("Cash on delivery is not currently available for this PIN code. Contact support for help.")
