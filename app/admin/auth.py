from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import limiter
from app.models import User
from app.admin.security import is_admin, issue_admin_session, revoke_admin_session, valid_admin_session
from app.security.session_auth import bind_login_session

# A missing user still performs the same expensive password check.
_DUMMY_HASH = generate_password_hash("not-a-login-credential")


def register_auth(bp):
    @bp.route("/login", methods=["GET", "POST"])
    @limiter.limit("5 per minute; 30 per hour", methods=["POST"])
    def login():
        if valid_admin_session():
            return redirect(url_for("admin.dashboard"))
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            user = User.query.filter_by(email=email[:255]).first() if len(email) <= 255 else None
            matches = check_password_hash(user.password_hash if user else _DUMMY_HASH, password[:1024])
            if not user or not matches or len(password) > 1024 or not is_admin(user):
                flash("Invalid email or password.", "error")
                return render_template("admin/login.html"), 401
            revoke_admin_session()
            guest_cart = session.get("guest_cart")
            session.clear()  # Rotate CSRF and authentication state on elevation.
            if guest_cart:
                session["guest_cart"] = guest_cart
            login_user(user, remember=False, fresh=True)
            bind_login_session(user)
            issue_admin_session(user)
            target = request.args.get("next", "")
            if not target.startswith("/admin/") or "\\" in target or any(ord(c) < 32 for c in target) or target.startswith("/admin/login"):
                target = url_for("admin.dashboard")
            return redirect(target)
        return render_template("admin/login.html")

    @bp.post("/logout")
    def logout():
        revoke_admin_session()
        logout_user()
        session.clear()
        return redirect(url_for("admin.login"))
