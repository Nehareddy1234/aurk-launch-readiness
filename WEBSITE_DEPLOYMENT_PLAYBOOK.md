# Reusable website deployment checklist and launch report

Template version: 6 November 2026. Copy this file into any project and replace the project record below. It applies to static sites, web applications and online stores. Requirements change with location, audience, data and business model; review conditional items for each project.

## Project record — fill this in for each release

| Field | Project value |
| --- | --- |
| Project / release / source commit | TO COMPLETE |
| Owner / technical maintainer / support contact | TO COMPLETE |
| Public URL / staging URL | TO COMPLETE |
| Site type | Static / application / shop / other |
| Audience and operating jurisdictions | TO COMPLETE |
| Data collected and external providers | TO COMPLETE |
| Hosting, runtime, database and persistent storage | TO COMPLETE |
| Release date and maintenance window | TO COMPLETE |
| Maximum acceptable data loss / recovery time | TO COMPLETE |
| Reviewer / decision / evidence location | TO COMPLETE |

Use these status values: **PASS** (verified evidence), **FAIL** (does not meet the criterion), **PENDING** (not checked or awaiting input), **N/A** (does not apply, with reason). Never treat “implemented,” “installed,” or “looks fine” as proof of a production check. Assign an owner and evidence to every applicable launch gate.

Priority labels: **Gate** = necessary before exposing the affected feature to real users; **Conditional gate** = necessary when the stated condition applies; **Recommended** = useful quality or resilience measure; **Optional** = deliberate product choice. A gate is an engineering release rule here, not a claim that every jurisdiction legally mandates it.

## What you actually need

A basic public site needs deployable content, a host that serves it, a reachable URL, HTTPS for safe public use, correct configuration, and working content/navigation. A host-provided address can work; a purchased custom domain is a branding choice. Dynamic applications also need a production runtime, secret management, reliable data storage where used, and operational ownership. Shops add accurate product/pricing information, a working order and fulfilment process, customer support and applicable business disclosures.

You do not inherently need AWS, Google submission, a particular repository host, paid SSL, a payment gateway for COD, analytics, a sticky mobile button, or a promotional monitoring platform. You do need to assess the capabilities those services would provide. Search visibility is separate from URL availability; submission is not a guarantee of indexing or sales.

| Capability | Static informational site | Account/application site | Online shop |
| --- | --- | --- | --- |
| Hosting, HTTPS, working public URL | Gate | Gate | Gate |
| Production application server | Only if server logic exists | Gate | Gate for server-driven orders |
| Database | Only when needed | If persistent records exist | Usually needed for products/orders |
| Authentication and authorization | If restricted areas exist | Gate for accounts/private data | Gate for admin and customer accounts |
| Transactional email | If forms promise email | If recovery/notifications depend on it | If receipts/status/support depend on it |
| Payment provider | N/A unless taking payments | If taking online payments | Only for selected online payment methods; COD can operate without one |
| Shipping and returns workflow | N/A | If physical goods involved | Gate for physical goods |
| Analytics and advertising | Optional | Optional | Optional |
| Cookie consent interface | Depends on actual technologies and applicable rules | Same | Same |

## 1. Product, content and user journeys

For each row, record `status | owner | evidence/date` in your project copy.

| ID | Priority | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- | --- |
| C01 | Gate | The site's purpose and primary action are clear; critical content is visible without broken loading states. | PENDING |
| C02 | Gate | All intended routes, navigation, footer, logo links and buttons work; no unexplained placeholders, dead links or demo data. | PENDING |
| C03 | Gate | Forms validate on the server, explain field errors, show progress and confirm success; duplicate submissions do not duplicate important actions. | PENDING |
| C04 | Gate | Empty, loading, unavailable, permission-denied, 404 and failure states offer a useful next step without stack traces. | PENDING |
| C05 | Gate | Prices, availability, service claims, contact methods and policy content match actual operations. | PENDING |
| C06 | Recommended | Page titles, descriptions, favicon and sharing image are meaningful; footer year is maintained. | PENDING |
| C07 | Conditional gate | All languages, dates, time zones, currencies, tax and rounding rules required by the audience work correctly. | PENDING |
| C08 | Optional | Sticky CTAs, thank-you routes, chat widgets and animation are added only when useful; an accessible confirmation can be inline or on a receipt page. | PENDING |

## 2. Mobile, accessibility and performance

| ID | Priority | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- | --- |
| U01 | Gate | Essential journeys work at narrow widths and enlarged text; no unintended horizontal scrolling or clipped controls. Check portrait/landscape and a real phone. | PENDING |
| U02 | Gate | Mobile menu opens/closes, exposes navigation, has an accessible name/state and can be operated without a mouse. | PENDING |
| U03 | Gate | Keyboard navigation, focus visibility, labels, error associations and dialog focus behavior work for essential tasks. | PENDING |
| U04 | Gate | Informative images have useful alternatives; decorative images use empty alt text; text has readable contrast and controls are usable by touch. | PENDING |
| U05 | Conditional gate | Motion can be paused where required, reduced-motion preferences are respected, and meaningful audio/video has appropriate alternatives. | PENDING |
| U06 | Recommended | Images have suitable dimensions/formats; noncritical images are deferred; critical hero content is not unnecessarily delayed. Videos do not dominate slow connections. | PENDING |
| U07 | Gate | No critical JavaScript errors, missing assets or mixed-content failures. Critical flows work on the browsers the project supports. | PENDING |
| U08 | Recommended | Measure loading, responsiveness and visual stability on representative mobile hardware/network conditions; record a budget and regressions. | PENDING |

Responsive screenshots and automated accessibility tools cover only part of accessibility. W3C's [reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) explains narrow/zoomed layouts and exceptions. Its [pause, stop or hide guidance](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) covers automatically moving content. [MDN's lazy-loading guide](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/Lazy_loading) explains deferring noncritical resources. Do not claim WCAG compliance from a single automated scan.

## 3. Security and privacy

| ID | Priority | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- | --- |
| S01 | Gate | Production debug is off. Secrets are unique, private, absent from source/releases/logs, and access is limited to authorized operators. | PENDING |
| S02 | Gate | Supported dependencies are locked and audited; findings are fixed or have a documented justified disposition. Include OS/container updates. | PENDING |
| S03 | Conditional gate | Accounts use safe password storage, rate limiting, secure sessions and recovery; password changes invalidate old sessions where appropriate. Privileged access is protected. | PENDING |
| S04 | Conditional gate | Each protected operation enforces server-side ownership/role checks, including guessed IDs, downloads and admin endpoints. | PENDING |
| S05 | Conditional gate | State-changing requests have appropriate CSRF protection; user inputs cannot inject SQL, script, shell commands or unsafe redirect destinations. | PENDING |
| S06 | Conditional gate | Uploads have size/type/content checks, safe filenames/storage and restricted execution; only approved content is publicly exposed. | PENDING |
| S07 | Gate | HTTPS works; cookies and proxy trust match the architecture; origin/host handling and security headers are reviewed. Private services are not public. | PENDING |
| S08 | Conditional gate | Collection, retention, sharing, deletion and access to personal data are documented and implemented as applicable. Policy text reflects actual behavior. | PENDING |
| S09 | Conditional gate | Inventory cookies, local storage, SDKs, embedded media and trackers. Implement consent/preferences and blocking before consent where applicable. | PENDING |
| S10 | Gate | Error and audit logs support investigation without exposing passwords, tokens or unnecessary personal data; incident and access-revocation owners are known. | PENDING |

Use [OWASP ASVS](https://asvs.owasp.org/) to scale verification to the application's risk. A dependency scan finds known advisories; it is not a penetration test. Consent requirements depend on technology, purpose and jurisdiction. For example, the UK's current [ICO exceptions guidance](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/what-are-the-exceptions/) distinguishes exempt uses and their conditions. Do not add a decorative “Accept” banner while tracking starts anyway, or assume a banner is universally required for an essential-session-only site.

## 4. Infrastructure and release engineering

| ID | Priority | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- | --- |
| D01 | Gate | Hosting supports the runtime/build and required storage, background jobs and resource limits; billing and renewal owners are recorded. | PENDING |
| D02 | Conditional gate | Custom-domain DNS resolves correctly; intended hostname redirects consistently; HTTPS certificates cover all served names and renew automatically. | PENDING |
| D03 | Gate | A clean build/install is reproducible from a reviewed release; artifacts contain no environment files, credentials, database dumps or customer data. | PENDING |
| D04 | Gate | Development, test, staging and production configuration/data are separated. Staging is access-controlled, cannot contact real customers, and is excluded from indexing. | PENDING |
| D05 | Conditional gate | Database migrations are versioned and tested on a representative restored copy; concurrent writes and transactional failures are handled correctly. | PENDING |
| D06 | Conditional gate | Uploads and other user data survive redeploy/restart; storage permissions, quotas and disk alerts are correct. | PENDING |
| D07 | Gate | Production process restarts after failure/reboot, exposes health/readiness checks and uses an appropriate production server or managed platform. | PENDING |
| D08 | Conditional gate | Jobs have ownership, timeouts, retries and duplicate protection; queues are monitored and cron schedules do not overlap unexpectedly. | PENDING |
| D09 | Gate | Previous release, configuration history and rollback procedure are available; data compatibility is explicitly assessed. | PENDING |
| D10 | Recommended | CI runs suitable tests and validates release artifacts; protected deployment access and approval responsibilities fit the team. | PENDING |

A dedicated production server or managed runtime is needed for a Flask application; its development server is unsuitable for production. See [Flask's deployment documentation](https://flask.palletsprojects.com/en/stable/deploying/). A static site does not need a Flask server merely to satisfy this checklist.

## 5. Data recovery, monitoring and support

| ID | Priority | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- | --- |
| O01 | Conditional gate | Persistent business data has encrypted/private backups away from the primary failure domain, with retention and backup-failure alerts. | PENDING |
| O02 | Conditional gate | A recent backup has been restored in isolation; sample data/files and the application work. Record recovery time and achievable data loss. | PENDING |
| O03 | Gate | A human receives and acknowledges a test outage alert. Monitor availability, errors, capacity and critical dependency failures. | PENDING |
| O04 | Conditional gate | Transactional email sender authentication and controlled-inbox arrival are verified. Bounce/failure handling and retry ownership are defined. | PENDING |
| O05 | Gate | Support channel is monitored; refund/privacy/security escalation and out-of-hours responsibility are assigned as appropriate. | PENDING |
| O06 | Recommended | Review failed jobs, backups, stock, dependencies, certificates/domain renewal and bills on a documented schedule. | PENDING |
| O07 | Conditional gate | Providers' limits, outages and cancellation/export paths are understood; failure does not silently lose important user actions. | PENDING |

## Additional verification worksheet for any deployment

Use these checks where the relevant component exists. Record observed production values separately from local test results; a passing homepage is insufficient evidence for the backend.

| Check | What to inspect or exercise | Required evidence / result |
| --- | --- | --- |
| Exact runtime and dependency versions | Compare local lock, deployed packages and OS/runtime support; test the actual production Python/Node/etc. version. | Version inventory, install consistency and relevant tests. |
| Startup and shutdown | Start the real production server with isolated data; exercise concurrent reads and graceful termination. | Exit status, failed requests and test limits. A small smoke load is not capacity certification. |
| Configuration failures | Invalid environment name, missing secret, insecure production cookies, debug/CSRF settings. | Unsafe startup is rejected; secrets never appear in output. |
| Readiness vs liveness | Disconnect DB/cache, use an old schema, remove the upload mount. | Readiness fails safely; process liveness is separate; no internal details exposed. |
| Database behavior | Clean/upgrade migrations, constraint violations, transaction rollback, simultaneous stock claims and overlapping workers. | Tests on the same database family, plus rehearsal on a recent restored copy. |
| Jobs and email | Retry count/backoff, duplicate delivery risk, uncertain acceptance, stale queues and scheduler ownership. | Bounded retry policy, reviewed recovery command, one scheduler, human failure alert and controlled inbox evidence. |
| Backup and recovery | SQL plus persistent files, checksums, off-server encryption/access, archive paths/links, retention and recovery time. | Actual isolated restore; test sample records/files. Synthetic tests do not prove production recovery. |
| Storage and resilience | Free disk/inodes, log growth, release/backup working space, encryption, deletion protection and stable addressing. | Explicit headroom threshold and alert; review destructive defaults and IP/DNS changes. |
| Deployment execution | One migration step, consistent worker environment, private DB/cache, persistent uploads, certificate renewal. | Staging deployment and public smoke evidence; syntax validation alone is insufficient. |
| Release hygiene | Allowlisted source package, SHA-256/manifest, no customer data or secrets; no active QA/demo catalogue. | Reproducible build instructions, verified archive and reviewed live content. |
| Logs and monitoring | Reset tokens/query strings, PII, retention/access, uptime, disk, queue and backup failure. | Redaction plus a test alert acknowledged by its recipient. |
| Cost and ownership | Static IP, storage/snapshots, backup retention, messaging, bandwidth and renewal. | Agreed spending limits and an operational owner; never infer approval to create billable resources. |

A test that timed out, was skipped, mocked an external dependency or ran on another database must retain that limitation in the report. Keep blockers separate from optional features and distinguish source changes from deployed changes.

## 6. Extra gates for commerce

| ID | Acceptance criterion | Status / owner / evidence |
| --- | --- | --- |
| E01 | Product variants, stock, images, total price, shipping and applicable tax are accurate. Server recalculates totals; overselling and repeat checkout are tested. | PENDING |
| E02 | Selected payment method works end to end. Online payments require verified provider configuration, signed callbacks, replay/duplicate handling and refund reconciliation. COD requires receipt/remittance reconciliation instead. | PENDING |
| E03 | Serviceable regions/PIN codes, courier handoff, tracking, dispatch timing, failed delivery/RTO and damaged/returned goods have a working process. | PENDING |
| E04 | Order states, cancellations and returns preserve stock and accounting correctly; receipts/bills describe actual tax status. | PENDING |
| E05 | Applicable business identity, address, grievance/support contacts, shipping, return/refund and terms disclosures are accurate and reachable. | PENDING |
| E06 | Owner can fulfil a controlled test order, answer support, process cancellation/return and reconcile payment without developer intervention. | PENDING |

For an India-facing e-commerce business, review the applicable provisions of the official [Consumer Protection (E-Commerce) Rules](https://consumeraffairs.gov.in/public/upload/files/E%20commerce%20rules_1732703966.pdf), including business/contact disclosures and grievance handling. Business model, tax registration and current legal obligations need factual owner/professional confirmation. Never invent a registration number or copy another store's address/policies to fill a blank.

## 7. Search and discoverability — separate from deployment

Check meaningful public titles/descriptions, canonical URLs, relevant content, crawlable navigation, robots rules, an accurate sitemap and appropriate structured data. Keep admin, account, cart and test pages out of search. `noindex` is not authorization. Sharing metadata helps social previews; it does not make a broken page usable.

Search-console verification, sitemap submission, merchant listings, advertising, business profiles and analytics are follow-up integrations selected for the project. A public site can accept direct visitors before any of those are configured. Product feeds need actual current products, prices, stock and valid image URLs. Never promise an indexing date or search ranking.

## 8. Evidence and sign-off

Minimum evidence set: release identifier/checksum; relevant automated test output; manual journey results; supported-browser/device list; dependency/security review; production configuration check; migration/restore rehearsal; public smoke results; controlled email/payment or COD evidence; monitoring test; owner-approved disclosures. Redact personal data and secrets from all shared evidence.

| Gate | Decision | Evidence / owner |
| --- | --- | --- |
| Source, dependencies and package verified | PENDING | |
| All critical journeys pass | PENDING | |
| Applicable security/privacy/business gates pass | PENDING | |
| Data recovery and rollback proven | PENDING | |
| Production runtime, HTTPS, jobs and alerts verified | PENDING | |
| Support/fulfilment owner accepts handover | PENDING | |
| Final decision and date | GO / NO-GO / LIMITED PREVIEW | |

Do not mark GO while an applicable gate is unknown. A limited preview can be appropriate if access and features are deliberately restricted. Record deferred optional improvements separately from unresolved blockers.

### Defect and exception register

| ID | Problem / affected users | Severity | Owner | Required action | Evidence / target date | Release decision |
| --- | --- | --- | --- | --- | --- | --- |
| SAMPLE | Replace with an actual finding | Critical / high / medium / low | Name | Concrete fix | Link/date | Block / accepted limitation / later |

### Release-day sequence

1. Confirm scope, release ID, owners, backup and maintenance window.
2. Complete staging acceptance and recovery rehearsal.
3. Deploy approved source/configuration and migrations with writes controlled.
4. Verify readiness, HTTPS, critical journeys, persistent media and jobs.
5. Verify real alert receipt and controlled transactional communication.
6. Open public access only after sign-off; watch errors and user feedback.
7. Roll back promptly if critical acceptance fails, preserving new business records.

### Cost worksheet

Record estimates and renewal owners for domain, hosting/compute, database, storage/backups, bandwidth/CDN, email, monitoring and support. Add payment/courier fees for commerce, and licensing/tax/legal review when needed. Some may be included or free at your scale; avoid buying a service solely because a social-media checklist names it. Set budget alerts and review scale assumptions before launch.

## How the two Instagram checklists fit

The [first post](https://www.instagram.com/p/DcKiRe3TvdB/) highlights layout, navigation, basic metadata and form feedback. The [second post](https://www.instagram.com/p/DfShMOkPXQW/) adds discoverability, policies, optional tracking and a promoted service. These are useful prompts, not a complete deployment standard. The detailed AURK companion report maps every listed item to a result. This template additionally covers configuration, security, concurrency, durable data, recovery, monitoring, fulfilment and ownership—the work that makes a public website dependable after the launch screen looks correct.
