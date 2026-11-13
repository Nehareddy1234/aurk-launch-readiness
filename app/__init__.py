import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, render_template, request

load_dotenv()

from app.config import (
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
)
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.security.headers import apply_security_headers


def create_app(config_name=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    configs = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}
    if config_name not in configs:
        raise RuntimeError("Unknown FLASK_CONFIG; choose development, testing or production.")
    app.config.from_object(configs[config_name])

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
        "SECRET_KEY must be configured for the selected environment."
    )

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError(
        "DATABASE_URL must be configured for the selected environment."
    )

    if config_name == "production":
        if len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Production SECRET_KEY must contain at least 32 characters.")
        if not app.config["SESSION_COOKIE_SECURE"] or not app.config["REMEMBER_COOKIE_SECURE"]:
            raise RuntimeError("Production requires secure session and remember cookies.")
        if not app.config["WTF_CSRF_ENABLED"]:
            raise RuntimeError("Production requires CSRF protection.")

    if config_name == "production" and app.config["TRUSTED_PROXY_COUNT"] > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix

        proxy_count = app.config["TRUSTED_PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

   # Initialize database and migration extensions first.
    db.init_app(app)
    # Store and compare timestamps as UTC regardless of the database host timezone.
    with app.app_context():
        if db.engine.dialect.name == "mysql":
            from sqlalchemy import event
            @event.listens_for(db.engine, "connect")
            def mysql_utc_session(connection, _record):
                with connection.cursor() as cursor:
                    cursor.execute("SET time_zone = '+00:00'")
    migrate.init_app(app, db)

    # Initialize authentication, CSRF, and rate limiting.
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    from app.models import register_models
    register_models()

    from app.auth.google import init_google
    init_google(app)

    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.products.routes import products_bp
    from app.cart.routes import cart_bp
    from app.checkout.routes import checkout_bp
    from app.orders.routes import orders_bp
    from app.admin.routes import admin_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    from app.community import community_bp
    app.register_blueprint(community_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp, url_prefix="/cart")
    app.register_blueprint(checkout_bp, url_prefix="/checkout")
    app.register_blueprint(orders_bp, url_prefix="/account")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp)

    from app.seo import init_seo
    from app.services.store_settings import get_settings
    init_seo(app)
    app.context_processor(lambda: {"business_settings": get_settings})

    app.after_request(apply_security_headers)

    def error_page(error):
        code = getattr(error, "code", 500) or 500
        from flask_wtf.csrf import CSRFError
        if isinstance(error, CSRFError) and request.endpoint == "auth.forgot_password":
            from flask import session
            # Reject this submission, but give the customer a fresh form to retry.
            # Never invoke the mail-sending route from an invalid CSRF request.
            session.pop("csrf_token", None)
            app.logger.warning("Password recovery form rejected by CSRF validation: %s", error.description)
            return render_template("auth/forgot_password.html", admin_reset=request.args.get("admin") == "1",
                recovery_error="Your form session expired or changed. We refreshed the form. Enter your email and submit again; no reset email was sent for this attempt."), 400
        if code == 500:
            from flask import g
            g.database_unavailable = True
            db.session.rollback()
        messages = {400: "Check your input and try again. If this form expired, reload the page.",
            403: "You do not have permission to access this page or perform this action.",
            404: "This page or record could not be found.", 405: "This request method is not allowed.",
            413: (f"This upload is too large. The total request must be {app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024):g} MB or smaller."
                  if app.config.get("MAX_CONTENT_LENGTH") else "This upload exceeds the server's request or form limits."),
            429: "Too many attempts. Please wait before trying again.",
            500: "We could not complete this request. Please try again later."}
        if request.path == "/admin" or request.path.startswith("/admin/"):
            return render_template("admin/error.html", code=code, message=messages.get(code, "Unable to complete this request.")), code
        template_code = code if code != 413 else 400
        return render_template(f"errors/{template_code}.html"), code

    for code in (400, 403, 404, 405, 413, 429, 500):
        app.register_error_handler(code, error_page)

    from app.services.order_notifications import send_order_alerts_command
    app.cli.add_command(send_order_alerts_command)
    from app.services.product_interests import send_interest_alerts_command, retry_interest_alert_command
    app.cli.add_command(send_interest_alerts_command)
    app.cli.add_command(retry_interest_alert_command)
    from app.services.operations import check_operations_command
    app.cli.add_command(check_operations_command)

    from app.services.customer_emails import send_customer_emails_command, send_email_test_command
    app.cli.add_command(send_customer_emails_command)
    app.cli.add_command(send_email_test_command)
    from app.services.launch_notifications import process_notifications_command
    app.cli.add_command(process_notifications_command)
    from app.services.deployment import check_deployment_command
    app.cli.add_command(check_deployment_command)

    configure_logging(app)
    return app


def configure_logging(app):
    if app.debug or app.testing:
        return
    handler = RotatingFileHandler("instance/ar_drips.log", maxBytes=2_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
