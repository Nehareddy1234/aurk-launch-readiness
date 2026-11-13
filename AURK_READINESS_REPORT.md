# AURK deployment readiness report

Assessment updated: 6 November 2026. Scope: prepare and test the local application, cover both supplied Instagram checklists, inspect the public website, and perform explicitly authorized read-only AWS/server diagnostics. No live files, services, resources, DNS or customer records were changed. The SSM session was terminated normally. Google account access and submission remain excluded. Business facts remain deferred by the owner.

## Decision

**Prepared for a controlled staging/deployment rehearsal; not yet signed off for unrestricted commercial launch.** Local fixes and the completed checks are listed below. The public server still runs an older release and has concrete infrastructure/recovery gaps. Confirmed business disclosures and operational evidence from the eventual live environment are still needed. These are explicit pending gates, not hidden behind a “100% ready” score.

Use `WEBSITE_DEPLOYMENT_PLAYBOOK.md` as the reusable file for other projects. Use `DEPLOYMENT.md` for this application's upgrade, backup, verification and rollback procedure. Older recovered files named TESTING_REPORT, PRODUCTION_TEST_REPORT and similar are historical records; they are not evidence that this release has been deployed.

## Current verification and deployment decision — 6 November

**NO-GO for signing off the commercial launch.** The existing website responds publicly, but the new application is not deployed and the infrastructure/operations gates below remain open. Most remaining actions are host configuration, recovery rehearsal, business facts and real provider acceptance—not missing frontend pages.

### Completed local changes in this follow-up

- Reject unknown environment names and unsafe production secret/cookie/CSRF settings. Production WSGI remains explicit; Compose uses consistent production/secure-cookie settings for every app process.
- Readiness checks the required database revision, shared Redis when configured and persistent upload permissions. Configuration preflight also flags active QA products and less than 2 GiB free disk space.
- Added migration `d4ab72cd5610` for bounded product-interest alert retries, backoff and uncertain-delivery holds. Added a reviewed single-alert retry command and read-only queue-age/failure checks.
- Reduced default database pool and Gunicorn worker counts for the observed small host; added worker recycling and graceful shutdown settings. This is a conservative starting configuration, not a capacity guarantee.
- Removed migration-on-web-start behavior in Compose. Migrations are a separate maintenance command. Repaired invalid CI YAML, constrained test dependencies to the release lock, and added Python 3.11/3.14 CI coverage configuration.
- Removed request URLs from supplied Gunicorn/Nginx access formats to reduce reset-token leakage.
- Hardened backup archives against path traversal, links, unexpected entries, tampering and insufficient restore space. Backup maintenance preserves the prior service/timer state and refuses an active legacy scheduler. Verified SQL/uploads recovery using disposable data. This does not certify the production backup process.

### New evidence

| Check | Observed result | Evidence / limitation |
| --- | --- | --- |
| Full Linux backend, Python 3.14.4 | **316 passed, 4 skipped** | `qa_artifacts/deployment-linux314-20261106.xml`; matches live Python exactly. Four tests require MySQL; four SQLAlchemy deprecation warnings. |
| Full Linux backend, Python 3.12.3 | **305 passed, 4 skipped** | `qa_artifacts/deployment-linux-20261106.xml`; earlier run before 11 additional backup archive tests. |
| Final retry/preflight/archive regressions | **23 passed, 1 skipped** | `qa_artifacts/operations-final-20261106.xml`; includes the final reviewed retry and QA-catalogue gate changes. |
| Dedicated MySQL 8.4.13 regression and synthetic restore | **30 regression checks passed; 1 restore check passed after fixture correction** | `qa_artifacts/deployment-mysql-focused-20261106.xml` records 30 passes and an initial existing-directory error in the new restore fixture. The corrected recovery test passed in `qa_artifacts/backup-mysql-20261106.xml`, verifying synthetic SQL records and upload content. The attempted full MySQL suite exceeded its 20-minute limit and is not a pass. |
| Real Linux Gunicorn on Python 3.14.4 | **Passed** | `qa_artifacts/linux-gunicorn-python314-20261106.json`; 40 public requests, concurrency 8, zero failures, p95 about 227 ms; graceful shutdown exit 0. Isolated SQLite/memory limiter, not production capacity or real Redis validation. |
| Backup archive regressions | **11 passed** | Included in the 316-test suite and final regression set; safe round trip, corrupted checksum and malformed/archive-link cases. Do not add these as unique tests again. |
| Existing public routes/assets | **46/46 passed** | `qa_artifacts/public-smoke-20261106.json`; legacy storefront/admin redirect/media-range checks, not a checkout/order mutation. |
| Supplementary live deployment checks | **Failed / partial** | `qa_artifacts/public-readiness-20261106.json`: four new routes still 404, canonical-host gap; public TLS/cookie checks passed. |
| AWS/server inventory | **Read-only completed** | `qa_artifacts/aws-readonly-20261106.json`; findings below. No deployment or resource change. |
| Docker/CI/systemd/Nginx deployment | **Pending execution** | Compose and workflow YAML parsed; CI not pushed/run, Docker image not built and service templates not installed. |

No real customer email/order/courier request was sent. Local tests block external SMTP/network effects. Counts overlap between runtimes and focused suites. A dependency advisory scan of the unchanged runtime lock on 5 November reported no known vulnerabilities; that is a point-in-time result, not security certification.

### Actual live findings and required action

| Priority | Verified observation | Required action before sign-off |
| --- | --- | --- |
| Deployment / capacity | Root EBS is 8 GiB; filesystem 84% used with about 1.1 GiB free. Host is t3.small, about 2 GiB RAM, no swap. | Plan more disk capacity and free-space alerts before installing another release/backup. The release preflight requires 2 GiB free. Review a larger volume, e.g. 20 GiB, against growth and cost; no resize performed. |
| Recovery | No snapshots observed in ap-south-2; the one listed S3 bucket contained four old deployment artifacts, with no SQL/uploads backups visible. | Create a consistent private off-server store backup, verify the download/checksum and restore it in isolation. Define retention, recovery time/data-loss targets and failure alerts. This inspection cannot rule out backups in an unexamined external system. |
| Data protection | Existing root EBS is unencrypted, delete-on-termination is enabled, instance termination protection is off. | Plan encrypted replacement/storage migration from a verified backup and review deletion/termination protection. Enabling encryption-by-default alone does not encrypt an existing volume. |
| Stable URL | Public IP is auto-assigned; no Elastic IP attached. | Choose stable addressing or a suitable frontend; coordinate DNS if allocating/associating an Elastic IP. Do not casually stop/start the instance while DNS depends on its current address. |
| Undeployed release | Live schema is `a1de49fa2387`; live Pillow is 12.3.0 while the reviewed lock has 13.0.0. Authlib is absent. | Rehearse and install the complete locked release; upgrade through b2, c3 and d4 after backup. OAuth can remain disabled. Never stamp or fresh-start the production database. |
| Shared limiter / proxy | Redis service inactive; no shared rate-limit URL or trusted-proxy count found in inspected settings. WSGI explicitly uses production. | Install/configure private Redis and the verified single proxy count, then exercise readiness and rate limits with the real services. An unset FLASK_CONFIG did not mean the live app was in debug mode. |
| New routes / canonical host | `/api/ready`, `/robots.txt`, `/sitemap.xml` and `/merchant-feed.xml` returned 404; HTTPS www remained www. | Deploy reviewed app/static/Nginx configuration; verify readiness, chosen-host redirect and public indexing settings after owner approval. No Google account is needed for these public checks. |
| Workers / alerts | Only aurk, the legacy customer-email service and its timer were installed. New notification/backup/health units were absent. No EC2 alarms were listed. | Carefully hand over from `aurk-customer-emails.timer` to the new worker, install reviewed backup/health jobs and configure a human alert destination. Prove a test failure reaches the owner. Other monitoring was not comprehensively audited. |
| Catalogue | Five active QA-marked products were found by aggregate query; a QA product was publicly reachable. | Owner reviews and archives appropriate QA listings without deleting order history. New preflight blocks sign-off while active QA markers remain. No live product was altered. |
| Email | SMTP configuration present; queues showed 9 customer and 4 owner messages submitted. MX points to Hostinger; SPF includes Hostinger; DMARC is monitoring (`p=none`). | Confirm actual sender/DKIM alignment and controlled recovery/receipt/owner-alert inbox arrival. SMTP acceptance is not delivery. No conclusion of SPF failure is justified from this record alone. |
| Business / fulfilment | Legal name/address/returns/grievance/GST facts and DTDC PIN list remain owner-deferred. | Supply confirmed facts and approve billing/returns promises; validate PIN coverage manually per order or load a confirmed allowlist. Do not invent disclosures. |
| Final acceptance | No real device/courier/full live COD acceptance or production restoration drill completed. | Owner-controlled end-to-end acceptance with approved test data, inbox and fulfilment process. |

Positive live observations: instance running with 3/3 status checks; IMDSv2 required; app/Nginx/MySQL active; security group exposes HTTP/HTTPS publicly with no public database/Redis rule, and SSH is restricted to two /32 rules plus a prefix list (prefix-list identity not independently audited). S3 public access blocking is on and default encryption is SSE-S3, but versioning is off. TLS 1.3 certificate covers aurk.in/www and expires 11 January 2027; certbot renewal timer exists and its last observed service result was successful. Secure/HttpOnly/SameSite cookies and HSTS were observed. A successful prior renewal result is not a fresh renewal dry-run.

AWS documents that [Elastic IPs are static and chargeable](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/working-with-eips.html) and [encryption-by-default affects new volumes/copies, not existing volumes](https://docs.aws.amazon.com/ebs/latest/userguide/encryption-by-default.html). Review the concrete addressing/storage plan and costs before any AWS writes.

### Recommended execution order

1. Confirm backup destination/access and recovery owner; take and restore a consistent store backup.
2. Approve the capacity, encrypted-storage and stable-address plan; protect the instance and verify DNS/HTTPS after any network change.
3. Rehearse the locked release and migrations against the restored copy, including private Redis and runtime readiness.
4. Deploy during a controlled write pause; preserve `.env`, uploads and prior release; hand over the old notification timer once.
5. Verify public routes, canonical host, catalogue, queue/backup/uptime alerts and controlled email arrival.
6. Complete owner disclosures, fulfilment and supported-device acceptance, then sign off commercial launch. Google work stays separate.

## Changes prepared in the application

- Reconciled the newer storefront/account/admin functionality with the existing login, security and checkout fixes. Preserved a recovery archive and avoided the destructive historical fresh-start workflow.
- Added safe public metadata, canonical origins, product variant structured data, crawl controls, sitemaps and a product feed. Private/search-result pages receive appropriate indexing exclusions. Added distinct descriptions for public information pages and preserved selected variants from product-feed links.
- Added an admin business/delivery settings screen without fabricating unknown legal/address/GST details. Added manual or PIN-list COD coverage handling, required verification before confirmation, tracking/AWB checks and shipment/return status controls.
- Added COD remittance records, partial settlement handling and safeguards against duplicate or excessive reconciliation. Updated customer-facing policy/receipt wording for the actual workflow.
- Strengthened authentication/session behavior and retained server-side stock/price checks. Added regression coverage for protected routes, uploads, account ownership, checkout and recovery.
- Reconciled migrations, added guards against the historical conflicting revision chain, and verified clean MySQL upgrades. Fixed MySQL UTC session handling and concurrent launch-notification queueing.
- Prepared customer/owner notification processing, stock rechecks and retry controls; added readiness/configuration checks, service/timer templates and backup/restore utilities.
- Improved the custom 404, dynamic copyright year, form busy/confirmation behavior and homepage video pause control. Verified public-page reflow and menu navigation at 320, 390, 768 and 1440 CSS pixels.
- Upgraded Pillow to 13.0.0 following the dependency advisory scan and restricted the remaining generic image decoder to JPEG/PNG/WebP. Updated static asset version URLs so browsers fetch the changed scripts/styles. The upstream version is documented in [Pillow's release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html).
- Prepared a source-only release builder with a file manifest and SHA-256 checksum; real environment files, databases, customer uploads, local QA tools and recovery archives are excluded.

## Prior verification — 5 November (retained evidence)

| Check | Result | Evidence and limits |
| --- | --- | --- |
| Unit, integration and security suite | 294 passed; 3 skipped | `qa_artifacts/launch-local.xml`; three skipped tests require MySQL row locking. Four existing SQLAlchemy Query.get deprecation warnings are non-failing maintenance items. |
| Dedicated local MySQL 8.4.13 suite | 17 passed | `qa_artifacts/launch-mysql.xml`; migrations/schema, checkout concurrency, notification locking, UTC and launch deduplication. Synthetic isolated database; no production data. |
| Chromium application/browser suite | 17 passed | `qa_artifacts/launch-browser.xml`; storefront/account/admin journeys, checkout, media, metadata, layout, mobile menu and automated accessibility checks. |
| Final homepage/accessibility regression | 5 passed | `qa_artifacts/launch-visual.xml`; four viewport screenshots, pause controls, readable content layering and automated accessibility rechecked after the final CSS/JS fix. |
| Local HTTPS recovery scenario | 1 passed | `qa_artifacts/launch-https.xml`; local TLS/password recovery test, not the public domain certificate. |
| Dependency advisory scan of release lock | No known vulnerabilities reported | `qa_artifacts/dependency-audit.json`, after Pillow upgrade; this is an advisory snapshot, not a guarantee of security. |
| Historical release archive integrity | Passed on 5 November | The 218-file package was superseded by the rebuilt 6 November release; use the current SHA-256 sidecar. |
| Dependency consistency | Passed | `python -m pip check`: no broken requirements. |
| Production host / Linux services / Docker | Not executed in the 5 November scope | See the newer 6 November inspection and Linux runtime results above. Actual Docker/service installation remains pending. |
| Real SMTP, courier and production restore | Not certified | No real customer messages, courier actions or production restore. Public HTTPS was checked on 6 November, as reported above. |

Do not add these counts as unique tests: the dedicated MySQL suite reruns selected integration scenarios. Tests block external SMTP/network effects and use disposable data. Automated accessibility checks did not report serious/critical violations in the tested routes; they do not establish full WCAG compliance or replace keyboard, screen-reader and real-device testing.

## Every item from the first Instagram post

Source: [@yatesvids checklist](https://www.instagram.com/p/DcKiRe3TvdB/). Item labels below are paraphrased. PASS means the stated local check, not a claim about the current public server.

| # | Item | AURK result / evidence |
| --- | --- | --- |
| 1 | Sideways page movement | PASS: tested routes fit 320/390/768/1440 viewports. |
| 2 | Dead destinations | PASS locally: critical journey links and public/footer destinations resolve; external inbox/courier services need live verification. |
| 3 | Small-screen navigation | PASS: menu opens and navigates to Contact in browser checks. |
| 4 | Browser icon | PRESENT: local site icon configured. |
| 5 | Meaningful document headings | PASS: page titles present; public information/product pages have descriptive titles. |
| 6 | Search summaries | FIXED: distinct public page descriptions plus product/category metadata. |
| 7 | Bottom navigation | PASS: footer destinations checked locally. |
| 8 | Missing-page recovery | FIXED: custom 404 with shop/home actions and correct status. |
| 9 | Current footer date | FIXED: copyright year comes from the current UTC year. |
| 10 | Image weight | IMPLEMENTED: WebP generation, bounded dimensions and deferred product images. Actual network performance remains a live/device measurement. |
| 11 | Working controls | PASS for covered customer/admin actions; no blanket certification of every possible state. |
| 12 | Completed-action feedback | PRESENT/IMPROVED: order/account/interest confirmations and form submission feedback. |
| 13 | Failed-action feedback | PASS in covered invalid-input, auth and commerce cases; errors do not expose server tracebacks. |
| 14 | Real content | Local customer pages reviewed; final legal identity/address details remain intentionally blank pending owner input. Production catalogue still needs owner approval. |
| 15 | Useful navigation only | PASS: no empty/hash-only anchors in the tested pages; deliberate section links retained. |
| 16 | Mobile clipping | PASS: public route reflow assertions at four widths. |
| 17 | Brand link behavior | PRESENT: header/footer branding links home. |
| 18 | Tap-to-call | PRESENT: Contact has a `tel:` link. Actual phone availability is an operational check. |
| 19 | Email action | PRESENT: `mailto:support@aurk.in`; actual inbox delivery remains unverified. |
| 20 | Phone usability | PASS for Chromium emulation and tested journeys; real iOS/Safari/Android checks remain pending. |

## Every item from the second Instagram post

Source: [@techfindsa checklist](https://www.instagram.com/p/DfShMOkPXQW/). Optional marketing/product choices are distinguished from launch gates.

| # | Item | AURK result / requirement |
| --- | --- | --- |
| 1 | Branded error destination | PASS: custom 404 and useful recovery links. |
| 2 | Early primary action | PASS: homepage CTA fits within the tested 900-pixel viewport height at all four widths. |
| 3 | Individual page metadata | IMPLEMENTED: public titles/canonicals and product overrides. Private auth/account pages are excluded from search. |
| 4 | Description snippets | FIXED for public information pages; product/category descriptions generated or editable. |
| 5 | Link-preview artwork | IMPLEMENTED: Open Graph/Twitter metadata with branded fallback and product images. Public crawler fetch/preview remains a later check. |
| 6 | Tab icon | PRESENT. |
| 7 | Crawler rules | IMPLEMENTED: `robots.txt` with staging/public behavior. Account access was not required. |
| 8 | URL inventory | IMPLEMENTED: sitemap index and page/product sitemaps. Submission excluded. |
| 9 | Image alternatives | PASS: no images missing an alt attribute in tested public pages; decorative controls appropriately use empty alternatives. Human quality review remains useful. |
| 10 | Adaptive widths | PASS at 320/390/768/1440 CSS pixels. |
| 11 | Persistent phone CTA | OPTIONAL: no blanket requirement to add one; current reachable product/cart controls remain. |
| 12 | Waiting feedback | IMPROVED: submit-once busy states and duplicate-submit protection on applicable forms. |
| 13 | Validation feedback | PASS for tested form and server validation. |
| 14 | Completion destination | PRESENT: existing order receipt/account confirmation serves the purpose. An extra generic thank-you route is unnecessary. |
| 15 | Privacy explanation | PRESENT/UPDATED: describes account, order, essential session, provider and photo behavior; factual business completion remains pending. |
| 16 | Terms | PRESENT/UPDATED: owner must confirm actual fulfilment and business details. Presence alone is not legal approval. |
| 17 | Consent banner | CONDITIONAL: no new analytics/advertising added. Review actual production embeds/cookies and applicable rules before deciding on consent UI. |
| 18 | Visitor measurement | OPTIONAL: no analytics account or tracker installed. It is not required to accept visitors/orders. |
| 19 | Genuine contact/address | PARTIAL: phone/email shown; legal/business/return address and grievance details await owner facts. This remains a business launch gate. |
| 20 | Promoted repository/service connection | OPTIONAL: no third-party promotional service connected. A reviewed versioned release and suitable monitoring matter; the named service does not. |

## Remaining gates and who supplies the evidence

| Priority | Pending item | Owner / next action |
| --- | --- | --- |
| Business launch gate | Legal name, business/return address and grievance contact | Owner supplies confirmed details later; enter Admin > Business & delivery. Do not reuse someone else's identity/address. |
| Business launch gate | Tax status and billing accuracy | Owner confirms GST registration/applicability and actual invoice requirements. The application does not fabricate GSTIN or claim a non-GST bill is a GST invoice. |
| Fulfilment gate | DTDC COD serviceability and operating process | Obtain supported PINs or use the implemented per-order manual coverage verification. Verify coverage before confirming/dispatching each order. Courier API automation is not required for this manual model. |
| Communications gate | Real mailbox, sender authentication and delivery | Verify support inbox, transactional sender/domain settings, controlled receipt/recovery/status emails and owner alert delivery. Local mocks cannot prove inbox arrival. |
| Deployment gate, writes pending | Production configuration, schema, durable storage and protected infrastructure | Follow DEPLOYMENT.md and the verified 6 November findings above. AWS inspection is complete; deployment/resource changes require a separately authorized execution step. |
| Recovery gate | Private off-server backup and successful restore | Configure actual destination/access, retention and failure alerts; restore a recent bundle in isolation and record recovery evidence. Templates alone do not satisfy this gate. |
| Operations gate | Human outage/queue/backup alerts | Choose an alert recipient/provider and prove a test failure reaches them. The health timer currently provides a check, not a complete alerting system. |
| Acceptance gate | Real-device and owner purchase/fulfilment review | Check supported devices, slow network, approved catalogue, delivery/refund promises and a controlled complete COD lifecycle. |
| Separate optional integration | Google sign-in, search/merchant submission | Explicitly deferred. Leave optional OAuth settings blank until separately configured; password/phone login can be used. |

Applicable business disclosures require owner confirmation. For the India-facing store, review the official [Consumer Protection (E-Commerce) Rules](https://consumeraffairs.gov.in/public/upload/files/E%20commerce%20rules_1732703966.pdf) against the actual business model. A cookie banner is not an automatic substitute for a data/technology inventory; see the conditional treatment in the reusable playbook.

## Operational limits worth retaining in the handover

SMTP is not an exactly-once delivery mechanism; acceptance can be uncertain after a connection or process failure. Inspect provider/inbox evidence before manual resend. Product-interest owner alerts now stop automatic retry after five failures or an uncertain delivery. Fix the provider, review the individual alert and use the documented reviewed retry command; never bulk-reset uncertain outcomes. Notification and backup timers must not duplicate older schedulers.

The default backup procedure briefly stops the app to keep SQL and uploads consistent. Retention cleanup and an external alert destination still need operational configuration. The restore script accepts trusted SQL only and should run in isolation. Local migration tests are not a production restoration drill.

The background video now has a pause control and honors reduced motion. Remaining visual polish, comprehensive assistive-technology review and real performance measurements can reveal further improvements; no accessibility, security or legal certification is claimed.

## Deliverables

- `WEBSITE_DEPLOYMENT_PLAYBOOK.md`: reusable requirements, status/owner/evidence template, launch sequence and cost worksheet.
- `AURK_READINESS_REPORT.md`: this assessment, every post item, evidence and remaining gates.
- `DEPLOYMENT.md`: AURK-specific staging, configuration, release, backup/restore and rollback procedure.
- `dist/aurk-release.zip` and `dist/aurk-release.sha256`: prepared source release, with `release-manifest.json` inside.
- `qa_artifacts/`: local test/advisory evidence; deliberately not included in the deployment archive.

The report separates “code prepared,” “locally tested,” “owner information required,” and “production verification pending” so that a future release decision can be made from evidence rather than the appearance of the website.
