# Production test report ? AURK

Tested 19 October 2026 (Asia/Kolkata). Target: https://aurk.in.

## Result

The local automated suite passed: **115 tests, 0 failures**, with four migration-library deprecation warnings. Dependency consistency (`pip check`) and JavaScript syntax checks passed.

The live site is reachable and **37 of 37 read-only public smoke checks passed** (pages, protected-page redirects, assets and a video range request). **Production sign-off remains pending**: the deployed website still has older code, and authenticated workflows, mobile rendering, AWS settings and operational recovery have not been verified.

## Confirmed on the live website

- HTTPS homepage and shop return 200. The TLS connection succeeds without disabling certificate validation.
- HTTP redirects to HTTPS (301).
- `/api/health` returns 200 and `{"status":"ok"}`. This endpoint is a liveness check; it does not query the database.
- Unauthenticated `/admin` redirects to `/admin/login` (302). Further admin-page checks follow redirects and verify the final URL is the login page.
- Admin login returns `Cache-Control: no-store, private` and `X-Robots-Tag: noindex, nofollow`.
- Session cookies carry Secure, HttpOnly and SameSite=Lax flags.
- HSTS, CSP, anti-framing and nosniff headers are present.
- A deliberately missing public page returns 404 without a Python traceback.
- The displayed product detail page, product images and referenced static assets respond successfully.
- Homepage MP4 supports byte-range requests (206 Partial Content).

HTTP checks do not prove that JavaScript executes correctly, that videos decode in every browser, or that protected workflows work end to end.

## Findings to resolve or verify before sign-off

### 1. Recent changes have not been deployed ? confirmed live

The public homepage still contains `SHOP AT YOUR PACE`. It references the older `20261013-gallery` storefront script and `20261013-dialog` admin script. The current workspace has updated text, hover behavior, product-video support and cursor styles. Re-test after deploying the intended workspace version. Do not assume local passing tests describe the currently deployed source.

### 2. Existing upload-limit override prevents larger videos ? confirmed locally; AWS value unknown

The configured local production profile reads **8 MB**, because the existing environment overrides the new 100 MB default. Its secure-cookie setting is also false locally. Live cookies are Secure, so that local setting does not establish a live failure.

For the AWS deployment, verify `MAX_CONTENT_LENGTH=104857600`, `SESSION_COOKIE_SECURE=true`, and `FLASK_CONFIG=production`. The running service uses `wsgi:app`, whose entry point already selects production. Ensure the active Nginx server uses `client_max_body_size 100M;`. Updating the repository sample alone does not update the running server configuration. Do not copy the local `.env` wholesale to production.

### 3. Upload preview policy ? source finding

`app/static/js/admin.js` uses `URL.createObjectURL()` for previews. `app/security/headers.py` currently permits images from self/data only and has no `media-src` allowance for blob URLs. This policy is expected to block local image/video previews. Add a narrowly scoped `blob:` allowance for image/media previews, retain restrictions for scripts, and verify the uploader in a browser. The live CSP has the same image-source restriction. No authenticated upload was attempted.

The 413 error message in `app/__init__.py` also still says 8 MB. Make it reflect the configured request limit.

### 4. Rate limiting behind Nginx and multiple workers ? deployment verification required

The local configuration uses `memory://` storage. If AWS uses this too, limits are per worker and reset on process restart. Use a shared supported backend for consistent production limits. Application source keys limits using `get_remote_address` and has no explicit forwarded-client-IP middleware. With Nginx proxying, verify the app sees each visitor's actual IP rather than the proxy address; configure trust only for the known proxy topology. Do not blindly trust arbitrary forwarded headers. No live brute-force or rate-limit saturation tests were performed.

### 5. Operational and browser checks ? pending

- Confirm database migration revision matches the deployed migration head; local tests use SQLite and do not verify the live MySQL server.
- Verify scheduled private database backups and upload backups; perform a restore drill in a separate environment.
- Confirm Gunicorn starts automatically after reboot, logs are rotated, storage has free space, and HTTPS certificate renewal is healthy.
- Check the storefront and checkout on desktop and a real phone: layout, keyboard access, product hover/swipe, image/video playback and typing fields.
- In staging, test registration/sign-in, guest bag merge, size/colour stock, COD checkout, My orders, admin confirmation, cancellation/stock restoration, dispatch/delivery and COD receipt recording. Verify order notifications using a controlled recipient.
- Test valid photo/MP4 uploads, invalid formats and per-file/request limits in staging.

A connected browser was unavailable in this session, so no visual or interactive browser sign-off is claimed. No live orders, logins, uploads or inventory changes were made. No load/stress test or penetration test was performed.

## Re-run checks

From the local workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --tb=short
.\.venv\Scripts\python.exe -m pip check
node --check app/static/js/app.js
node --check app/static/js/admin.js
.\.venv\Scripts\python.exe scripts/production_smoke.py --base-url https://aurk.in
```

The smoke script makes a small set of read-only GET/HEAD requests, checks public assets and protected-page redirects, and saves a JSON report in `instance/production-live-results.json`. It does not submit forms. It is a smoke test, not a load test or security certification.

On EC2, as the Ubuntu user in `/home/ubuntu/Aurk`, these are read-only diagnostic commands:

```bash
sudo nginx -t
.venv/bin/python -m flask --app wsgi:app db current
.venv/bin/python -m flask --app wsgi:app db heads
df -h
```

Check the effective application configuration without printing credentials:

```bash
.venv/bin/python - <<'PY'
from urllib.parse import urlsplit
from wsgi import app
for key in ('DEBUG', 'TESTING', 'WTF_CSRF_ENABLED', 'SESSION_COOKIE_SECURE', 'MAX_CONTENT_LENGTH'):
    print(key, app.config.get(key))
print('Rate-limit backend:', urlsplit(app.config['RATELIMIT_STORAGE_URI']).scheme)
PY
```

Expected: debug/testing false, CSRF/secure cookies true, upload limit 104857600, and a verified shared rate-limit backend. Keep credentials and customer data out of pasted diagnostics.
