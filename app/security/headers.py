from flask import current_app, request, g


def apply_security_headers(response):
    if request.blueprint in {'auth', 'cart', 'checkout', 'orders', 'admin', 'api'}:
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    if not current_app.config.get('SEARCH_INDEXING_ENABLED') or response.status_code >= 400 or request.args.get('q') or request.args.get('sort') or request.endpoint == 'products.search':
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    if request.path == "/account" or request.path.startswith("/account/"):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.path == "/admin" or request.path.startswith("/admin/"):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.endpoint in {"auth.forgot_password", "auth.reset_password", "auth.login", "auth.register", "auth.login_phone", "auth.google_login", "auth.google_callback"}:
        response.headers["Cache-Control"] = "no-store, private"
        # HTTPS CSRF validation requires a same-origin Referer. Send only the
        # origin, never a reset-token path or query string.
        response.headers["Referrer-Policy"] = "strict-origin"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    form_destinations = "'self'"
    if request.endpoint in {"auth.login", "auth.register", "auth.google_login"}:
        # Some browsers apply form-action to redirects after the same-origin OAuth POST.
        form_destinations += " https://accounts.google.com"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; " +
        ("img-src 'self' data: blob:; media-src 'self' blob:; "
         if request.path == "/admin" or request.path.startswith("/admin/")
         else "img-src 'self' data:; media-src 'self'; ") +
        "style-src 'self' 'unsafe-inline'; "
        f"script-src 'self' 'nonce-{getattr(g, 'csp_nonce', '')}'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        f"base-uri 'self'; form-action {form_destinations}"
    )
    if not current_app.debug and request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
