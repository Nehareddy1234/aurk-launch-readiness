"""Server-side Google OpenID Connect; tokens never enter browser storage."""
import secrets
from urllib.parse import urlsplit

from authlib.integrations.flask_client import OAuth
from flask import current_app, flash, redirect, request, session, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from app.extensions import db, limiter
from app.models import User


def init_google(app):
    oauth = OAuth(app)
    oauth.register("google", client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256", "timeout": 10})
    app.extensions["customer_oauth"] = oauth


def configured():
    return all(current_app.config.get(key) for key in
        ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"))


def register_google_routes(bp):
    @bp.post("/google")
    @limiter.limit("10 per minute")
    def google_login():
        from app.auth.routes import _safe_next_url
        if current_user.is_authenticated:
            return redirect(_safe_next_url(request.args.get("next")) or url_for("main.home"))
        if not configured():
            flash("Google sign-in is not available yet. Use your email or phone and password.", "error")
            return redirect(url_for("auth.login", next=_safe_next_url(request.args.get("next"))))
        callback = current_app.config["GOOGLE_REDIRECT_URI"]
        parsed = urlsplit(callback)
        local_preview = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password
                or parsed.query or parsed.fragment
                or (parsed.scheme != "https" and not local_preview)):
            flash("Google sign-in is unavailable. Please use your password.", "error")
            return redirect(url_for("auth.login"))
        session["google_next"] = _safe_next_url(request.args.get("next"))
        try:
            return current_app.extensions["customer_oauth"].google.authorize_redirect(callback)
        except Exception:
            session.pop("google_next", None)
            current_app.logger.warning("Google authorization could not be started.")
            flash("Google sign-in is unavailable. Please try again or use your password.", "error")
            return redirect(url_for("auth.login"))

    @bp.get("/google/callback")
    @limiter.limit("20 per minute")
    def google_callback():
        from app.auth.routes import _safe_next_url, complete_customer_login
        next_url = _safe_next_url(session.pop("google_next", None))
        if current_user.is_authenticated:
            return redirect(next_url or url_for("main.home"))
        if not configured():
            return redirect(url_for("auth.login", next=next_url))
        try:
            # Authlib verifies OAuth state, signature, issuer, audience, expiry and nonce.
            token = current_app.extensions["customer_oauth"].google.authorize_access_token()
            info = token.get("userinfo") or {}
            subject = info.get("sub")
            email = (info.get("email") or "").strip().lower()
            if not isinstance(subject, str) or not subject or len(subject) > 255 or info.get("email_verified") is not True or not email or len(email) > 255:
                raise ValueError("Unverified identity")
            user = User.query.filter_by(google_sub=subject).first()
            if user is None:
                candidates = User.query.filter(db.func.lower(User.email) == email).limit(2).all()
                if len(candidates) > 1:
                    raise ValueError("Use your existing password")
                user = candidates[0] if candidates else None
                if user:
                    # Google is authoritative for Gmail / verified Workspace email only.
                    if user.google_sub or not (email.endswith("@gmail.com") or info.get("hd")):
                        raise ValueError("Use your existing password")
                else:
                    user = User(is_active=True, email=email, first_name=(info.get("given_name") or info.get("name") or "Customer")[:100],
                        last_name=(info.get("family_name") or "")[:100],
                        password_hash=generate_password_hash(secrets.token_urlsafe(48)))
                    db.session.add(user)
                    from app.services.customer_emails import queue_customer_email
                    queue_customer_email("welcome", user)
                if not user.is_active or user.roles:
                    raise ValueError("Use the existing sign-in method")
                user.google_sub = subject
            if not user.is_active or user.roles:
                raise ValueError("Use the existing sign-in method")
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning("Google sign-in failed or was declined.")
            flash("Could not sign in with Google. Try again or use your existing password.", "error")
            return redirect(url_for("auth.login", next=next_url))
        return complete_customer_login(user, next_url)
