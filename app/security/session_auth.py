"""Bind signed login cookies to the current password without a schema change."""
import hashlib
import hmac
from flask import session


def password_fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()


def bind_login_session(user):
    session['auth_fingerprint'] = password_fingerprint(user)


def matches_login_session(user):
    stored = session.get('auth_fingerprint')
    return isinstance(stored, str) and hmac.compare_digest(stored, password_fingerprint(user))
