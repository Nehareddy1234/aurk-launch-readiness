from functools import wraps
from flask import abort, g
from flask_login import current_user


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from app.admin.security import is_admin, valid_admin_session
            if not is_admin(current_user) or not (g.get("admin_authenticated") or valid_admin_session()) or not current_user.has_permission(permission):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
