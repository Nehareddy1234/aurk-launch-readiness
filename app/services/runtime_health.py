"""Readiness checks shared by the HTTP endpoint and deployment checks."""
import os
from pathlib import Path
from flask import current_app
from app.extensions import db

EXPECTED_SCHEMA_REVISION = "d4ab72cd5610"


def check_runtime_dependencies():
    """Raise on unusable database/schema, shared limiter or persistent uploads.

    The caller must never expose the exception/configuration to public clients.
    Test databases made with create_all deliberately have no Alembic revision.
    """
    try:
        db.session.execute(db.text("SELECT id FROM store_settings LIMIT 1"))
        if current_app.config.get("REQUIRE_SCHEMA_REVISION", False):
            revisions = set(db.session.scalars(db.text("SELECT version_num FROM alembic_version")))
            if revisions != {EXPECTED_SCHEMA_REVISION}:
                raise RuntimeError("Database revision does not match the release")
    finally:
        db.session.rollback()
    storage = current_app.config.get("RATELIMIT_STORAGE_URI", "")
    if current_app.config.get("RATELIMIT_ENABLED", True) and storage.startswith(("redis://", "rediss://")):
        import redis
        with redis.Redis.from_url(storage, socket_connect_timeout=2, socket_timeout=2) as client:
            client.ping()
    upload = Path(current_app.config["UPLOAD_DIR"])
    if not upload.is_dir() or not os.access(upload, os.W_OK | os.X_OK):
        raise RuntimeError("Persistent upload directory is not writable")
