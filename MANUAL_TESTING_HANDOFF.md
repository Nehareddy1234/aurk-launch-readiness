# AURK manual testing handoff

Prepared: 24 October 2026. This is a test plan, not a record of completed testing.

## Owner: complete before sharing

| Item | Value to supply |
|---|---|
| Test website URL | Pending |
| Build identifier / deployment date | Pending; local workspace has uncommitted changes |
| Testing window and contact | Pending |
| Customer A and Customer B | Dedicated test accounts; share credentials privately |
| Administrator | Dedicated test administrator; share credentials privately |
| Restricted administrator | Optional account with selected permissions |
| Email testing | Controlled inboxes and whether sending/workers are enabled |
| Bug submission location | Pending |
| Allowed environment | Staging with disposable test data recommended |

The tester needs browser access, not the source repository, database credentials, `.env`, AWS access or the owner's personal admin account. A localhost URL works only on the machine running the app. To test remotely, provide a reachable staging URL with the intended build deployed.

Before the run, the owner should apply the included migrations to the test database, confirm the app starts, and prepare the data below. Record the tested build separately: testing the deployed site does not automatically test the current local workspace.

## Test data and operating rules

- Use synthetic customers, addresses and photos, and inboxes controlled by the team. Prefix test product names and captions with `QA-`.
- Prepare a product with multiple sizes/colours, an out-of-stock variant, a last-unit variant, a coming-soon product with hidden price, and a coming-soon product with announced price. Include multiple photos, a size chart and a valid MP4.
- Give Customer A a delivered test order for customer-photo testing. Prepare enough orders/photos to test pagination, or mark those cases blocked.
- Prepare valid JPG/PNG/WEBP files, a small valid MP4, an unsupported file, and files just above the 8 MB photo / 25 MB video limits. Customer-photo tests also need a photo above 20 megapixels.
- Use separate browser profiles for Customer A, Customer B and admin. A second tab alone shares the same login session.
- Order placement reduces stock; cancellation restores it. Coordinate test inventory. Do not dispatch products, contact real customers, or record real payment receipts during this test.
- On a live store, restrict work to agreed read-only checks until the owner explicitly authorizes test orders, uploads, email sending and admin changes. Test-only stock and payment actions belong on staging.
- Capture order numbers and test record IDs for cleanup. The owner should remove/archive test data and revoke temporary accounts after the run; do not delete historical order records directly.

## Execution and evidence

Run P0 cases first. P1 cases cover secondary flows and edge cases. Run the main shopping journey on desktop Chrome and a real mobile browser; repeat critical cases on another browser where available. Record actual browser/version, device, OS and viewport. Suggested viewport checks: 375 px, 768 px and 1440 px.

For every case, record: **Pass / Fail / Blocked / Not run**, actual result, evidence link and bug ID. A known issue is still Fail when reproduced. Blocked is not Pass. Run negative checks only against your own test records.

| ID | Priority | Steps | Expected result |
|---|---|---|---|
| SHOP-01 | P0 | Open home, shop, category and product pages; follow header/footer links. | Pages and relevant images load; navigation works; no broken layout or error page. |
| SHOP-02 | P1 | Search for an existing product, then nonsense text; use available category/sort controls and clear them. | Results match controls; price ordering is correct; empty results are understandable. |
| SHOP-03 | P0 | Select different size/colour combinations, including sold-out variants; add a valid selection. | Selected variant and price are clear; unavailable stock cannot be purchased; bag receives the correct variant. |
| SHOP-04 | P1 | Use product thumbnails, full-size image/size chart and mobile swipe; play/pause the product video. | Images remain usable and readable; controls work; video plays on tested browsers. |
| SHOP-05 | P1 | Open both coming-soon products and use Notify me where shown. | Hidden price stays hidden across home/shop/detail; announced price is visible; coming-soon item cannot be bought; acknowledgement is clear. Automatic launch emails require separate verification. |
| AUTH-01 | P0 | Register a fresh test customer, sign in, sign out, then try wrong credentials. | Valid flow works; wrong login is rejected without exposing account existence. |
| AUTH-02 | P1 | Submit missing fields, malformed email, password under 12 characters and duplicate signup; test mixed-case email signup/login. | Invalid submissions show useful errors; no duplicate account; case-normalized login works. Mixed-case login is a known failing regression on SQLite. |
| AUTH-03 | P0 | Request password recovery using a controlled inbox; follow the link, reset, try old/new passwords, then reuse the link. | Email arrives when configured; new password works; old password and reused link fail. Mark email-dependent steps blocked if delivery is unavailable. |
| AUTH-04 | P0 | Sign Customer A into two independent browser profiles; reset its password in one; refresh Account in the other. | Previous authenticated session is revoked. Known local defect: the other customer session currently remains active. |
| BAG-01 | P0 | As guest, add items from cards/detail; change quantity, remove an item, reload. | Correct variants, totals and quantities persist; removal works; empty bag is usable. |
| BAG-02 | P0 | Put items in an account bag; sign out; create a guest bag; sign in during checkout. | Guest and account bags merge without losing items or exceeding available stock; checkout destination is preserved. |
| BAG-03 | P1 | Try zero/negative/excessive quantities through normal UI; reduce stock in admin while an item remains in the bag. | Invalid quantities are rejected; stale availability is rechecked and clearly reported. |
| ORDER-01 | P0 | Complete checkout with a valid Indian test address and COD. Record order number, totals and stock before/after. | One Pending order is created, totals match the bag, stock decreases correctly, and success/history show the same order. No online payment is requested. |
| ORDER-02 | P0 | Try incomplete address, invalid phone/postcode, empty bag and unavailable stock; correct errors and resubmit. | Invalid checkout creates no order and does not consume stock; valid retry works. |
| ORDER-03 | P0 | Double-click submit, then refresh/back after order success; inspect history and stock. | No unintended duplicate order or stock deduction; any failure has recorded reproduction steps. |
| ORDER-04 | P0 | Put the final unit in two customers' bags; submit checkouts close together from separate profiles. | At most one purchase succeeds; no negative stock. A manual run is a spot check, not proof of concurrency correctness. |
| ACCT-01 | P0 | Open Account/history/detail; update name, phone and saved address; revisit checkout. | Counts and own orders are correct; valid edits persist; checkout uses saved address; old order address snapshots remain unchanged; email is read-only. |
| ACCT-02 | P0 | While signed in as B, open A's recorded order URL; repeat logged out. | B cannot see A's order; anonymous users must authenticate. No customer data leaks. |
| ADMIN-01 | P0 | Open an admin page anonymously and as a customer; then use the dedicated admin login and logout. | Unauthorized users cannot enter; admin login works; protected pages remain inaccessible after logout/refresh. |
| ADMIN-02 | P1 | With a restricted admin, try an allowed action and a disallowed page/action URL supplied by the owner. | Server permits only granted actions; hiding a menu is not the only restriction. Block if no restricted account is supplied. |
| ADMIN-03 | P0 | Create/edit a QA category and product; add sizes/colours/SKUs and stock; inspect storefront and inventory. | Changes persist; SKUs/stock correspond to the correct variants; storefront reflects intended active products. |
| ADMIN-04 | P1 | Upload valid photos/video; inspect previews; try unsupported, oversized and more than ten total media files. | Supported uploads display correctly; invalid uploads show errors; limits hold without partial unwanted records. Known CSP defect can block local previews. |
| ADMIN-05 | P0 | Archive a QA product; search/browse it and open its saved public URL; revisit an old order containing it. | Product disappears from public sale; direct page is unavailable; historical order details remain intact. Inconsistent archive/active flags need developer-assisted reproduction. |
| ADMIN-06 | P0 | Move an order Pending -> Confirmed -> Shipped -> Delivered, inspecting customer history after each step. | Correct status appears to the customer; invalid backward/skipped transitions are rejected. |
| ADMIN-07 | P0 | Cancel separate Pending and Confirmed test orders with a reason; retry cancellation. Try cancelling a Shipped order. | Pre-shipment cancellation restores stock once; repeated cancellation does not restore twice; shipped cancellation is unavailable. |
| ADMIN-08 | P0 | On staging, try recording COD before delivery; then deliver, acknowledge receipt and repeat the action. | Early receipt is rejected; acknowledged delivered receipt is recorded once; totals do not double. This is a simulated test receipt only. |
| ADMIN-09 | P1 | Review customer search/detail, inventory edits, analytics, coupon configuration and review moderation using QA records. | Pages and permitted actions work; numbers reconcile with the test records and selected filters. Storefront coupon redemption/customer review submission are outside current functionality. |
| PHOTO-01 | P1 | As A, upload a valid customer photo for its delivered item with consent; check logged-out gallery and B's access to its image URL. | Submission is pending and private; only owner/moderator can access unapproved photo. |
| PHOTO-02 | P1 | Approve a photo in admin; view publicly; withdraw as owner; attempt to republish it. Repeat with a rejected photo. | Approved photo is public; withdrawn photo becomes private and cannot be republished; rejected photo stays private. |
| PHOTO-03 | P1 | Try uploading without consent, for undelivered items, above the file/pixel limits and a sixth submission for the same item. | Invalid submissions are rejected; customer cannot submit against another customer's purchase. |
| EMAIL-01 | P1 | If enabled, register a new customer, place an order and confirm it; wait for the configured worker interval. | Controlled inbox receives welcome/order-received/order-confirmed messages with correct test data, branding and working authenticated links; order-email replies reach support. Record latency/spam placement. |
| EMAIL-02 | P1 | Ask owner to exercise email failure/retry on staging; inspect saved order/account and eventual messages. | Sending failure does not erase signup/order; retries follow configured policy. Ambiguous SMTP timeouts can cause duplicates; manual inbox observation cannot establish exactly-once delivery. |
| UI-01 | P0 | Repeat browse -> variant -> bag -> login -> checkout -> history on phone and desktop. Open menus/dialogs and rotate phone. | No horizontal overflow, hidden actions, overlapping text or unusable controls; keyboard does not obstruct required fields. |
| UI-02 | P1 | Navigate with keyboard, inspect focus, dismiss dialogs, zoom to 200%, and enable reduced motion. | Focus is visible/logical; dialogs and forms remain usable; text/errors readable; reduced-motion preference is respected. |
| UI-03 | P1 | Open an invalid URL; use slow network/reload during navigation; inspect Contact, Shipping, Returns, Refund, Privacy and Terms. | Friendly error/empty/loading states; no traceback; policy/contact links and published text are consistent. |

## Known issues and scope limits

Source: `TESTING_REPORT.md` (19 October 2026). The 24 October focused check reproduced AUTH-001, AUTH-002, CONFIG-001 and SECURITY-001. The full audit was not rerun during this handoff.

| Audit ID | Known finding / tester treatment |
|---|---|
| QA-AUTH-002 | High: other customer session remains active after password reset. Recheck AUTH-04 first. |
| QA-AUTH-001 | Mixed-case registration/login mismatch reproduced on SQLite; MySQL collation may mask it. Record environment. |
| QA-CATALOG-001 | Archived + active flags can expose a product. Normal archive also disables it; inconsistent flags require prepared data. |
| QA-UI-001 | CSP blocks admin blob image previews; this alone does not prove upload saving fails. |
| QA-PERF-001 | Per-product size/colour queries grow with catalogue size. Record perceived slowness; developer profiling is separate. |
| QA-EMAIL-001 | Lost SMTP acknowledgement can lead to duplicate email on retry. |
| QA-CONFIG-001 | Testing configuration can inherit enabled email automation; developer verification, not a browser case. |
| QA-SECURITY-001 | Product photos are allowed in Git; policy decision pending. Customer photos are ignored. |
| QA-DB-001 | Fresh SQLite migrations differ from model foreign-key types; MySQL parity is unverified. Developer verification. |

COD is the only checkout payment method. Automated courier tracking, automatic confirmation phone calls, online refunds and storefront coupon redemption/customer review submission are not established features. Owner alerts/WhatsApp need external configuration. Do not treat an unavailable external integration as verified. Confirm Notify me email behavior with the owner for the exact deployed build; an acknowledgement alone does not demonstrate later delivery.

`PRODUCTION_TEST_REPORT.md` records historical public smoke checks, not current deployment status. Production URL/build, worker schedules, backups/restores, MySQL concurrency and server upload limits need separate owner verification. This manual plan does not replace those checks or a full accessibility/security/load audit.

## Bug report template

```text
Title:
Test case ID:
Environment URL and build:
Date/time and timezone:
Browser/version, OS/device, viewport:
Role/account alias (no passwords):
Preconditions and test record IDs:
Steps to reproduce:
1.
2.
Expected result:
Actual result:
Reproduction rate:
Screenshot/video link (redact private data):
Severity and reason:
Known audit issue ID, if applicable:
```

Severity guide: Critical = broad outage or unauthorized access to sensitive data; High = broken core purchase/admin flow, incorrect stock/payment behavior or session-security failure; Medium = feature failure with a workaround; Low = cosmetic/text issue. Report credentials or sensitive evidence privately.

## Tester completion report

```text
Environment/build:
Testing dates:
Devices/browsers covered:
Cases: total __ / passed __ / failed __ / blocked __ / not run __
Critical/high open bugs:
Other bug IDs:
Known issues reproduced / no longer reproduced:
Untested areas and blockers:
Recommendation: Ready for agreed scope / Retest required / Not ready
Evidence location:
```

Recommended release gate: every P0 case passes on the agreed build, no unresolved critical/high defects, and blocked cases explicitly accepted by the owner. Record remaining defects and browser/environment limits rather than marking the whole project passed.
