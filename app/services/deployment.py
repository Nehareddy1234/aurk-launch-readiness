"""Read-only deployment checks; report missing keys without printing secrets."""
from pathlib import Path
import shutil
import click
from flask import current_app
from flask.cli import with_appcontext
from app.extensions import db


@click.command("check-deployment")
@click.option("--technical-only", is_flag=True, help="Defer business disclosures; does not certify business launch readiness.")
@with_appcontext
def check_deployment_command(technical_only):
    from app.seo import origin
    from app.services.store_settings import get_settings
    from app.services.runtime_health import EXPECTED_SCHEMA_REVISION
    config = current_app.config
    errors=[]
    if current_app.debug or current_app.testing: errors.append("Use the production configuration.")
    if len(config.get("SECRET_KEY") or "") < 32: errors.append("Set a unique SECRET_KEY of at least 32 characters.")
    if not config.get("SESSION_COOKIE_SECURE") or not config.get("REMEMBER_COOKIE_SECURE"): errors.append("Enable secure cookies.")
    if not config.get("WTF_CSRF_ENABLED"): errors.append("Enable CSRF protection.")
    if origin() != "https://aurk.in": errors.append("Set PUBLIC_BASE_URL=https://aurk.in.")
    if config.get("TRUSTED_PROXY_COUNT") != 1: errors.append("Configure exactly one trusted Nginx proxy for this deployment.")
    if not config.get("RATELIMIT_STORAGE_URI", "").startswith(("redis://", "rediss://")): errors.append("Use shared Redis rate-limit storage.")
    else:
        try:
            import redis
            redis.Redis.from_url(config["RATELIMIT_STORAGE_URI"],socket_connect_timeout=3,socket_timeout=3).ping()
        except Exception: errors.append("Redis is not reachable.")
    if not config.get("SEARCH_INDEXING_ENABLED"): errors.append("Public search indexing is disabled.")
    oauth=[bool(config.get(k)) for k in ("GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REDIRECT_URI")]
    if any(oauth) and (not all(oauth) or config.get("GOOGLE_REDIRECT_URI")!="https://aurk.in/auth/google/callback"):
        errors.append("Complete Google sign-in configuration or leave all three values unset.")
    if not config.get("CUSTOMER_EMAILS_ENABLED"): errors.append("Customer transactional email automation is disabled.")
    for key in ("MAIL_SERVER","MAIL_USERNAME","MAIL_PASSWORD","MAIL_FROM","ORDER_ALERT_EMAIL"):
        if not config.get(key): errors.append(f"Configure {key}.")
    if config.get("MAIL_USE_TLS")==config.get("MAIL_USE_SSL"): errors.append("Choose SMTP TLS or SSL, not both or neither.")
    try:
        if db.engine.dialect.name != "mysql": errors.append("Validate the production MySQL database.")
        revisions=set(db.session.scalars(db.text("SELECT version_num FROM alembic_version")))
        if revisions!={EXPECTED_SCHEMA_REVISION}: errors.append("Database migration head differs from this release.")
        from app.models import Product
        demo_count=db.session.scalar(db.select(db.func.count()).select_from(Product).where(
            Product.is_active.is_(True), Product.is_archived.is_(False),
            db.or_(Product.slug.like("qa-%"), Product.name.like("QA %"))))
        if demo_count: errors.append(f"Review/archive {demo_count} active QA catalogue product(s) before public launch.")
        settings=get_settings()
        if not technical_only:
            for field in ("legal_name","address","return_address","grievance_name","grievance_email"):
                if not settings.get(field): errors.append(f"Confirm business {field} in Admin > Business & delivery.")
        if settings["coverage_mode"]=="manual": click.echo("NOTE: Manually verify DTDC COD coverage before each confirmation.")
    except Exception:
        db.session.rollback(); errors.append("Database/schema check failed; inspect private server logs.")
    upload=Path(config["UPLOAD_DIR"])
    if not upload.is_dir(): errors.append("Persistent uploads directory is missing.")
    elif shutil.disk_usage(upload).free < 2*1024**3: errors.append("Less than 2 GiB free on the upload volume.")
    elif not __import__('os').access(upload, __import__('os').W_OK | __import__('os').X_OK): errors.append("Persistent uploads directory is not writable by this service user.")
    for error in errors: click.echo("FAIL: " + error)
    click.echo("Verify externally: HTTPS renewal, off-server restore, worker timers, SMTP delivery and monitoring.")
    if errors: raise click.ClickException(f"{len(errors)} readiness check(s) failed.")
    click.echo("Technical configuration checks passed." if technical_only else "Configuration checks passed; external launch checks still apply.")
