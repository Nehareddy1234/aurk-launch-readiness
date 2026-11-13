"""An explicit admin sign-in elevates the existing Flask-Login identity.

The random credential is stored hashed in the database. Logout revokes it;
password changes, disabled users, role removal and timeouts invalidate it.
Storefront sign-in alone never establishes an admin session.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import abort, current_app, g, redirect, request, session, url_for
from flask_login import current_user
from app.extensions import db
from app.models.admin_session import AdminSession

ADMIN_PERMISSIONS = (
    "dashboard.view", "products.view", "products.create", "products.update",
    "products.delete", "orders.manage", "customers.manage", "inventory.manage",
    "coupons.manage", "reviews.manage", "analytics.view", "settings.manage",
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_admin(user):
    return user.is_authenticated and user.is_active and any(
        user.has_role(role) for role in ("Super Admin", "Admin")
    )


def fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()


def revoke_admin_session():
    token = session.pop("admin_token", None)
    if isinstance(token, str):
        db.session.execute(db.delete(AdminSession).where(
            AdminSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        db.session.commit()
    g.admin_authenticated = False


def issue_admin_session(user):
    now = utcnow()
    token = secrets.token_urlsafe(32)
    db.session.add(AdminSession(user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        password_fingerprint=fingerprint(user), created_at=now, last_seen_at=now,
        expires_at=now + timedelta(seconds=current_app.config["ADMIN_SESSION_MAX_SECONDS"])))
    # Opportunistic cleanup avoids unbounded storage of expired sessions.
    db.session.execute(db.delete(AdminSession).where(AdminSession.expires_at < now))
    db.session.commit()
    session["admin_token"] = token


def valid_admin_session():
    token = session.get("admin_token")
    if not is_admin(current_user) or not isinstance(token, str) or len(token) > 128:
        return False
    record = db.session.scalar(db.select(AdminSession).where(
        AdminSession.token_hash == hashlib.sha256(token.encode()).hexdigest(),
        AdminSession.user_id == current_user.id))
    now = utcnow()
    if not record or record.expires_at <= now or (
        now - record.last_seen_at).total_seconds() >= current_app.config["ADMIN_SESSION_IDLE_SECONDS"] or not hmac.compare_digest(
            record.password_fingerprint, fingerprint(current_user)):
        return False
    record.last_seen_at = now
    db.session.commit()
    g.admin_authenticated = True
    return True


def protect_admin():
    # Default deny: newly added blueprint routes are protected automatically.
    if request.endpoint == "admin.login":
        return None
    if not valid_admin_session():
        revoke_admin_session()
        if current_user.is_authenticated and not is_admin(current_user):
            abort(403)
        return redirect(url_for("admin.login", next=request.path))
