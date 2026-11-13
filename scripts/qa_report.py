"""Generate the audit report from actual pytest/coverage artifacts."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET


FINDINGS = [
    dict(id="QA-AUTH-002", severity="High", match="test_QA_AUTH_002", source="app/auth/routes.py:41,191-195",
         title="Password reset leaves another customer session active",
         expected="Resetting a password invalidates existing authenticated customer sessions.",
         actual="A separately logged-in test client still receives HTTP 200 from /account/ after a successful password reset in another client.",
         steps="Create a customer; sign in with client A and verify /account/ returns 200; reset the password with a valid single-use token in client B; request /account/ again with A's original cookie.",
         fix="Add a per-user session version or authentication fingerprint checked on every customer request, and rotate it on password reset/change. Admin-session deletion alone does not revoke customer cookies.",
         caveat="Database-independent reproduction. Requires possession of an already valid customer session; this is not an unauthenticated login bypass."),
    dict(id="QA-AUTH-001", severity="Medium", match="test_QA_AUTH_001", source="app/auth/routes.py:56,86",
         title="Signup and login normalize email case differently",
         expected="An account registered with MiXeD@example.com can sign in using its normalized email.",
         actual="Signup preserves local-part case while login lowercases the full address; login fails on the isolated case-sensitive SQLite database.",
         steps="POST /auth/register with MiXeD@example.com and a valid password; POST /auth/login with mixed@example.com; GET /account/ returns 302 instead of 200.",
         fix="Use one explicit email-normalization policy for registration, login, password recovery and uniqueness; review existing records before any normalization migration.",
         caveat="The login failure is reproduced on SQLite. A case-insensitive MySQL collation can mask it; live MySQL impact is NOT verified. Treat this as a confirmed normalization/portability defect, not proof all production users are affected."),
    dict(id="QA-CATALOG-001", severity="Medium", match="test_QA_CATALOG_001", source="app/products/routes.py:24,111-118; app/main/routes.py:16-22",
         title="Archived products can still be publicly displayed",
         expected="An archived product is excluded from public catalog queries and its direct detail URL returns 404.",
         actual="A product with is_archived=True and is_active=True returns 200 at its public detail URL. Public queries filter is_active but not is_archived.",
         steps="Seed a product with is_active=True and is_archived=True, with a variant; GET /product/<slug>.",
         fix="Filter is_archived=False consistently in all public product/media queries and define/enforce the archive-active invariant.",
         caveat="The usual admin archive action also disables a product. This test exercises inconsistent flags that the model/schema permit, not a demonstrated normal admin-archive workflow failure."),
    dict(id="QA-UI-001", severity="Medium", match="test_QA_UI_001", source="app/security/headers.py:21; app/static/js/admin.js:64-66",
         title="Content Security Policy blocks admin image-upload previews",
         expected="Selecting a valid image in the admin product form displays its local preview.",
         actual="Chromium creates the preview element, but its blob: URL is refused by img-src 'self' data:. The completed image has naturalWidth=0.",
         steps="Sign into admin; open /admin/products/create; choose a valid PNG; wait for the preview image to complete and inspect naturalWidth or the browser CSP error.",
         fix="Allow blob: in the narrowly required image/media source policies, preferably scoped to admin pages, or use an approved preview URL strategy. Keep the remaining CSP restrictions.",
         caveat="Confirmed with real local Chromium and the application's CSP enabled. Image preview failure does not by itself prove server-side uploading fails. Video previews also use blob URLs but were not separately decoded in this browser test."),
    dict(id="QA-PERF-001", severity="Medium", match="test_catalog_query_growth_and_route_timings", source="app/products/routes.py:24; app/services/catalog.py:5-9; app/templates/shop/_variant_fields.html:2",
         title="Shop rendering issues two additional queries per product/variant in the fixture",
         expected="Adding products to a catalog page does not introduce linear per-product size/colour queries.",
         actual="The controlled fixture grows from 10 SELECT statements for one product to 28 for ten products. Timings remain below one second locally, but query count scales linearly.",
         steps="Attach SQLAlchemy before_cursor_execute; GET /shop with one stocked variant; seed nine more products with distinct sizes/colours; GET /shop again and compare counts.",
         fix="Eager-load ProductVariant.size and ProductVariant.color alongside inventory, and measure repeated requests and admin lists after the change.",
         caveat="Measured on isolated SQLite; this confirms redundant queries, not production latency. See catalog-performance.json for actual timing measurements."),
    dict(id="QA-EMAIL-001", severity="Medium", match="test_QA_EMAIL_001", source="app/services/customer_emails.py:82-91",
         title="SMTP acceptance followed by a lost response can produce duplicate emails",
         expected="The requested timeout/idempotency guarantee would permit one provider acceptance for one event.",
         actual="A mock accepts the message then raises TimeoutError. The worker marks it failed and a due retry accepts it a second time.",
         steps="Queue one welcome event; use a fake SMTP sender that records acceptance then times out; dispatch; make next_attempt_at due; dispatch again; acceptance count is two.",
         fix="Document at-least-once delivery explicitly. If exactly-once provider submission is required, adopt a provider API with enforceable idempotency keys or an uncertain-delivery reconciliation state. A unique outbox event alone cannot solve an ambiguous SMTP acknowledgement.",
         caveat="A protocol/design limitation exposed by the user's requested guarantee. No real email was sent. This differs from repeat worker runs after a recorded successful submission, which are already deduplicated."),
    dict(id="QA-CONFIG-001", severity="Medium", match="test_QA_CONFIG_001", source="app/config.py:91-95",
         title="TestingConfig can inherit enabled customer email automation",
         expected="TestingConfig keeps CUSTOMER_EMAILS_ENABLED=False regardless of a live-style environment flag.",
         actual="The explicit False assignment is overwritten by a second environment-based assignment; setting CUSTOMER_EMAILS_ENABLED=true yields True in TestingConfig.",
         steps="Evaluate config with CUSTOMER_EMAILS_ENABLED=true; inspect TestingConfig.CUSTOMER_EMAILS_ENABLED.",
         fix="Remove the duplicate environment override from TestingConfig and keep test mail transports explicitly isolated.",
         caveat="QA fixtures force automation off and block SMTP sockets. MAIL_SERVER is also blank in TestingConfig, so this finding does not claim its default configuration alone can send live mail."),
    dict(id="QA-SECURITY-001", severity="Low", match="test_QA_SECURITY_001", source=".gitignore:27-34",
         title="Product uploads do not meet the requested all-uploads Git-ignore policy",
         expected="git check-ignore recognizes all upload paths as ignored.",
         actual="Explicit image exceptions allow instance/uploads/products/999/private.jpg into Git. The sensitive customer-photos directory has its own ignore rule and is protected.",
         steps="Run git check-ignore --no-index instance/uploads/products/999/private.jpg; exit status is 1.",
         fix="Decide whether product media are intentional versioned assets. If all uploads must be excluded, remove the image exceptions and review already tracked files without deleting live media.",
         caveat="Policy mismatch, not evidence of leaked customer photos or credentials. Existing product-image versioning appears intentional, so application/security impact is limited."),
    dict(id="QA-DB-001", severity="Low", match="test_QA_DB_001", source="app/models/catalog.py:82,286,296,305,360,465; migrations/versions/11b8ff211bcb_initial_schema.py",
         title="Fresh SQLite migrations differ from model foreign-key types",
         expected="Alembic metadata comparison on a freshly migrated test database produces no unexpected type changes.",
         actual="Autogenerate proposes six BIGINT-to-INTEGER changes for catalog foreign keys because BigIntPrimaryKey compiles as INTEGER on SQLite but the initial migration declares those foreign keys BIGINT.",
         steps="Create an empty SQLite database; flask db upgrade; compare_metadata with compare_type=True and compare_server_default=True.",
         fix="Align SQLite variants for the six foreign-key columns, or explicitly document an intentional comparator policy. Confirm independently against MySQL before issuing any production ALTER TABLE.",
         caveat="Confirmed SQLite migration portability drift only. MySQL metadata parity is UNVERIFIED, and both types compile to BIGINT there; do not apply the generated SQLite changes blindly to production."),
]


def read_run(seed):
    kind="coverage" if seed==202 else "test"
    path=Path(f"qa_artifacts/{kind}-{seed}.xml")
    root=ET.parse(path).getroot()
    cases=list(root.iter("testcase"))
    failed=[c for c in cases if c.find("failure") is not None]
    errors=[c for c in cases if c.find("error") is not None]
    skipped=[c for c in cases if c.find("skipped") is not None]
    return dict(seed=seed,path=path,cases=cases,failed=failed,errors=errors,skipped=skipped,
        passed=len(cases)-len(failed)-len(errors)-len(skipped),time=sum(float(s.get("time",0)) for s in root.iter("testsuite")))


def main():
    runs=[read_run(seed) for seed in (202,303,404)]
    latest=runs[-1]
    coverage=json.loads(Path("qa_artifacts/coverage-202.json").read_text())
    inventory=json.loads(Path("qa_artifacts/inventory.json").read_text())
    hashes=json.loads(Path("qa_artifacts/application-source-hashes.json").read_text())
    changed=[name for name,digest in hashes.items() if not Path(name).exists() or hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]
    failure_sets=[{c.get("classname")+"::"+c.get("name") for c in run["failed"]+run["errors"]} for run in runs]
    stable=all(s==failure_sets[0] for s in failure_sets[1:])
    axe_path=Path("qa_artifacts/accessibility.json")
    axe=json.loads(axe_path.read_text()) if axe_path.exists() else []
    timings_path=Path("qa_artifacts/public-route-timings.json")
    timings=json.loads(timings_path.read_text()) if timings_path.exists() else []
    lines=["# AURK QA audit report", "", "Date: 2026-10-19. Scope: the local repository and isolated test environments only.", "",
        "**This is an audit, not a production readiness certificate. Application defects were left unfixed as requested. No production/AWS connection or real email sending was used.**", "",
        "## Results", "", "| Random seed | Total | Passed | Failed | Errors | Skipped | Xfail | Seconds |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for run in runs:
        lines.append(f"| {run['seed']} | {len(run['cases'])} | {run['passed']} | {len(run['failed'])} | {len(run['errors'])} | {len(run['skipped'])} | 0 | {run['time']:.2f} |")
    totals=coverage["totals"]
    lines += ["",f"Line coverage: **{totals['percent_covered']:.2f}%** ({totals['covered_lines']}/{totals['num_statements']} executable lines). Coverage is not branch or concurrency coverage.", "",
        f"Final randomized failure sets identical: **{stable}**. Application/deployment files differing from the discovery hash snapshot: **{len(changed)}**.", "",
        "The 167-case original suite was first characterized under stricter upload/mail isolation. Its only initial failure was a test fixture creating an already-existing directory, which was corrected. The final runs include new audit regressions and real Chromium tests. No application test was weakened, xfailed, or deleted to hide a defect.", "",
        "The only expected environmental skips are the two explicit MySQL row-lock tests. A local MySQL service exists, but no dedicated test schema/account was supplied and the development account lacks schema-creation privileges. SQLite does not establish MySQL transaction, collation, deadlock, or locking correctness. The proposed GitHub Actions MySQL job was authored, not executed remotely.", "",
        "## FAILED TESTS — ordered by severity", ""]
    matched=set()
    for finding in FINDINGS:
        cases=[case for case in latest["failed"] if finding["match"] in case.get("name","")]
        if not cases: continue
        matched.update(id(case) for case in cases)
        lines += [f"### {finding['id']} — {finding['severity']}: {finding['title']}", "",
            "- Test: "+", ".join(f"`{case.get('classname')}::{case.get('name')}`" for case in cases),
            f"- Application/source location: `{finding['source']}`.",
            f"- Expected: {finding['expected']}",f"- Actual: {finding['actual']}",f"- Reproduce: {finding['steps']}",
            f"- Suggested fix (not applied): {finding['fix']}",f"- Evidence limits: {finding['caveat']}", ""]
    for case in latest["failed"]:
        if id(case) not in matched:
            failure=case.find("failure")
            lines += [f"### Unclassified failure: {case.get('classname')}::{case.get('name')}", "",failure.get("message","")[:1500], ""]
    for case in latest["errors"]:
        lines += [f"### Test error: {case.get('classname')}::{case.get('name')}", "",case.find("error").get("message","")[:1500], ""]
    lines += ["## Security findings and tested protections", "",
        "- High: QA-AUTH-002 preserves an existing customer session after password reset. Admin-session invalidation is implemented separately.",
        "- Medium test-isolation issue: QA-CONFIG-001 inherits the email-enable flag. Tests override it and block real SMTP/network access.",
        "- Low policy mismatch: QA-SECURITY-001 allows product images into Git. Customer photos, .env, SQL dumps and logs are ignored. A current-tree scan covered 179 tracked/untracked nonignored source/config/document text files and found no known SMTP-key, AWS access-key or private-key patterns (secret-scan.json). No .env/key/log/SQL files were listed by the corresponding tracked-file check. These checks are not an entropy-based or repository-history secret audit.",
        "- Route-wide mutation tests send requests without CSRF tokens to every registered POST/PUT/PATCH/DELETE route and require rejection. See csrf-routes.json.",
        "- Admin access is tested as anonymous, customer, zero-permission admin, fully permissioned Super Admin, and each individual admin permission. Authorized nonexistent-record requests may legitimately return 400/404; this matrix proves the gates, not every successful mutation. Existing CRUD tests exercise actual records.",
        "- Cross-customer order, status, checkout-success, cart-update/remove and address tampering tests verify ownership boundaries. Existing community tests verify pending-photo ownership/admin access and withdrawal boundaries.",
        "- Password hashing, safe redirect rejection, auth rate limits, production-like response headers, and XSS escaping are exercised with synthetic data. The negative SQL search payloads do not produce query errors or stack traces.",
        "- CSP needs a narrow correction for upload previews (QA-UI-001); do not remove the policy wholesale.", "",
        "Static operational observations, not confirmed live findings: the limiter defaults to memory:// (app/config.py), and its default key is get_remote_address (app/extensions.py). Multi-worker deployments and trusted-proxy/client-IP handling need independent verification; this audit did not access Nginx or the live limiter backend.", "",
        "## Feature-by-feature evidence", "", "| Area | Result and what was actually exercised |", "|---|---|"]
    rows=[
        ("Catalog", "Search empty/no-result/special/SQL-like/long queries, availability/hidden pricing, sorting and variant stock are tested. QA-CATALOG-001 and QA-PERF-001 remain failing."),
        ("Cart", "No remaining cart-specific failures: guest persistence/update/remove, merge, stock and quantity boundaries, exact submitted SKU, ownership and ignored client price fields are asserted."),
        ("Accounts", "Registration/login/profile/address/password recovery are exercised. QA-AUTH-001 (SQLite collation caveat) and QA-AUTH-002 remain failing."),
        ("Checkout", "No remaining sequential checkout failures: actual order/items/snapshots/totals/COD/inventory/movements/cart-clear/outbox assertions, stock/product/variant revalidation and forced post-order exception rollback. Concurrent last-unit checkout is NOT verified without MySQL."),
        ("Order lifecycle", "No remaining lifecycle-specific failures: invalid-transition matrix, confirmation deduplication, cancellation/restock-once, audit, delivery versus cash receipt and ownership tests pass."),
        ("Admin", "Authentication/session expiry/revocation, role gates, inventory, catalog/category/coupon/review/report operations are exercised. Local image preview fails (QA-UI-001)."),
        ("Emails", "SMTP is mocked: sender/recipient/Reply-To/HTML/text/logo/theme/escaping, success/failure/backoff/exhaustion/cancellation/deduplication and Notify me business/customer alerts are asserted. Ambiguous SMTP timeout can duplicate (QA-EMAIL-001); overlapping MySQL worker safety is unverified."),
        ("Notify me", "Guest redirects through login/signup return path; signed-in registration and duplicate suppression; matching acknowledgement/customer data and business Reply-To; repeated worker handling. No restock launch-mail feature is invented."),
        ("Worn by you", "No remaining community-specific failures: public approved-only gallery, each ownership/delivery/consent rule, moderation/withdrawal, private direct URLs, limits, corrupt/oversized images, traversal-safe generated filenames, metadata and executable-tail removal."),
        ("Migrations", "Fresh SQLite upgrade reaches a single 90cd38ef1276 head, latest downgrade/upgrade succeeds, uniqueness/foreign-key/cascade cases are exercised. SQLite catalog foreign-key type drift remains (QA-DB-001). MySQL migration parity has not been run locally."),
        ("Browser", "Real Chromium loopback-only browse/product/variant/cart/login/checkout/order-history journey and gallery/Notify me at 375px and 1440px. No horizontal overflow on measured pages or JS pageerrors in passing journeys. Upload-preview CSP regression remains."),
        ("Deployment", "Static inspection only: Flask production-like boot with dummy values, WSGI/Gunicorn configuration, cookie/header behavior and deployment docs. No AWS, public-domain probing, service restarts or releases."),
    ]
    lines += [f"| {a} | {b} |" for a,b in rows]
    lines += ["", "## Browser accessibility and performance", "",
        f"axe-core 4.10.3 ran WCAG 2 A/AA and 2.1 AA tags on **{len(axe)}** pages. Recorded violations: **{sum(len(r['violations']) for r in axe)}**. Pages: "+", ".join(f"`{r['path']}`" for r in axe)+".", "",
        "This is a Chromium DOM audit of synthetic fixture pages, not manual keyboard/screen-reader certification, all product content, mobile accessibility, all interactive states, or full WCAG conformance. The detailed evidence is accessibility.json.", "",
        "Mobile and desktop document-width measurements are in layout-375.json and layout-1440.json; screenshots are notify-375.png and notify-1440.png. Full-page screenshots may retain the current scroll/focus position. Pointer target geometry and actual touchscreen gestures were not exhaustively audited.", "",
        f"Public route timings recorded: {len(timings)}. Maximum observed: {max((r['seconds'] for r in timings),default=0):.3f}s. Routes over one second: "+str([r['path'] for r in timings if r['seconds']>1])+". These are local test timings, not a load test or production SLA.", "",
        "The shop query-growth regression is recorded in catalog-performance.json. Internal links and static assets referenced by the tested public information pages were requested locally; no broken links/assets remained in that test. Every asset under every admin/product state was not crawled.", "",
        "## Known limitations — not misreported as new functional failures", "",
        "- Notify me currently acknowledges a request; no automatic email blast is triggered when the drop goes live.",
        "- Cash on delivery only; no online gateway tests were invented.",
        "- No established courier tracking integration or automated confirmation phone call.",
        "- No established automatic backup schedule. Prior manual backups do not constitute scheduled backup monitoring or restore drills.",
        "- Historical server Nginx limit was 8 MB. The checked-in Nginx template now says 100M and the app allows 100 MB total (photos/video have lower per-file caps). The current live config was not accessed and may still differ; this is an operational verification gap, not a newly measured live failure.",
        "- Customer photos require delivered-order ownership and moderation; no AI garment/photo verification is implemented.",
        "- SMTP submission is not a delivery receipt. Spam placement, domain/IP authorization, real mail-client rendering and reply delivery were not tested here.", "",
        "## Coverage gaps and constraints", "",
        "- Dedicated MySQL unavailable: two explicit environmental skips, no claim of row-lock correctness, deadlock handling, full same-customer parallel checkout coverage, MySQL schema parity or MySQL collation behavior.",
        "- Browser coverage is Chromium only, with synthetic products/users and local loopback hosting. No Firefox, Safari/iOS, Android hardware, reverse-proxy behavior or Nginx/TLS path was exercised.",
        "- MP4 container validation and gallery exclusion are unit-tested; codec decode quality, malformed media fuzzing and production-size video playback/performance were not comprehensively tested.",
        "- No production load/stress test, large-catalog benchmark, exhaustive admin-list query-count profiling or SMTP process-crash recovery proof.",
        "- Passing browser journeys assert uncaught JavaScript pageerrors and selected HTTP failures; they do not exhaustively classify every console.error/warning or browser-extension/system message.",
        "- Route permission/CSRF enumeration is broad; successful data mutations, multi-role combinations, every form branch and all malicious payloads cannot be inferred merely from that enumeration.",
        "- Coverage is statement coverage. Uncovered lines below and in the HTML report are explicit evidence gaps, even in modules whose tests pass.", "",
        "## Per-module line coverage", "", "| Module | Covered / executable lines | Coverage | Missing lines |", "|---|---:|---:|---|"]
    for name,data in sorted(coverage["files"].items()):
        summary=data["summary"]
        missing=", ".join(map(str,data.get("missing_lines",[]))) or "—"
        lines.append(f"| `{name}` | {summary['covered_lines']}/{summary['num_statements']} | {summary['percent_covered']:.2f}% | {missing} |")
    lines += ["", "## Test-harness corrections (not application fixes)", "",
        "- Shared fixtures now validate the test DB location, use temporary uploads, blank delivery configuration and prohibit real SMTP/non-local sockets.",
        "- pytest-flask's implicit test-wide request context was removed. It had cached users/catalog objects across separate requests, masking password-session behavior and causing false stale-price/variant results in exploratory tests.",
        "- Factories return scalar snapshots outside their context so commits do not expire/reattach objects and create misleading DetachedInstanceError failures.",
        "- An exploratory permission-matrix fixture accidentally logged in its anonymous actor. That test-only mistake was corrected before the three final seeded runs.",
        "- Existing hidden-image test mkdir now tolerates the temporary upload directory already created by the app fixture.",
        "- Large binary parameter cases have short IDs; otherwise Windows rejects pytest's oversized PYTEST_CURRENT_TEST environment variable. The oversized exploratory trace was replaced with a short explanation.",
        "- The gallery browser test follows the active full-photo link/track because JavaScript intentionally replaces the original img element. This corrects a test selector, not a gallery failure.",
        "- Pixel-limit tests assert actual rejection/no saved file rather than one exact error string: Pillow's decompression-bomb check may reject before the custom pixel check. Pillow global limits and SQLite engines are restored/disposed between tests.",
        "- Request-flow tests use actual commits and fresh per-test schemas because application services commit internally. The optional db_session fixture rolls back uncommitted work; committed flows are isolated by schema recreation, not a misleading outer rollback.", "",
        "## Files and commands", "",
        "Added: TEST_INVENTORY.md, TESTING_REPORT.md, requirements-test.txt, scripts/qa_inventory.py, scripts/run_qa.py, scripts/qa_report.py, .github/workflows/qa.yml, tests/security/test_qa_audit.py, tests/integration/test_qa_commerce.py, tests/integration/test_qa_database.py, tests/integration/test_qa_email_edges.py, tests/unit/test_qa_uploads_and_config.py, tests/e2e/test_local_browser.py, and generated qa_artifacts/ evidence.", "",
        "Changed testing infrastructure only: tests/conftest.py and tests/security/test_admin_workspace.py. App, migrations, Nginx and runtime dependency sources remain unchanged according to the hash snapshot.", "",
        "```powershell\n.venv/Scripts/python.exe -m pip install -r requirements-test.txt\n.venv/Scripts/python.exe -m scripts.run_qa browser-setup\n.venv/Scripts/python.exe -m scripts.run_qa test\n.venv/Scripts/python.exe -m scripts.run_qa test-unit\n.venv/Scripts/python.exe -m scripts.run_qa test-integration\n.venv/Scripts/python.exe -m scripts.run_qa test-security\n.venv/Scripts/python.exe -m scripts.run_qa test-e2e\n.venv/Scripts/python.exe -m scripts.run_qa coverage --seed 202\n.venv/Scripts/python.exe -m scripts.run_qa test --seed 303\n.venv/Scripts/python.exe -m scripts.run_qa test --seed 404\n.venv/Scripts/python.exe -m scripts.qa_report\n```", "",
        "For MySQL, configure TEST_DATABASE_URL privately with a dedicated disposable local schema containing test or qa in its name. The suite creates/drops its tables. Never point it at the application database. CI defines its own disposable aurk_qa_test service; the workflow has not been pushed/executed as part of this audit.", "",
        "Full per-route/model/relationship/service/migration inventory: TEST_INVENTORY.md and qa_artifacts/inventory.json. HTML coverage: qa_artifacts/coverage/index.html. Seeded JUnit XML and redacted logs are under qa_artifacts/.", "",
        "## Recommended next steps", "",
        "1. Obtain approval to fix QA-AUTH-002, then test customer-session revocation and admin-session behavior together.",
        "2. Supply the isolated MySQL test schema/run the proposed CI workflow. Verify last-unit checkout, overlapping workers, migrations and email collation before claiming concurrency readiness.",
        "3. Approve account normalization, public archive filtering and narrow upload-preview CSP fixes; rerun their failing regressions.",
        "4. Eager-load variant dimensions, hard-disable test email automation, and agree the uploads version-control policy.",
        "5. Choose and document the email delivery/idempotency guarantee; reconcile ambiguous SMTP outcomes rather than promising exactly-once delivery.",
        "6. Verify the deployed upload limits separately in an authorized operations session, establish scheduled backups/restore drills, then expand cross-browser, accessibility-state and load testing.", ""]
    if changed:
        lines += ["Unexpected protected-source changes: "+", ".join(changed)]
    Path("TESTING_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    summary=dict(runs=[{k:v for k,v in run.items() if k in {"seed","passed","time"}} | dict(total=len(run["cases"]),failed=len(run["failed"]),errors=len(run["errors"]),skipped=len(run["skipped"])) for run in runs],coverage=totals,stable=stable,protected_source_changes=changed)
    Path("qa_artifacts/summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
