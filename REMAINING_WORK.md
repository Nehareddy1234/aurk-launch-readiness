# AURK remaining work before launch

Updated 13 November 2026. This is the current handover checklist for the client and technical team. The last live AWS inspection was on 6 November; server findings below must be rechecked before changes. No fresh live-server verification is implied by this document date.

## Current decision

**The updated source is prepared and tested locally, but it has not been deployed or approved for unrestricted commercial launch.** The existing public website runs an older release. The client has set a **zero additional AWS spending budget**. New instances, additional storage, snapshots, paid monitoring and other chargeable resources must not be created without a revised budget approval. Existing AWS charges are not made free by this restriction.

## Completed work

- Reconciled the storefront, account, admin, checkout and COD functionality; added business/delivery settings, search metadata, sitemap/feed support and responsive/accessibility improvements.
- Added migration safeguards, shared-limiter/readiness checks, bounded notification retries, queue monitoring, backup/restore utilities and deployment/rollback instructions.
- Prepared host disk checks and an operational failure-email service using the existing SMTP configuration. These are local templates only; they are not installed or configured on the server.
- Ran local backend/security/integration, browser and targeted MySQL checks. Live read-only checks found no broken references across 42 database relationships, no checked stock/order/payment inconsistencies, and all 55 referenced media files present.
- Prepared a source-only release process that excludes credentials, databases and customer uploads. The new Git repository contains the project source, tests, migrations, deployment templates and handover documents.

Historical evidence: 316 Linux backend tests passed with four MySQL-only skips; 30 focused MySQL regressions passed; a synthetic MySQL/uploads restore passed after its fixture was corrected; 17 Chromium journey tests and 46 public route/asset checks passed. The full historical MySQL run timed out and is not a pass. Tests overlap and should not be added together as unique coverage. See the current verification record below for the latest source check.

## Technical checklist

| Pending work | Next action and completion evidence | Owner | Constraint or status |
| --- | --- | --- | --- |
| Refresh AWS access and inventory | Sign in to the intended AWS account; verify instance, disk, runtime, schema and service state again. | Client + technical team | AWS session expired on 7 November. Do not assume the old session still works. |
| Confirm a maintenance window | Agree an IST window, maximum interruption and rollback contact before pausing writes, restarting services or changing DNS. | Client | Not supplied. |
| Prove production recovery | Back up the real SQL database and persistent uploads to a private off-server destination; verify checksum and restore in isolation. Preserve configuration securely. | Technical team | No recoverable store backup demonstrated in inspected AWS resources. An existing no-extra-cost destination/access plan is needed, or the budget must change. A local archive on the same server is insufficient. |
| Resolve disk headroom | Recheck storage usage and identify genuinely disposable files without deleting orders, uploads or recovery data. Meet the configured 2 GiB free-space reserve. | Technical team | Last observed: 8 GiB volume, 84% used, about 1.1 GiB free. No cleanup candidate or safe free-space recovery has been proven. Paid expansion is on hold. |
| Protect storage and addressing | Address unencrypted storage, delete-on-termination, disabled termination protection and the auto-assigned public IP through an approved plan. | Technical team + client | Last observed settings remain unremediated. Encryption replacement/snapshots and stable-IP changes may incur cost. Do not stop/start casually while DNS depends on the current IP. |
| Isolated AWS transactional tests | Test registration, checkout, last-item concurrency, duplicate submissions, cancellation/restocking, COD reconciliation and worker retries with synthetic data. Disable real provider actions. | Technical team | No full AWS-hosted test suite or isolated staging environment was created. New paid staging is on hold; prior local tests remain valid only for their stated scope. |
| Configure runtime dependencies | Install/configure private Redis and trusted proxy settings; validate the actual host-service configuration and locked dependencies. | Technical team | Redis/shared limiter was not verified live. Preparation can use the existing host only after capacity/recovery/maintenance gates are met. |
| Deploy the new release | Preserve `.env`, persistent uploads and the prior release. Rehearse and apply migrations from the observed `a1de49fa2387` through `b2ef50ab3498`, `c3fa61bc4509` and `d4ab72cd5610`. Install app/static/Nginx changes once. | Technical team | Not deployed. Never reset, seed, stamp or run test fixtures against the live database. |
| Verify public endpoints | Verify HTTPS and renewal, canonical-host redirect, `/api/ready`, `/robots.txt`, `/sitemap.xml`, `/merchant-feed.xml`, private-page access and media. | Technical team | The four new URLs returned 404; HTTPS www did not redirect to the chosen canonical host. Current live Nginx syntax passed, but the new template has not been installed. |
| Hand over scheduled jobs | Replace `aurk-customer-emails.timer` with the reviewed notification scheduler without overlap. Configure backup and health jobs; prove restart behavior. | Technical team | New notification/backup/health/alert units are not installed. Review the daily backup downtime before enabling its timer. |
| Activate alerts and monitoring | Confirm a monitored inbox and permission for controlled test emails. Install the failure-alert template, verify one-hour suppression, and prove a failure reaches a human. Add an approved external uptime check for whole-host/network loss. | Client + technical team | Recipient/send permission not supplied. Existing-host email alerts depend on that host and SMTP being alive; they do not replace independent monitoring. No paid monitor may be added under the current budget. |
| Final operational acceptance | Complete the approved live COD lifecycle and recovery/email/device checks, record results and client sign-off. | Client + technical team | Not complete. A passing read-only data audit cannot prove all write workflows or inbox delivery. |

## Client information still required

- [ ] Legal business name, business address and return address.
- [ ] Grievance-contact name and email; confirm monitored customer support.
- [ ] GST registration status and GSTIN if applicable; confirm invoice/receipt wording.
- [ ] Verified DTDC COD PIN coverage, or an approved per-order manual coverage process.
- [ ] Confirm dispatch times, shipping charges, tracking, failed delivery/RTO, cancellation and return/refund promises.
- [ ] Review the five active QA-marked products and approve archiving appropriate test listings while preserving order history. Confirm genuine products, stock and prices.
- [ ] Alert and controlled test inboxes, with explicit permission to send test messages.
- [ ] Maintenance window and operational owners. Supply account access through secure sign-in; do not commit passwords or keys.

## Verification still needed with real providers and devices

- [ ] Actual inbox arrival for registration/recovery, receipts/status messages and owner alerts; verify sender-domain authentication. SMTP acceptance alone is not proof of delivery.
- [ ] Approved test order through confirmation, shipment/tracking, delivery and COD reconciliation, plus cancellation/restocking and the agreed return flow.
- [ ] Supported real phones/browsers, slow connectivity and owner fulfilment review.
- [ ] Successful production-backup restore and an acknowledged outage/queue/backup alert.
- [ ] Validate the selected production hosting route. Docker builds and remote CI execution have not been certified; Docker is optional for the existing host-service route.

## Google and optional integrations

Google account access and submission remain separately deferred. After the site is ready, choose the correct Google account, verify Search Console and submit the sitemap if desired. Google submission is not required for direct visitors and does not guarantee indexing. Google sign-in, Merchant Center, analytics, advertising and online payments are separate choices; COD does not require an online payment gateway.

## Current source verification

**13 November 2026:** the full Linux backend/security/integration suite passed with **330 passed, 5 skipped**, on the isolated Python 3.14 environment. The skipped cases need MySQL/client tools. Four existing SQLAlchemy Query.get deprecation warnings remain maintenance items. Focused Windows alert/archive/runtime checks passed with **36 passed, 1 MySQL-only skip** outside the restricted sandbox. An earlier sandbox run hit file-rename permission errors; it was superseded by this successful focused run. No real email or production data was used. Browser and live AWS checks were not rerun on 13 November. See [verification notes](docs/VERIFICATION_20261113.md).

## Release order

1. Restore AWS access and confirm maintenance, inbox and cost constraints.
2. Secure and prove recovery; resolve safe storage headroom and infrastructure protection.
3. Rehearse the new release and transactional tests in an isolated environment within the approved budget.
4. Deploy during the approved window, preserving rollback and data.
5. Verify endpoints, jobs, human alerts, email delivery and the complete COD workflow.
6. Complete owner disclosures and supported-device acceptance, then record launch approval.

The client may supply business information in parallel. **Do not mark launch approved while an applicable recovery, security, business or acceptance gate remains unresolved.**

## Related documents

- [Detailed readiness assessment](AURK_READINESS_REPORT.md) - historical findings and both supplied Instagram checklists.
- [AWS backend and data audit](AWS_BACKEND_DATA_TEST_REPORT.md) - read-only live results and their limits.
- [Deployment runbook](DEPLOYMENT.md) - configuration, migration, backup and rollback procedure.
- [Reusable deployment playbook](WEBSITE_DEPLOYMENT_PLAYBOOK.md) - checklist for other projects.
- [Technical execution proposal](TECHNICAL_EXECUTION_PLAN.md) - original paid-resource proposal; its cost-bearing steps are superseded by the zero-additional-spend constraint above.
- [Client handover PDF dated 6 November](docs/AURK_Client_Launch_Readiness_Handover_20261106.pdf) - historical client summary. This checklist takes precedence for current status and budget.
