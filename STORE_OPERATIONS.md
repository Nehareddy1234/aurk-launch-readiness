# AR Drips

Production-oriented Flask/MySQL e-commerce foundation for the AR Drips streetwear store.

## Stack
Python, Flask, SQLAlchemy, Flask-Migrate, Flask-WTF, Flask-Login, Flask-Limiter, MySQL, Pillow, Gunicorn and Nginx.

## Setup

Follow the current [README setup instructions](README.md#local-setup-on-windows). Existing migrations must be applied with `python -m flask --app run.py db upgrade`; do not initialize a second migration history.

## Security
Never commit `.env`. Production must use HTTPS, secure cookies, a real rate-limit store, a managed/object image store where appropriate, restricted database credentials, backups and a properly configured reverse proxy. Payment integration is intentionally not enabled until provider credentials and gateway-specific verification code are configured.

## Owner workflow
Normal product operations belong in the admin CMS; source code should not be edited to change product information.


## Cash-on-delivery orders and owner confirmation

Checkout saves a Pending order, its delivery address and line items, a pending cash-on-delivery payment, and two persistent owner alerts. Inventory is reduced when the order is placed. The customer sees Awaiting confirmation. An administrator with `orders.manage` can sign in at `/admin/login`, review the order under Orders and press Confirm order. This changes the status to Confirmed; it does not mark payment as paid. The customer order page checks for status updates every 15 seconds and displays: Order confirmed - you will receive a call shortly.

Apply the migration with `python -m flask --app run.py db upgrade`. It adds the alert table and grants `orders.manage` to the existing Super Admin role. New admins created through `python -m scripts.create_admin` receive this permission too.

### Activate owner alerts

Receiving contact details alone are not sufficient to send email or WhatsApp messages. Set the following in your local `.env`, then restart Flask. Do not commit credentials.

- `PUBLIC_BASE_URL`: the deployed site's HTTPS address, for example `https://your-store.example`. A localhost address cannot be opened from your phone.
- `ORDER_ALERT_EMAIL`: your receiving email address.
- `ORDER_ALERT_WHATSAPP`: your receiving WhatsApp number with country code, digits only.
- Email: `MAIL_SERVER`, `MAIL_PORT`, `MAIL_FROM`, and, when required by the provider, `MAIL_USERNAME` and `MAIL_PASSWORD`. Port 587 normally uses `MAIL_USE_TLS=true` and `MAIL_USE_SSL=false`. For implicit TLS on port 465, use `MAIL_USE_SSL=true` and `MAIL_USE_TLS=false`. Use the sending provider's supported credentials.
- WhatsApp Cloud API: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_API_VERSION` (a supported version from your Meta dashboard), `WHATSAPP_ORDER_TEMPLATE`, and `WHATSAPP_TEMPLATE_LANGUAGE` (defaults to `en_US`). The business sender and receiving owner number must be configured with Meta; a regular WhatsApp number alone is not a sending API.

Create an approved WhatsApp template with exactly seven positional text parameters in its body, in this order: order number, customer name, customer phone, delivery address, items, COD total, review URL. Example body:

```
New COD order {{1}}. Customer: {{2}}. Phone: {{3}}. Deliver to: {{4}}. Items: {{5}}. Pay on delivery: {{6}}. Review and confirm: {{7}}. Sign in as an administrator to confirm.
```

The item summary is shortened for WhatsApp; the linked authenticated page always contains the full order. The email includes the complete summary and review link. Visiting a link does not change status: confirmation requires an authenticated, CSRF-protected POST from the review page.

Meta reference: https://www.postman.com/meta/whatsapp-business-platform/request/o65u5m5/send-message-template-text

### Alert failures and retries

Checkout attempts both channels after committing the order. Missing configuration or sending failures do not delete or cancel the order. The owner review page shows each channel as Pending, Failed, or Submitted, and has a Retry unsent alerts button. Submitted means provider acceptance, not verified delivery. Successful channels are not deliberately resent.

Checkout saves alert jobs with the order and redirects after commit. Compose runs an alert worker every 30 seconds. Outside Compose, schedule `python -m flask --app run.py send-order-alerts` periodically using the same environment as the website. Each run handles up to 25 eligible alerts. Failed sends are retried with delays from 1 to 60 minutes. An admin can retry an individual order immediately. A crash after provider acceptance but before saving its result can cause a duplicate alert on retry. Confirmation remains idempotent.

The software integration can be tested with mocks, but live delivery must be verified after real sender credentials, template approval and the public URL are configured. No online payment gateway is used.


## Guest shopping

Visitors can browse products and add, update, or remove bag items without an account. The signed browser session stores only variant IDs and quantities (up to 40 distinct options, 99 units each); prices and availability always come from the database. Checkout requires sign-in. A successful login merges the guest bag into the account cart and then clears the guest bag after the database commit. Existing account quantities are combined up to 99; any adjustment is disclosed. Stock changes remain visible in the bag and are validated again at checkout. Registration preserves the checkout destination and guest bag through the subsequent sign-in step. Guest bags are browser-session based and are not shared between devices.


## Order fulfilment

In Manage orders, filter by status or search the order number/customer name. Orders move from Pending to Confirmed, then Shipped, then Delivered. Mark shipped after handoff and delivered after verifying delivery. Delivery does not automatically mark a cash-on-delivery payment as collected.

Pending or Confirmed orders can be cancelled with an internal reason. Cancellation restores the ordered stock, cancels pending COD payment records, and skips outstanding new-order alerts in one database transaction. Repeated updates do not restore stock or record the same transition twice. Shipped/Delivered orders cannot use this cancellation flow; returns and post-delivery payment reconciliation are separate work. The admin review page shows an audit history, and customers see status changes on their order page.


## Recording COD receipts

After an order is Delivered, its admin review page offers Record payment received. The owner must explicitly acknowledge that the full amount was received or courier remittance was verified. The server checks the order status, payment provider, amount and currency, records the receipt time and an audit event, and ignores duplicate submissions. This records an offline receipt; it does not charge the customer. Payment corrections and partial receipts are not supported by this action.


## Collections

Admin > Manage collections lets users with products.update create and edit categories, their descriptions, URL slugs, display order and navigation visibility. Assign products through the existing product editor. Hiding a category removes storefront collection links, but leaves its active products available in the all-products shop. Collection descriptions appear on their filtered shop pages. Existing category links change when their slug changes.


## Local completion and verification

See [LOCAL_STATUS.md](LOCAL_STATUS.md) for completed store functionality, agreed policy rules, final test results and excluded hosting work. Prices shown in the shop and price sorting use available variant prices. Checkout enforces India delivery, and reset links are invalidated after a password change.


## Separate admin workspace

Open `/admin/login` to access the protected monochrome management workspace. Customer sign-in does not grant admin access. The existing Super Admin account and password are retained; the new migration grants its workspace permissions.

See [ADMIN_WORKSPACE.md](ADMIN_WORKSPACE.md) for all routes, permissions, session behavior, database changes, local commands, tests and remaining limitations. Admin uses its own CSS, JavaScript and template layout. The customer storefront keeps the existing logo, brand colors and shopping/checkout flows.

Apply migrations with `python -m flask --app run.py db upgrade` after installing `requirements.txt`. New optional settings are `ADMIN_SESSION_IDLE_SECONDS` (1800) and `ADMIN_SESSION_MAX_SECONDS` (28800). Restart the development server after upgrading dependencies.
