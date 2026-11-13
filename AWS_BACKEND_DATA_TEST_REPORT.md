# AWS backend and live data verification

Verified 6 November 2026, approximately 23:15 IST, on the existing AURK EC2 server in ap-south-2. This is a read-only live inspection, distinct from the earlier isolated automated suites. No deployment, database changes, test accounts/orders, stock changes, customer messages or cloud resource changes were made. The SSM session was terminated normally. Google accounts were not accessed.

## Result

**The inspected live backend is responding, and the existing records passed the consistency checks listed below. This is not full commercial-launch sign-off.** The readiness endpoint is still missing, five active QA products remain, and the previously documented storage, backup and deployment gates are still open.

## Actual data inspected

| Record type | Count |
| --- | ---: |
| users | 4 |
| products | 22 |
| product_variants | 105 |
| inventory | 105 |
| orders | 4 |
| order_items | 6 |
| payments | 4 |
| customer_emails | 9 |
| order_notifications | 4 |

Only aggregate counts were returned. No names, email addresses, phone numbers, shipping addresses, order identifiers, passwords, password hashes or credential values were printed or exported.

## Database integrity checks

The checks found **zero anomalies** for all of the following:

- Orphaned references across 42 declared foreign-key relationships.
- Negative stock, negative reservations, reservations exceeding stock, or variants without inventory records.
- Invalid cart/order-item quantities, negative order monetary components, negative product/variant prices or sale prices above base prices.
- Order total versus subtotal minus discount plus shipping/tax, order subtotal versus item quantities/prices, and item line-total arithmetic.
- Orders with no items/payment records, payment amount/currency mismatches, unknown order status, or paid payments on cancelled orders.
- Paid payments missing their payment timestamp and pending payments on cancelled orders.
- Failed/stale customer notification queues, pending/failed owner alerts or unsent product-interest alerts.
- Blank password storage or password values outside the expected scrypt/PBKDF2 formats. This checks storage format, not actual password strength or login correctness.

All inspected database tables use InnoDB and foreign-key checking is enabled. Queries used read-only transactions, a 3-second per-query execution limit, and rollback/close. A final connection also explicitly set and verified session read-only mode. No CHECK/REPAIR TABLE, writes, schema changes or database reset were executed.

There are **five active QA-marked catalogue products**. Their presence remains a launch/content issue. Review/archive them through an approved process while preserving order history; this inspection did not alter them.

## Stored media

| Reference set | Checked | Missing | Unsafe paths | Empty files |
| --- | ---: | ---: | ---: | ---: |
| Product images | 50 | 0 | 0 | 0 |
| Customer photos | 2 | 0 | 0 | 0 |
| Storefront media | 3 | 0 | 0 | Not measured |

All 55 referenced media paths resolve to existing files inside the configured upload directory. No file was copied, edited or removed. Presence/path/size checks do not prove image/video decoding integrity or recoverability from backup.

## Running backend and access protection

Direct requests were made to the existing loopback Gunicorn service with the production host header. Requests were serial and light; this was not a load test.

| Route/check | Result |
| --- | --- |
| `/api/health` | 200 |
| `/shop` | 200 |
| `/auth/login` | 200 |
| Deliberately nonexistent URL | Correct 404 |
| `/api/ready` | **404 — new release still undeployed** |
| `/admin/`, `/admin/orders`, `/admin/products` without login | 302 to `/admin/login` |
| `/account/`, `/account/orders` without login | 302 to `/auth/login` |
| App service | Active/running; systemd NRestarts=0 at inspection |
| Current installed Nginx configuration | `nginx -t` passed; no reload performed |

The initial HTTP client followed redirects; a second check explicitly disabled redirects to verify the five access-control responses above. No authenticated account access or CSRF-protected POST was exercised.

## Sanitized operational evidence

- The application journal returned 393 lines for the last 24 hours, within a 2,000-line cap. It contained no traceback marker and no ERROR/CRITICAL-marked line in that sample.
- The Nginx access-log sample contained 609 recognizable status records, **zero 5xx** and 362 4xx responses. A stricter request-line parser matched 607 records; its statuses were 190 × 200, 344 × 404, 41 × 301, 13 × 400, 3 × 405, 13 × 206 and 3 × 302.
- Of the stricter parser's 4xx results, 103 involved common probe paths such as WordPress/environment-file locations, 21 involved the known missing readiness/robots/sitemap/feed routes, and 236 were other requests not individually investigated. A 4xx count alone is not proof of an application fault or compromise.

Log bodies, visitor IPs, URLs with query strings and customer information were not exported. Sampling, log rotation and logging configuration limit these conclusions; this is not a claim of zero historical failures.

## What remains for full AWS backend acceptance

These checks inspect current records; four existing orders cannot establish every order/refund/concurrency path. The next test stage must use an isolated AWS environment with synthetic data and outbound SMTP/payment/courier actions disabled:

1. Install the prepared locked release and run clean migrations to `d4ab72cd5610` on a dedicated QA database.
2. Test registration, session revocation, login/recovery, account ownership, invalid input and administrative permissions.
3. Exercise cart/checkout, simultaneous claims on the last item, duplicate submissions, cancellation/restocking, order transitions and COD reconciliation.
4. Exercise overlapping notification workers, bounded retries, uncertain-delivery holds and dependency failures using test doubles/private services.
5. Back up and restore synthetic SQL plus media, then separately rehearse a protected production backup restore under an approved data-access plan.
6. Verify the production server configuration, Redis, Nginx and worker lifecycle in staging; then perform controlled live acceptance after deployment.

**Execution boundary:** the current AWS authorization is read-only. An isolated environment requires authorization for cloud/test-environment writes and an agreed cost limit if new resources are needed. The existing production host had only about 1.1 GiB free and should not be used for an unplanned full test installation or restore. No new AWS resources were created.

Earlier local verification already covered 316 passing Linux backend checks (four MySQL-only skips), 30 focused MySQL regression checks, a corrected synthetic MySQL/uploads restore and a real Linux Gunicorn probe. Those results are documented in the main readiness report; they are not presented as AWS-hosted test-suite runs.

## Evidence files

- `qa_artifacts/aws-backend-data-20261106.json`: sanitized observations from this live inspection.
- `AURK_READINESS_REPORT.html`: deployment readiness and existing blockers.
- `DEPLOYMENT.html`: reviewed release/migration/backup/rollback procedure.
- `WEBSITE_DEPLOYMENT_PLAYBOOK.md`: reusable checklist for other projects.
