# Admin workspace

The existing Flask/Jinja storefront, MySQL database, SQLAlchemy models, Flask-Login users and role/permission tables are retained. The storefront still loads `app.css` and `premium.css`, with the supplied original AR Drips logo and its navy/blue/cyan palette on light surfaces (updated at the owner's subsequent request). Admin uses its own Jinja layout, monochrome `admin.css` and `admin.js`; no admin links appear in the customer navbar.

## Local use

1. Stop the running development server with Ctrl+C.
2. From this project directory, install dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
3. Apply migrations: `.\.venv\Scripts\python.exe -m flask --app run.py db upgrade`.
4. Start the site: `.\.venv\Scripts\python.exe run.py`.
5. Open `http://127.0.0.1:5000/admin/login` and use the existing administrator email and password.

Do not recreate your existing account. On a new database only, create an administrator interactively using `.\.venv\Scripts\python.exe -m scripts.create_admin`. Passwords are prompted without echo, confirmed, hashed with Werkzeug's scrypt default, and never placed in code. The command refuses an existing email instead of silently promoting or replacing an account. Forgot-password uses the existing email recovery flow.

## Routes and permissions

All routes below are within the `admin` blueprint. Its default guard protects every route except the explicit login endpoint, including POST actions and private product images. Every management endpoint also has an explicit server-side permission decorator. Forms use ordinary HTTP requests; there is no duplicate public `/api/admin` API. Such nonexistent paths return 404, and `/api/health` contains only service health.

| Route | Function | Permission |
| --- | --- | --- |
| `/admin/login` | Dedicated admin login; GET and POST | Active Admin or Super Admin database role |
| `/admin/logout` | POST-only logout and credential revocation | Valid admin session |
| `/admin`, `/admin/` | Guarded redirects to overview | Valid admin session |
| `/admin/dashboard` | Real store totals and recent orders | dashboard.view |
| `/admin/products` | Search, filter and paginate products | products.view |
| `/admin/products/create` | Product creation and validated image uploads | products.create |
| `/admin/products/<id>/edit` | Product pricing, status, images and options | products.update |
| `/admin/products/<id>/delete` | Delete unused products; hide products with order or stock history | products.delete |
| `/admin/products/<id>/variants` | Add option/SKU with stock | products.update |
| `/admin/products/<id>/variants/<variant_id>` | Update stock and option visibility | products.update |
| `/admin/product-images/<image_id>` | Private image preview, including hidden products | products.view |
| `/admin/categories` | Collection listing | products.update |
| `/admin/categories/create`, `/admin/categories/<id>/edit` | Create/edit collection | products.update |
| `/admin/categories/<id>/delete` | POST; unassign products without deleting them | products.delete |
| `/admin/orders` | Search and filter orders | orders.manage |
| `/admin/orders/<number>` | Order details and existing fulfilment, receipt and notification actions | orders.manage |
| `/admin/customers` | Search customer accounts | customers.manage |
| `/admin/customers/<id>` | Details, order history, enable/disable customer access | customers.manage |
| `/admin/inventory` | Stock, reserved units, low-stock filter | inventory.manage |
| `/admin/inventory/<variant_id>` | POST stock and low-stock threshold changes, with movement history | inventory.manage |
| `/admin/coupons` | Existing database coupon configurations | coupons.manage |
| `/admin/coupons/create`, `/admin/coupons/<id>/edit` | Discount type/value, dates, minimum, caps and limits | coupons.manage |
| `/admin/coupons/<id>/disable`, `/admin/coupons/<id>/delete` | POST; used coupons cannot be deleted | coupons.manage |
| `/admin/reviews` | Existing review records, escaped review text | reviews.manage |
| `/admin/reviews/<id>` | POST approve or reject/hide | reviews.manage |
| `/admin/analytics` | Order status totals, received cash, top ordered products, stock and customers | analytics.view |
| `/admin/settings` | Profile, current-password verified password changes, revoke admin sessions | settings.manage |

Existing product image primary/delete routes and order confirm/status/payment-received/retry-alerts routes retain their paths and permission checks. State transitions still follow the existing order service; cancellation restores stock, while receipt recording requires a delivered order and explicit confirmation. No payment gateway or money-transfer/refund API was introduced.

## Authentication and authorization

There is one existing user/password/role system, not separate customer and administrator databases. Dedicated admin login reauthenticates the user through the existing Werkzeug password verification and Flask-Login session. Storefront login alone does not elevate access, even for an administrator account. Successful elevation clears and reissues signed session/CSRF state, retains a guest bag if present, and creates a random admin credential. Only its SHA-256 hash is stored in the database.

Each admin request verifies the active database user, Admin/Super Admin role, credential ownership, password fingerprint, absolute expiry and idle timeout. It then checks the individual permission. Disabling a user, removing a role/permission, changing a password, expiry, or logout takes effect on following requests. Server-side deletion makes a logged-out admin credential unusable even if its old signed browser cookie is replayed. Admin logout also signs out the shared Flask-Login identity. Ordinary storefront logout revokes the associated admin credential too.

`Super Admin` receives all workspace permissions in the migration. Restricted `Admin` roles must be assigned permissions through a trusted server-side process; no role-changing browser endpoint is exposed. Customer account status management cannot target administrator accounts and cannot assign arbitrary fields or roles.

## Database migration

`34cd72ef5610_admin_workspace` follows `23ab91cd4500`:

- Adds `admin_sessions` linked to existing users, containing token hash, password fingerprint, created/last-seen/expiry timestamps, and indexes.
- Adds missing workspace permission names and links them only to the established Super Admin role.
- Preserves existing users, products, images, orders, customer carts and credentials.
- Does not introduce a second user table or alter the order/payment schema.
- Downgrade removes admin sessions but retains permissions that may have been assigned since migration.

Review-to-product/customer SQLAlchemy relationships add no columns. Coupons and reviews use pre-existing tables.

## Security controls

- Server-side role, session and per-operation permission checks; no frontend role trust.
- Generic admin login errors and equivalent password hashing work for missing accounts; 5 POST attempts/minute and 30/hour per source IP.
- Password lengths bounded to 12-1024 for admin creation/change; no plaintext storage.
- Flask-WTF CSRF on login, logout and every mutation; no CSRF exemptions.
- Signed HttpOnly, SameSite=Lax cookies; Secure cookies in production configuration.
- No-store/private caching and noindex on admin responses, including errors and private images.
- CSP, frame-ancestors none, X-Frame-Options DENY, nosniff, referrer policy and HSTS when serving HTTPS outside debug mode.
- Parameterized SQLAlchemy queries, Jinja escaping, explicit writable fields and server-side validation.
- Financial values reject NaN, infinity, overflows, negatives and excess decimal places.
- Image allowlist restricts decoding to JPEG/PNG/WEBP, validates contents and dimensions, randomizes stored filenames and checks private-serving paths. Upload size remains 8 MB per request; image pixel limit is 20 million.
- Inventory updates use database locks and enforce reserved stock minimums, with actor-attributed stock movement records.
- Raw product-save/database errors are replaced with safe messages. Admin 400/403/404/405/413/429/500 pages use the separate layout.
- No arbitrary store environment editor; mail/database/API secrets never appear in settings. `.env`, environment variants and instance logs/databases are excluded from source control, with `.env.example` retained.

## Configuration

No new secrets are required. Existing `SECRET_KEY`, `DATABASE_URL`, mail and WhatsApp variables remain server-side. Two optional variables have defaults and are documented in `.env.example`:

```dotenv
ADMIN_SESSION_IDLE_SECONDS=1800
ADMIN_SESSION_MAX_SECONDS=28800
```

`RATELIMIT_STORAGE_URI=memory://` remains appropriate for one local process. A shared limiter backend is necessary for consistent limits across multiple processes. Production must use the production configuration and HTTPS for secure cookies; no hosting was configured as part of this work.

## Files

New core files: `app/admin/security.py`, `app/admin/auth.py`, `app/admin/management.py`, `app/models/admin_session.py`, `app/templates/admin/base.html`, `_components.html`, login/error/customer/inventory/coupon/review/analytics/settings templates, `app/static/css/admin.css`, `app/static/js/admin.js`, the migration, and `tests/security/test_admin_workspace.py`.

Modified: existing admin routes/templates, storefront base navigation, authentication user loading/logout, app error handling/configuration, headers/permissions/validators, model registration/review relationships, initial admin script, dependency requirements, `.gitignore`, `.env.example`, tests and documentation.

## Verification and limitations

Verified on 8 September 2026:

- Full suite: **77 passed in 92.32 seconds**, using `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`.
- Coverage includes existing browsing, guest/account carts, checkout, owner confirmation, cancellation/stock restoration, COD receipts, collections, image upload, price sorting and password recovery, plus 21 admin checks for route rendering, customer/guest denial, forged/expired/replayed sessions, permission/role revocation, disabled accounts, password changes, CSRF, actual login throttling, role mass assignment, stock bounds/audit, coupon CRUD, escaped reviews/moderation, category deletion, private hidden images and migration preservation.
- JavaScript syntax check: `node --check app/static/js/admin.js` passed.
- `pip check`: no broken requirements.
- `pip-audit`: initially reported 37 advisory entries in three packages; after updating Pillow to 12.3.0, cryptography to 50.0.1 and pytest to 9.1.1, the scan reported **no known vulnerabilities**. Reports are in `instance/dependency-audit.json` and `instance/dependency-audit-after.json`. This is a point-in-time package advisory check, not proof of application security.
- Local MySQL migration **already applied** to revision `34cd72ef5610`. Existing row counts remained unchanged: 1 user, 2 products, 1 order and 2 product images. The existing Super Admin role has 12 workspace permissions.
- MySQL analytics queries ran successfully. Local Flask requests to `/`, `/shop`, `/cart` and `/admin/login` returned 200; unauthenticated `/admin/dashboard` and `/admin/products` redirected to login.
- No live messages, orders, payments, customer profiles or product records were created or changed during final local checks. Mutation tests used an isolated SQLite database. No hosting changes were made.

For this already-updated workspace, restart the terminal server and open `/admin/login`; the install/migration commands above are for reproducing the setup elsewhere.

Coupon configuration and review moderation are connected to their existing database tables. The existing storefront has no coupon-redemption or customer review-submission workflow; those customer-facing features are not added by this admin separation. A coupon being enabled in administration does not yet discount a checkout. Review rejection uses the existing unapproved/hidden flag rather than introducing a separate rejected state.

Store settings display the current COD/delivery policy and allow profile/security changes. Public policy content and server credentials are intentionally managed outside browser settings. Manual UPI/cash refunds remain outside the existing backend; analytics does not subtract unrecorded refunds. Metrics distinguish placed order value from cash recorded as received.

No browser surface was available through the connected browser tool, so responsive appearance and browser network-error interactions need a manual browser review. Server-side page rendering and form workflows are covered by automated checks. Native form submissions provide browser network failures/retry behavior; the dashboard does not invent an optimistic successful save.

Security is not a guarantee: add administrator MFA and centralized monitoring when appropriate; review permissions periodically, keep dependencies patched and repeat the vulnerability scan. Development debug mode is for local use. New sessions are cleaned up opportunistically at login; a high-volume installation may prefer a scheduled cleanup. Existing signed storefront sessions retain Flask-Login's behavior; the new revocable elevation specifically protects admin operations.

Dependency patch references: [cryptography changelog](https://cryptography.io/en/latest/changelog/), [Pillow release notes](https://pillow.readthedocs.io/en/stable/releasenotes/index.html), [pytest changelog](https://docs.pytest.org/en/stable/changelog.html).

## Simplified product listing

`/admin/products/create` now combines product details, photos, size selection, colour and opening stock in one form. Product links and SKUs are generated automatically. Discount, availability and promotional settings are optional. One save creates the product and audited inventory together; invalid input rolls back the complete listing and keeps text entries for correction. Choose photos again after a validation error. Additional colours and individual stock adjustments remain available through Edit product.

## Dashboard and downloadable reports

The dashboard includes an inclusive IST date range (last 30 days by default, maximum 366 days), order value excluding cancellations, recorded cash receipts, orders placed, average non-cancelled order value, recent orders, status distribution and top products. Attention counts show current operations across all dates. Products and stock counts exclude archived products.

CSV downloads are available at /admin/reports/summary.csv, /admin/reports/orders.csv, /admin/reports/receipts.csv and /admin/reports/inventory.csv. Use start and end ISO dates for financial reports. Inventory is always a current snapshot. All exports require analytics.view; detailed orders/receipts also require orders.manage and inventory requires inventory.manage. Exports include a UTF-8 BOM for Excel, protect text cells against formula interpretation and inherit private no-store admin headers. No customer phone numbers or addresses are included. Cash receipts use payment receipt dates; orders use placement dates. No new permissions or migrations are required.

Every admin HTML page has a deterministic parent back link in the shared layout. Creation and detail screens return to the corresponding section; section pages return to the dashboard; the dashboard and login return to the store.
