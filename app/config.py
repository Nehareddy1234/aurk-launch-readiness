import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(BASE_DIR / ".env")

class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "5")),
        "pool_timeout": 10,
    }

    ADMIN_SESSION_IDLE_SECONDS = int(os.environ.get("ADMIN_SESSION_IDLE_SECONDS", "1800"))
    ADMIN_SESSION_MAX_SECONDS = int(os.environ.get("ADMIN_SESSION_MAX_SECONDS", "28800"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_NAME = "ar_drips_session"

    # CSRF protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Prevent browsers from unnecessarily sending the session
    # cookie when navigating from another site.
    SESSION_COOKIE_PATH = "/"

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_PATH = "/"

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    ORDER_ALERT_EMAIL = os.environ.get("ORDER_ALERT_EMAIL", "")
    INTEREST_NOTIFICATION_EMAIL = os.environ.get("INTEREST_NOTIFICATION_EMAIL", "")
    ORDER_ALERT_WHATSAPP = os.environ.get("ORDER_ALERT_WHATSAPP", "")
    CUSTOMER_EMAILS_ENABLED = os.environ.get("CUSTOMER_EMAILS_ENABLED", "false").lower() == "true"
    CUSTOMER_SUPPORT_EMAIL = os.environ.get("CUSTOMER_SUPPORT_EMAIL", "support@aurk.in")
    CUSTOMER_NOREPLY_EMAIL = os.environ.get("CUSTOMER_NOREPLY_EMAIL", "no-reply@aurk.in")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "")
    WHATSAPP_ORDER_TEMPLATE = os.environ.get("WHATSAPP_ORDER_TEMPLATE", "")
    WHATSAPP_TEMPLATE_LANGUAGE = os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "en_US")

    MAX_CONTENT_LENGTH = int(
        os.environ.get(
            "MAX_CONTENT_LENGTH",
            str(100 * 1024 * 1024),
        )
    )

    UPLOAD_DIR = os.environ.get(
        "UPLOAD_DIR",
        str(BASE_DIR / "instance" / "uploads"),
    )

    RATELIMIT_STORAGE_URI = os.environ.get(
        "RATELIMIT_STORAGE_URI",
        "memory://",
    )

    RATELIMIT_HEADERS_ENABLED = True
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    SEARCH_INDEXING_ENABLED = os.environ.get("SEARCH_INDEXING_ENABLED", "false").lower() == "true"
    GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    COD_SERVICEABILITY_REQUIRED = True
    BUSINESS_LEGAL_NAME = os.environ.get("BUSINESS_LEGAL_NAME", "")
    BUSINESS_ADDRESS = os.environ.get("BUSINESS_ADDRESS", "")
    BUSINESS_RETURN_ADDRESS = os.environ.get("BUSINESS_RETURN_ADDRESS", "")
    BUSINESS_GRIEVANCE_NAME = os.environ.get("BUSINESS_GRIEVANCE_NAME", "")
    BUSINESS_GRIEVANCE_EMAIL = os.environ.get("BUSINESS_GRIEVANCE_EMAIL", "")
    BUSINESS_GSTIN = os.environ.get("BUSINESS_GSTIN", "")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SEARCH_INDEXING_ENABLED = True
    COD_SERVICEABILITY_REQUIRED = False
    CUSTOMER_EMAILS_ENABLED = False
    PUBLIC_BASE_URL = ""
    CUSTOMER_SUPPORT_EMAIL = os.environ.get("CUSTOMER_SUPPORT_EMAIL", "support@aurk.in")
    CUSTOMER_NOREPLY_EMAIL = os.environ.get("CUSTOMER_NOREPLY_EMAIL", "no-reply@aurk.in")
    MAIL_SERVER = ""
    WHATSAPP_ACCESS_TOKEN = ""

    # Tests must not depend on the production secret.
    SECRET_KEY = os.environ.get(
        "TEST_SECRET_KEY",
        "ar-drips-test-secret",
    )

    WTF_CSRF_ENABLED = False

    # Use an isolated in-memory database for tests.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "sqlite:///:memory:",
    )

    # SQLite does not use the MySQL connection-pool options above.
    SQLALCHEMY_ENGINE_OPTIONS = {}

    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    REQUIRE_SCHEMA_REVISION = True
    SEARCH_INDEXING_ENABLED = os.environ.get("SEARCH_INDEXING_ENABLED", "true").lower() == "true"

    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    )

    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
