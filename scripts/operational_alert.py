"""Send a bounded service-failure alert without importing the application/database."""
import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
import time

from dotenv import dotenv_values

ALLOWED_UNITS = {"aurk.service", "aurk-health.service", "aurk-backup.service", "aurk-notifications.service"}


def send_alert(unit, config, state_dir, *, now=None):
    if unit not in ALLOWED_UNITS:
        raise ValueError("Unsupported service name")
    recipient = config.get("AURK_ALERT_EMAIL", "")
    sender = config.get("MAIL_FROM") or config.get("MAIL_USERNAME")
    if not recipient or not sender or not config.get("MAIL_SERVER"):
        raise ValueError("Configure the alert recipient and SMTP settings")
    tls = str(config.get("MAIL_USE_TLS", "true")).lower() == "true"
    ssl_enabled = str(config.get("MAIL_USE_SSL", "false")).lower() == "true"
    if tls == ssl_enabled:
        raise ValueError("Choose exactly one secure SMTP transport")
    port = int(config.get("MAIL_PORT") or (465 if ssl_enabled else 587))
    now = time.time() if now is None else now
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = state_dir / (unit + ".json")
    if marker.exists():
        previous = json.loads(marker.read_text(encoding="utf-8"))["last_attempt"]
        if 0 <= now - previous < 3600:
            return False
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "AURK service failure: " + unit
    message.set_content(
        "AURK needs operator attention.\n\nService: " + unit +
        "\nObserved at: " + datetime.fromtimestamp(now, timezone.utc).isoformat() +
        "\n\nInspect the private service logs, readiness, disk space and job queues. "
        "This alert contains no customer records, credentials or log contents. "
        "Repeated attempts for this service are suppressed for one hour.\n")
    # Record before SMTP: a timeout can occur after the provider accepts a message.
    # systemd serializes each template instance, so one service cannot send concurrently.
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps({"last_attempt": now}), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(marker)
    context = ssl.create_default_context()
    if ssl_enabled:
        connection = smtplib.SMTP_SSL(config["MAIL_SERVER"], port, timeout=10, context=context)
    else:
        connection = smtplib.SMTP(config["MAIL_SERVER"], port, timeout=10)
    with connection as smtp:
        if tls:
            smtp.starttls(context=context)
        if config.get("MAIL_USERNAME"):
            smtp.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
        if smtp.send_message(message):
            raise RuntimeError("Alert recipient refused")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unit", choices=sorted(ALLOWED_UNITS))
    parser.add_argument("--env-file", type=Path, default=Path("/home/ubuntu/Aurk/.env"))
    parser.add_argument("--state-dir", type=Path, default=Path("/var/lib/aurk-alerts"))
    args = parser.parse_args()
    config = {**dotenv_values(args.env_file), **os.environ}
    try:
        sent = send_alert(args.unit, config, args.state_dir)
    except Exception as exc:
        # Provider exceptions can contain addresses and authentication details.
        print("Operational alert failed (" + type(exc).__name__ + "); inspect private settings.")
        return 1
    print("Alert submitted to SMTP; verify inbox delivery." if sent else "Alert attempt suppressed by the one-hour cooldown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
