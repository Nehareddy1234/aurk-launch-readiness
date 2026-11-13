# Product availability and customer interest

## Deploy

No new dependencies are required. This feature reuses SQLAlchemy, Flask-Migrate,
Flask-Login, Flask-WTF CSRF, Flask-Limiter, and the existing SMTP service.

Back up the database, deploy the code, then apply the migration before serving requests:

```powershell
.venv/Scripts/python.exe -m flask --app wsgi:app db upgrade
```

For Docker, the existing Compose startup command already runs `db upgrade`:

```sh
docker compose up -d --build web
```

Migration `56ef94ab7832` follows `45de83fa6721`. It adds
`products.product_status` (default `available`, with a check constraint) and
`product_interests`. Existing products retain normal purchasing behaviour and
their current visibility and stock. Interest records include the product, optional
account ID, contact snapshots, status at registration, UTC registration time, and
email notification time. A unique product/identity constraint prevents duplicates;
product ID, customer ID, and email are indexed. Product deletion cascades to its
interests; user deletion sets the optional account reference to NULL. Existing
product archiving retains the interest history.

## Configuration

Set these in the deployment environment / `.env`:

```dotenv
INTEREST_NOTIFICATION_EMAIL=owner@example.com
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=your-smtp-user
MAIL_PASSWORD=your-smtp-password
MAIL_FROM=store@example.com
MAIL_USE_TLS=true
MAIL_USE_SSL=false
```

Use your existing SMTP provider's settings. `MAIL_FROM` is the project's existing
sender setting; no new SMTP credentials or mail library are introduced. For
implicit TLS, use the provider's SSL port and `MAIL_USE_SSL=true`.

Interest is committed before sending email. SMTP failure does not lose the
registration or prompt the customer to submit it again. The admin list shows
`Pending retry`. Schedule this command periodically (for example every five minutes):

```powershell
.venv/Scripts/python.exe -m flask --app wsgi:app send-interest-alerts
```

Docker equivalent:

```sh
docker compose exec -T web python -m flask --app wsgi:app send-interest-alerts
```

Each invocation attempts up to 100 pending emails. Successful notifications are
not resent. SMTP acceptance is not an inbox delivery guarantee. As with most SMTP
outboxes, a process crash after SMTP acceptance but before the database commit can
cause a duplicate notification on retry.

## Admin workflow

Open **Products → Add Product / Edit Product → Product status**, select Available,
Coming Soon, or Out of Stock, then save. Keep **Visible in shop** checked to display
the product. Availability does not alter size/colour inventory: an Available
product still needs an active variant with stock to be purchased.

**Product Interest** in the admin sidebar shows the total, per-product counts,
a product filter, paginated registrations, and email delivery status. It uses the
existing `customers.manage` permission because it exposes customer contact details.
Product status editing uses the existing product create/update permissions.

## Customer workflow

Coming Soon and Out of Stock products remain visible with a blurred visual area,
status badge, and an **I'm Interested** button on homepage cards, shop cards, and
product details. Available products keep their existing cart flow. Server-side
cart add/update and checkout checks enforce availability even for manipulated
requests or products changed after being added to a cart. Checkout locks product
rows and reads current status before creating an order.

Interest uses AJAX when JavaScript is available and a regular CSRF-protected form
otherwise. Successful submissions disable matching buttons and remain registered
after a reload. Logged-in customers use their saved name, email, and phone. Guests
are anonymous and identified by a random signed-session identifier; no account or
contact form is required, and emails identify them as Guest / Not provided.
No customer identity or status submitted by the browser is trusted.

There is one registration per product/account or product/guest session, including
across availability changes. Clearing cookies gives a guest a new identity.
Rate limits (10/minute, 60/hour per client IP) supplement database uniqueness.
Use the existing shared `RATELIMIT_STORAGE_URI` configuration for multi-worker
deployments. This feature notifies the owner; it does not send customers restock
emails.

## Validation and release checks

Automated coverage is in `tests/integration/test_product_availability.py`, alongside
the existing commerce, authentication, admin, email, and migration suites. Run:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
```

Tests use an isolated SQLite database and mocked SMTP. Before release, verify the
migration against staging MySQL, deliver a real test notification, and check shop,
homepage, and detail layouts on desktop and mobile. No production migration or real
notification is sent by the automated tests.

## Implementation files

- Models/config: `app/models/catalog.py`, `app/models/engagement.py`,
  `app/models/__init__.py`, `app/config.py`, `.env.example`.
- Routes/services: `app/products/routes.py`, `app/cart/routes.py`,
  `app/checkout/routes.py`, `app/admin/routes.py`,
  `app/services/product_interests.py`, `app/__init__.py`.
- Storefront: `app/templates/shop/_interest.html`, `_quick_add.html`,
  `_home_card.html`, `shop.html`, `product.html`; `app/static/js/app.js`,
  `app/static/css/aurk.css`.
- Admin: `app/templates/admin/product_form.html`, `base.html`,
  `_components.html`, `interests.html`.
- Migration/tests: `migrations/versions/56ef94ab7832_product_availability.py`,
  `tests/integration/test_product_availability.py`,
  `tests/integration/test_migrations.py`.
