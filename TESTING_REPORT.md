# AURK local verification ? 28 October 2026

Scope: local source review and isolated SQLite, MySQL and Chromium testing. These fixes have **not been deployed to AWS**. No real customer email was sent or store database modified.

## Current results

| Check | Result |
|---|---|
| Full randomized suite (seed 20261029) | **282 passed, 0 failed, 2 skipped**, 370.55 seconds |
| Disposable local MySQL suite | **8 passed, 0 failed**, 70.46 seconds |
| Application statement coverage | **93.19%**, 2929 of 3143 executable statements |
| Python compilation and dependency consistency | Passed |
| JavaScript syntax and 73 Jinja templates | Passed |

The full suite's two skips are MySQL-specific locking checks; both ran successfully in the separate MySQL suite. That suite created and removed its own temporary schema. Four remaining warnings concern the legacy SQLAlchemy Query.get API; they are deprecation warnings, not test failures. Coverage measures statements, not every branch or possible production condition.

Evidence: `qa_artifacts/coverage-20261029.log`, `coverage-20261029.xml`, `coverage-20261029.json`, `mysql-local.log`, and `mysql-local.xml`. The initial run on 28 October had 269 passing tests, 10 failures and 2 skips. Fixes and additional regressions produced the current passing results.

## Fixes verified locally

- **Password-reset HTTP 400:** reproduced in Chromium over local HTTPS with strict CSRF enabled. Recovery pages used `Referrer-Policy: no-referrer`, suppressing the header that HTTPS CSRF validation requires. Changed it to `strict-origin`, preserving only the origin and withholding reset-token paths. Verified requesting the email, resetting the password and signing in. Foreign-origin submissions remain rejected. Expired/invalid CSRF submissions now return an actionable recovery form.
- Customer password reset invalidates other authenticated sessions through a password fingerprint. Admin login binds the same fingerprint. Existing sessions without this binding will require a fresh sign-in after deployment.
- Registration, login and recovery consistently handle email case; ambiguous existing identities are rejected safely.
- Archived products are excluded from public listings, detail pages and product media. Shop relationships load together to avoid per-product query growth.
- Admin image/video previews allow local blob sources within admin CSP only.
- Testing configuration disables customer email automation. Uncertain SMTP outcomes are held for manual review instead of automatically risking duplicate delivery; definitive failures retain normal retry behavior. SMTP cannot guarantee exactly-once delivery across every process crash.
- Model foreign-key types and equivalent boolean defaults now match migration metadata. MySQL queue timestamps avoid fractional-second rounding that could delay a newly queued email. Migration round trips, schema parity and concurrency checks pass.
- Per your approval, future uploaded media is excluded from Git. Files on disk were retained; existing tracked media was not removed from the index.

The full run also covers customer/admin access controls, cart and checkout, inventory, order status, PDF bills and email attachments, storefront content, cover-video sequencing, banner/product carousels, size charts and coming-soon presentation.

## Verification limits and next deployment

Email sending was mocked, so actual SMTP credentials and inbox delivery still require a controlled post-deployment check. Chromium tests do not certify every browser/device, production workload or external service. These results establish that the local automated checks pass, not that every possible code path has been exercised.

Use the current source for any future deployment package: previously prepared bill-only archives predate these fixes. No deployment was performed during this local review.

---

# Historical audit ? 19 October 2026 (superseded)

The following original findings are retained for traceability. Statements below that defects were left unfixed or MySQL was unavailable describe that earlier audit, not the current results above.

# AURK QA audit report

Date: 2026-10-19. Scope: the local repository and isolated test environments only.

**This is an audit, not a production readiness certificate. Application defects were left unfixed as requested. No production/AWS connection or real email sending was used.**

## Results

| Random seed | Total | Passed | Failed | Errors | Skipped | Xfail | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 202 | 255 | 244 | 9 | 0 | 2 | 0 | 241.68 |
| 303 | 255 | 244 | 9 | 0 | 2 | 0 | 247.70 |
| 404 | 255 | 244 | 9 | 0 | 2 | 0 | 222.57 |

Line coverage: **92.80%** (2656/2862 executable lines). Coverage is not branch or concurrency coverage.

Final randomized failure sets identical: **True**. Application/deployment files differing from the discovery hash snapshot: **0**.

The 167-case original suite was first characterized under stricter upload/mail isolation. Its only initial failure was a test fixture creating an already-existing directory, which was corrected. The final runs include new audit regressions and real Chromium tests. No application test was weakened, xfailed, or deleted to hide a defect.

The only expected environmental skips are the two explicit MySQL row-lock tests. A local MySQL service exists, but no dedicated test schema/account was supplied and the development account lacks schema-creation privileges. SQLite does not establish MySQL transaction, collation, deadlock, or locking correctness. The proposed GitHub Actions MySQL job was authored, not executed remotely.

## FAILED TESTS — ordered by severity

### QA-AUTH-002 — High: Password reset leaves another customer session active

- Test: `tests.security.test_qa_audit::test_QA_AUTH_002_password_reset_revokes_other_customer_session`
- Application/source location: `app/auth/routes.py:41,191-195`.
- Expected: Resetting a password invalidates existing authenticated customer sessions.
- Actual: A separately logged-in test client still receives HTTP 200 from /account/ after a successful password reset in another client.
- Reproduce: Create a customer; sign in with client A and verify /account/ returns 200; reset the password with a valid single-use token in client B; request /account/ again with A's original cookie.
- Suggested fix (not applied): Add a per-user session version or authentication fingerprint checked on every customer request, and rotate it on password reset/change. Admin-session deletion alone does not revoke customer cookies.
- Evidence limits: Database-independent reproduction. Requires possession of an already valid customer session; this is not an unauthenticated login bypass.

### QA-AUTH-001 — Medium: Signup and login normalize email case differently

- Test: `tests.security.test_qa_audit::test_QA_AUTH_001_mixed_case_signup_can_sign_in`
- Application/source location: `app/auth/routes.py:56,86`.
- Expected: An account registered with MiXeD@example.com can sign in using its normalized email.
- Actual: Signup preserves local-part case while login lowercases the full address; login fails on the isolated case-sensitive SQLite database.
- Reproduce: POST /auth/register with MiXeD@example.com and a valid password; POST /auth/login with mixed@example.com; GET /account/ returns 302 instead of 200.
- Suggested fix (not applied): Use one explicit email-normalization policy for registration, login, password recovery and uniqueness; review existing records before any normalization migration.
- Evidence limits: The login failure is reproduced on SQLite. A case-insensitive MySQL collation can mask it; live MySQL impact is NOT verified. Treat this as a confirmed normalization/portability defect, not proof all production users are affected.

### QA-CATALOG-001 — Medium: Archived products can still be publicly displayed

- Test: `tests.integration.test_qa_commerce::test_QA_CATALOG_001_archived_products_not_public`
- Application/source location: `app/products/routes.py:24,111-118; app/main/routes.py:16-22`.
- Expected: An archived product is excluded from public catalog queries and its direct detail URL returns 404.
- Actual: A product with is_archived=True and is_active=True returns 200 at its public detail URL. Public queries filter is_active but not is_archived.
- Reproduce: Seed a product with is_active=True and is_archived=True, with a variant; GET /product/<slug>.
- Suggested fix (not applied): Filter is_archived=False consistently in all public product/media queries and define/enforce the archive-active invariant.
- Evidence limits: The usual admin archive action also disables a product. This test exercises inconsistent flags that the model/schema permit, not a demonstrated normal admin-archive workflow failure.

### QA-UI-001 — Medium: Content Security Policy blocks admin image-upload previews

- Test: `tests.e2e.test_local_browser::test_QA_UI_001_admin_upload_preview_not_blocked_by_csp`
- Application/source location: `app/security/headers.py:21; app/static/js/admin.js:64-66`.
- Expected: Selecting a valid image in the admin product form displays its local preview.
- Actual: Chromium creates the preview element, but its blob: URL is refused by img-src 'self' data:. The completed image has naturalWidth=0.
- Reproduce: Sign into admin; open /admin/products/create; choose a valid PNG; wait for the preview image to complete and inspect naturalWidth or the browser CSP error.
- Suggested fix (not applied): Allow blob: in the narrowly required image/media source policies, preferably scoped to admin pages, or use an approved preview URL strategy. Keep the remaining CSP restrictions.
- Evidence limits: Confirmed with real local Chromium and the application's CSP enabled. Image preview failure does not by itself prove server-side uploading fails. Video previews also use blob URLs but were not separately decoded in this browser test.

### QA-PERF-001 — Medium: Shop rendering issues two additional queries per product/variant in the fixture

- Test: `tests.integration.test_qa_commerce::test_catalog_query_growth_and_route_timings`
- Application/source location: `app/products/routes.py:24; app/services/catalog.py:5-9; app/templates/shop/_variant_fields.html:2`.
- Expected: Adding products to a catalog page does not introduce linear per-product size/colour queries.
- Actual: The controlled fixture grows from 10 SELECT statements for one product to 28 for ten products. Timings remain below one second locally, but query count scales linearly.
- Reproduce: Attach SQLAlchemy before_cursor_execute; GET /shop with one stocked variant; seed nine more products with distinct sizes/colours; GET /shop again and compare counts.
- Suggested fix (not applied): Eager-load ProductVariant.size and ProductVariant.color alongside inventory, and measure repeated requests and admin lists after the change.
- Evidence limits: Measured on isolated SQLite; this confirms redundant queries, not production latency. See catalog-performance.json for actual timing measurements.

### QA-EMAIL-001 — Medium: SMTP acceptance followed by a lost response can produce duplicate emails

- Test: `tests.integration.test_qa_email_edges::test_QA_EMAIL_001_provider_acceptance_then_timeout_can_duplicate`
- Application/source location: `app/services/customer_emails.py:82-91`.
- Expected: The requested timeout/idempotency guarantee would permit one provider acceptance for one event.
- Actual: A mock accepts the message then raises TimeoutError. The worker marks it failed and a due retry accepts it a second time.
- Reproduce: Queue one welcome event; use a fake SMTP sender that records acceptance then times out; dispatch; make next_attempt_at due; dispatch again; acceptance count is two.
- Suggested fix (not applied): Document at-least-once delivery explicitly. If exactly-once provider submission is required, adopt a provider API with enforceable idempotency keys or an uncertain-delivery reconciliation state. A unique outbox event alone cannot solve an ambiguous SMTP acknowledgement.
- Evidence limits: A protocol/design limitation exposed by the user's requested guarantee. No real email was sent. This differs from repeat worker runs after a recorded successful submission, which are already deduplicated.

### QA-CONFIG-001 — Medium: TestingConfig can inherit enabled customer email automation

- Test: `tests.security.test_qa_audit::test_QA_CONFIG_001_testing_email_automation_cannot_inherit_live_flag`
- Application/source location: `app/config.py:91-95`.
- Expected: TestingConfig keeps CUSTOMER_EMAILS_ENABLED=False regardless of a live-style environment flag.
- Actual: The explicit False assignment is overwritten by a second environment-based assignment; setting CUSTOMER_EMAILS_ENABLED=true yields True in TestingConfig.
- Reproduce: Evaluate config with CUSTOMER_EMAILS_ENABLED=true; inspect TestingConfig.CUSTOMER_EMAILS_ENABLED.
- Suggested fix (not applied): Remove the duplicate environment override from TestingConfig and keep test mail transports explicitly isolated.
- Evidence limits: QA fixtures force automation off and block SMTP sockets. MAIL_SERVER is also blank in TestingConfig, so this finding does not claim its default configuration alone can send live mail.

### QA-SECURITY-001 — Low: Product uploads do not meet the requested all-uploads Git-ignore policy

- Test: `tests.security.test_qa_audit::test_QA_SECURITY_001_uploads_are_all_gitignored`
- Application/source location: `.gitignore:27-34`.
- Expected: git check-ignore recognizes all upload paths as ignored.
- Actual: Explicit image exceptions allow instance/uploads/products/999/private.jpg into Git. The sensitive customer-photos directory has its own ignore rule and is protected.
- Reproduce: Run git check-ignore --no-index instance/uploads/products/999/private.jpg; exit status is 1.
- Suggested fix (not applied): Decide whether product media are intentional versioned assets. If all uploads must be excluded, remove the image exceptions and review already tracked files without deleting live media.
- Evidence limits: Policy mismatch, not evidence of leaked customer photos or credentials. Existing product-image versioning appears intentional, so application/security impact is limited.

### QA-DB-001 — Low: Fresh SQLite migrations differ from model foreign-key types

- Test: `tests.integration.test_qa_database::test_QA_DB_001_models_match_fresh_migration_schema`
- Application/source location: `app/models/catalog.py:82,286,296,305,360,465; migrations/versions/11b8ff211bcb_initial_schema.py`.
- Expected: Alembic metadata comparison on a freshly migrated test database produces no unexpected type changes.
- Actual: Autogenerate proposes six BIGINT-to-INTEGER changes for catalog foreign keys because BigIntPrimaryKey compiles as INTEGER on SQLite but the initial migration declares those foreign keys BIGINT.
- Reproduce: Create an empty SQLite database; flask db upgrade; compare_metadata with compare_type=True and compare_server_default=True.
- Suggested fix (not applied): Align SQLite variants for the six foreign-key columns, or explicitly document an intentional comparator policy. Confirm independently against MySQL before issuing any production ALTER TABLE.
- Evidence limits: Confirmed SQLite migration portability drift only. MySQL metadata parity is UNVERIFIED, and both types compile to BIGINT there; do not apply the generated SQLite changes blindly to production.

## Security findings and tested protections

- High: QA-AUTH-002 preserves an existing customer session after password reset. Admin-session invalidation is implemented separately.
- Medium test-isolation issue: QA-CONFIG-001 inherits the email-enable flag. Tests override it and block real SMTP/network access.
- Low policy mismatch: QA-SECURITY-001 allows product images into Git. Customer photos, .env, SQL dumps and logs are ignored. A current-tree scan covered 179 tracked/untracked nonignored source/config/document text files and found no known SMTP-key, AWS access-key or private-key patterns (secret-scan.json). No .env/key/log/SQL files were listed by the corresponding tracked-file check. These checks are not an entropy-based or repository-history secret audit.
- Route-wide mutation tests send requests without CSRF tokens to every registered POST/PUT/PATCH/DELETE route and require rejection. See csrf-routes.json.
- Admin access is tested as anonymous, customer, zero-permission admin, fully permissioned Super Admin, and each individual admin permission. Authorized nonexistent-record requests may legitimately return 400/404; this matrix proves the gates, not every successful mutation. Existing CRUD tests exercise actual records.
- Cross-customer order, status, checkout-success, cart-update/remove and address tampering tests verify ownership boundaries. Existing community tests verify pending-photo ownership/admin access and withdrawal boundaries.
- Password hashing, safe redirect rejection, auth rate limits, production-like response headers, and XSS escaping are exercised with synthetic data. The negative SQL search payloads do not produce query errors or stack traces.
- CSP needs a narrow correction for upload previews (QA-UI-001); do not remove the policy wholesale.

Static operational observations, not confirmed live findings: the limiter defaults to memory:// (app/config.py), and its default key is get_remote_address (app/extensions.py). Multi-worker deployments and trusted-proxy/client-IP handling need independent verification; this audit did not access Nginx or the live limiter backend.

## Feature-by-feature evidence

| Area | Result and what was actually exercised |
|---|---|
| Catalog | Search empty/no-result/special/SQL-like/long queries, availability/hidden pricing, sorting and variant stock are tested. QA-CATALOG-001 and QA-PERF-001 remain failing. |
| Cart | No remaining cart-specific failures: guest persistence/update/remove, merge, stock and quantity boundaries, exact submitted SKU, ownership and ignored client price fields are asserted. |
| Accounts | Registration/login/profile/address/password recovery are exercised. QA-AUTH-001 (SQLite collation caveat) and QA-AUTH-002 remain failing. |
| Checkout | No remaining sequential checkout failures: actual order/items/snapshots/totals/COD/inventory/movements/cart-clear/outbox assertions, stock/product/variant revalidation and forced post-order exception rollback. Concurrent last-unit checkout is NOT verified without MySQL. |
| Order lifecycle | No remaining lifecycle-specific failures: invalid-transition matrix, confirmation deduplication, cancellation/restock-once, audit, delivery versus cash receipt and ownership tests pass. |
| Admin | Authentication/session expiry/revocation, role gates, inventory, catalog/category/coupon/review/report operations are exercised. Local image preview fails (QA-UI-001). |
| Emails | SMTP is mocked: sender/recipient/Reply-To/HTML/text/logo/theme/escaping, success/failure/backoff/exhaustion/cancellation/deduplication and Notify me business/customer alerts are asserted. Ambiguous SMTP timeout can duplicate (QA-EMAIL-001); overlapping MySQL worker safety is unverified. |
| Notify me | Guest redirects through login/signup return path; signed-in registration and duplicate suppression; matching acknowledgement/customer data and business Reply-To; repeated worker handling. No restock launch-mail feature is invented. |
| Worn by you | No remaining community-specific failures: public approved-only gallery, each ownership/delivery/consent rule, moderation/withdrawal, private direct URLs, limits, corrupt/oversized images, traversal-safe generated filenames, metadata and executable-tail removal. |
| Migrations | Fresh SQLite upgrade reaches a single 90cd38ef1276 head, latest downgrade/upgrade succeeds, uniqueness/foreign-key/cascade cases are exercised. SQLite catalog foreign-key type drift remains (QA-DB-001). MySQL migration parity has not been run locally. |
| Browser | Real Chromium loopback-only browse/product/variant/cart/login/checkout/order-history journey and gallery/Notify me at 375px and 1440px. No horizontal overflow on measured pages or JS pageerrors in passing journeys. Upload-preview CSP regression remains. |
| Deployment | Static inspection only: Flask production-like boot with dummy values, WSGI/Gunicorn configuration, cookie/header behavior and deployment docs. No AWS, public-domain probing, service restarts or releases. |

## Browser accessibility and performance

axe-core 4.10.3 ran WCAG 2 A/AA and 2.1 AA tags on **8** pages. Recorded violations: **0**. Pages: `/`, `/shop`, `/product/browser-tee`, `/cart`, `/auth/login`, `/admin/login`, `/account/`, `/checkout`.

This is a Chromium DOM audit of synthetic fixture pages, not manual keyboard/screen-reader certification, all product content, mobile accessibility, all interactive states, or full WCAG conformance. The detailed evidence is accessibility.json.

Mobile and desktop document-width measurements are in layout-375.json and layout-1440.json; screenshots are notify-375.png and notify-1440.png. Full-page screenshots may retain the current scroll/focus position. Pointer target geometry and actual touchscreen gestures were not exhaustively audited.

Public route timings recorded: 14. Maximum observed: 0.040s. Routes over one second: []. These are local test timings, not a load test or production SLA.

The shop query-growth regression is recorded in catalog-performance.json. Internal links and static assets referenced by the tested public information pages were requested locally; no broken links/assets remained in that test. Every asset under every admin/product state was not crawled.

## Known limitations — not misreported as new functional failures

- Notify me currently acknowledges a request; no automatic email blast is triggered when the drop goes live.
- Cash on delivery only; no online gateway tests were invented.
- No established courier tracking integration or automated confirmation phone call.
- No established automatic backup schedule. Prior manual backups do not constitute scheduled backup monitoring or restore drills.
- Historical server Nginx limit was 8 MB. The checked-in Nginx template now says 100M and the app allows 100 MB total (photos/video have lower per-file caps). The current live config was not accessed and may still differ; this is an operational verification gap, not a newly measured live failure.
- Customer photos require delivered-order ownership and moderation; no AI garment/photo verification is implemented.
- SMTP submission is not a delivery receipt. Spam placement, domain/IP authorization, real mail-client rendering and reply delivery were not tested here.

## Coverage gaps and constraints

- Dedicated MySQL unavailable: two explicit environmental skips, no claim of row-lock correctness, deadlock handling, full same-customer parallel checkout coverage, MySQL schema parity or MySQL collation behavior.
- Browser coverage is Chromium only, with synthetic products/users and local loopback hosting. No Firefox, Safari/iOS, Android hardware, reverse-proxy behavior or Nginx/TLS path was exercised.
- MP4 container validation and gallery exclusion are unit-tested; codec decode quality, malformed media fuzzing and production-size video playback/performance were not comprehensively tested.
- No production load/stress test, large-catalog benchmark, exhaustive admin-list query-count profiling or SMTP process-crash recovery proof.
- Passing browser journeys assert uncaught JavaScript pageerrors and selected HTTP failures; they do not exhaustively classify every console.error/warning or browser-extension/system message.
- Route permission/CSRF enumeration is broad; successful data mutations, multi-role combinations, every form branch and all malicious payloads cannot be inferred merely from that enumeration.
- Coverage is statement coverage. Uncovered lines below and in the HTML report are explicit evidence gaps, even in modules whose tests pass.

## Per-module line coverage

| Module | Covered / executable lines | Coverage | Missing lines |
|---|---:|---:|---|
| `app\__init__.py` | 75/78 | 96.15% | 27, 32, 81 |
| `app\admin\auth.py` | 37/39 | 94.87% | 18, 31 |
| `app\admin\management.py` | 235/253 | 92.89% | 38, 41, 42, 80, 96, 114, 128, 129, 182, 185, 213, 214, 265, 268, 270, 282, 283, 298 |
| `app\admin\reports.py` | 88/89 | 98.88% | 43 |
| `app\admin\routes.py` | 450/530 | 84.91% | 59, 61, 65, 82, 93, 96, 105, 113, 119, 120, 123, 194, 242, 252, 257, 293, 298, 337, 338, 339, 340, 394, 399, 404, 409, 424, 459, 544, 545, 551, 552, 553, 554, 556, 557, 558, 559, 560, 561, 562, 563, 596, 641, 643, 645, 658, 659, 660, 681, 686, 687, 688, 691, 692, 695, 697, 699, 714, 720, 721, 734, 739, 741, 742, 746, 748, 755, 756, 758, 761, 762, 763, 764, 765, 767, 814, 815, 945, 960, 978 |
| `app\admin\security.py` | 48/48 | 100.00% | — |
| `app\api\routes.py` | 4/4 | 100.00% | — |
| `app\auth\routes.py` | 139/150 | 92.67% | 45, 46, 53, 60, 83, 125, 126, 131, 142, 143, 144 |
| `app\cart\routes.py` | 124/150 | 82.67% | 38, 84, 89, 137, 142, 161, 163, 183, 187, 189, 194, 198, 236, 248, 250, 263, 280, 282, 283, 288, 302, 307, 313, 318, 345, 362 |
| `app\checkout\routes.py` | 89/95 | 93.68% | 36, 77, 162, 163, 164, 176 |
| `app\community.py` | 73/78 | 93.59% | 23, 24, 27, 60, 78 |
| `app\config.py` | 67/67 | 100.00% | — |
| `app\extensions.py` | 11/11 | 100.00% | — |
| `app\main\routes.py` | 39/39 | 100.00% | — |
| `app\models\__init__.py` | 11/11 | 100.00% | — |
| `app\models\admin_session.py` | 11/11 | 100.00% | — |
| `app\models\catalog.py` | 111/111 | 100.00% | — |
| `app\models\commerce.py` | 103/103 | 100.00% | — |
| `app\models\customer_email.py` | 22/22 | 100.00% | — |
| `app\models\customer_photo.py` | 17/17 | 100.00% | — |
| `app\models\engagement.py` | 42/42 | 100.00% | — |
| `app\models\operations.py` | 32/32 | 100.00% | — |
| `app\models\promotion.py` | 25/25 | 100.00% | — |
| `app\models\types.py` | 8/9 | 88.89% | 27 |
| `app\models\user.py` | 34/34 | 100.00% | — |
| `app\orders\routes.py` | 71/72 | 98.61% | 34 |
| `app\products\routes.py` | 118/130 | 90.77% | 65, 162, 163, 166, 207, 208, 229, 247, 248, 250, 251, 252 |
| `app\security\decorators.py` | 13/13 | 100.00% | — |
| `app\security\headers.py` | 20/20 | 100.00% | — |
| `app\security\rate_limit.py` | 5/5 | 100.00% | — |
| `app\security\tokens.py` | 10/11 | 90.91% | 14 |
| `app\security\validators.py` | 31/32 | 96.88% | 42 |
| `app\services\addresses.py` | 16/16 | 100.00% | — |
| `app\services\catalog.py` | 17/17 | 100.00% | — |
| `app\services\customer_email_templates.py` | 42/42 | 100.00% | — |
| `app\services\customer_emails.py` | 96/105 | 91.43% | 55, 56, 59, 60, 102, 103, 138, 139, 140 |
| `app\services\customer_photos.py` | 32/33 | 96.97% | 13 |
| `app\services\email.py` | 29/31 | 93.55% | 26, 36 |
| `app\services\guest_cart.py` | 43/49 | 87.76% | 31, 32, 51, 52, 56, 65 |
| `app\services\order_notifications.py` | 78/84 | 92.86% | 30, 47, 51, 66, 78, 79 |
| `app\services\order_status.py` | 57/60 | 95.00% | 31, 62, 69 |
| `app\services\pricing.py` | 7/7 | 100.00% | — |
| `app\services\product_interests.py` | 30/32 | 93.75% | 19, 20 |
| `app\services\product_video.py` | 46/55 | 83.64% | 12, 17, 18, 19, 20, 22, 36, 38, 42 |

## Test-harness corrections (not application fixes)

- Shared fixtures now validate the test DB location, use temporary uploads, blank delivery configuration and prohibit real SMTP/non-local sockets.
- pytest-flask's implicit test-wide request context was removed. It had cached users/catalog objects across separate requests, masking password-session behavior and causing false stale-price/variant results in exploratory tests.
- Factories return scalar snapshots outside their context so commits do not expire/reattach objects and create misleading DetachedInstanceError failures.
- An exploratory permission-matrix fixture accidentally logged in its anonymous actor. That test-only mistake was corrected before the three final seeded runs.
- Existing hidden-image test mkdir now tolerates the temporary upload directory already created by the app fixture.
- Large binary parameter cases have short IDs; otherwise Windows rejects pytest's oversized PYTEST_CURRENT_TEST environment variable. The oversized exploratory trace was replaced with a short explanation.
- The gallery browser test follows the active full-photo link/track because JavaScript intentionally replaces the original img element. This corrects a test selector, not a gallery failure.
- Pixel-limit tests assert actual rejection/no saved file rather than one exact error string: Pillow's decompression-bomb check may reject before the custom pixel check. Pillow global limits and SQLite engines are restored/disposed between tests.
- Request-flow tests use actual commits and fresh per-test schemas because application services commit internally. The optional db_session fixture rolls back uncommitted work; committed flows are isolated by schema recreation, not a misleading outer rollback.

## Files and commands

Added: TEST_INVENTORY.md, TESTING_REPORT.md, requirements-test.txt, scripts/qa_inventory.py, scripts/run_qa.py, scripts/qa_report.py, .github/workflows/qa.yml, tests/security/test_qa_audit.py, tests/integration/test_qa_commerce.py, tests/integration/test_qa_database.py, tests/integration/test_qa_email_edges.py, tests/unit/test_qa_uploads_and_config.py, tests/e2e/test_local_browser.py, and generated qa_artifacts/ evidence.

Changed testing infrastructure only: tests/conftest.py and tests/security/test_admin_workspace.py. App, migrations, Nginx and runtime dependency sources remain unchanged according to the hash snapshot.

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-test.txt
.venv/Scripts/python.exe -m scripts.run_qa browser-setup
.venv/Scripts/python.exe -m scripts.run_qa test
.venv/Scripts/python.exe -m scripts.run_qa test-unit
.venv/Scripts/python.exe -m scripts.run_qa test-integration
.venv/Scripts/python.exe -m scripts.run_qa test-security
.venv/Scripts/python.exe -m scripts.run_qa test-e2e
.venv/Scripts/python.exe -m scripts.run_qa coverage --seed 202
.venv/Scripts/python.exe -m scripts.run_qa test --seed 303
.venv/Scripts/python.exe -m scripts.run_qa test --seed 404
.venv/Scripts/python.exe -m scripts.qa_report
```

For MySQL, configure TEST_DATABASE_URL privately with a dedicated disposable local schema containing test or qa in its name. The suite creates/drops its tables. Never point it at the application database. CI defines its own disposable aurk_qa_test service; the workflow has not been pushed/executed as part of this audit.

Full per-route/model/relationship/service/migration inventory: TEST_INVENTORY.md and qa_artifacts/inventory.json. HTML coverage: qa_artifacts/coverage/index.html. Seeded JUnit XML and redacted logs are under qa_artifacts/.

## Recommended next steps

1. Obtain approval to fix QA-AUTH-002, then test customer-session revocation and admin-session behavior together.
2. Supply the isolated MySQL test schema/run the proposed CI workflow. Verify last-unit checkout, overlapping workers, migrations and email collation before claiming concurrency readiness.
3. Approve account normalization, public archive filtering and narrow upload-preview CSP fixes; rerun their failing regressions.
4. Eager-load variant dimensions, hard-disable test email automation, and agree the uploads version-control policy.
5. Choose and document the email delivery/idempotency guarantee; reconcile ambiguous SMTP outcomes rather than promising exactly-once delivery.
6. Verify the deployed upload limits separately in an authorized operations session, establish scheduled backups/restore drills, then expand cross-browser, accessibility-state and load testing.

