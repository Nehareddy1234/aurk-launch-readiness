# AURK release runbook

Updated 6 November 2026 after authorized read-only AWS console and server diagnostics. This is a procedure for a later authorized deployment. No production configuration was changed; Google account access remains excluded. Read `AURK_READINESS_REPORT.md` for remaining release gates and `WEBSITE_DEPLOYMENT_PLAYBOOK.md` for the reusable checklist.

## 1. Protect the existing store

This is an upgrade of an existing application. Preserve the existing database, `.env`, uploads, server configuration and last working release. Do not upload the historical recovery ZIP, run a fresh-start script, reset tables, seed demo customers, overwrite production credentials, or run test fixtures against production.

The expected historical installation is `/home/ubuntu/Aurk`, Nginx static files under `/var/www/aurk/static`, and systemd `aurk.service`. The read-only inspection confirmed the existing host installation and services. Recheck release, static, environment and upload paths before executing commands. Reconcile source control and save the current release identifier before publishing; local changes have not been committed or pushed.

Build locally with `python scripts/build_release.py`. The output is `dist/aurk-release.zip` plus its SHA-256 file. Validate that checksum after transfer, and verify each entry against `release-manifest.json`. The package contains application source and bundled media, not customer uploads, databases or secrets. Keep copies of the previous release and its lock file.

## 2. Rehearse on isolated staging

Use Linux, MySQL 8.4 and a private Redis service. The exact live Python 3.14.4 runtime passed local Linux backend and Gunicorn checks; the Docker base remains Python 3.11. Do not substitute an untested dependency set. Install `requirements-lock.txt` into a new virtual environment and run `python -m pip check`. Local Linux Gunicorn checks passed; an actual Docker image build and systemd/Nginx installation are still unverified. Use a different secret, database and upload directory in staging. Block public access and outgoing customer messages; set `CUSTOMER_EMAILS_ENABLED=false`, clear SMTP/WhatsApp values, and keep indexing disabled. Robots exclusion alone is not access control.

Restore a recent backup into staging, inspect its migration revision and rehearse the upgrade. The supported chain is through `a1de49fa2387`, followed by `b2ef50ab3498`, `c3fa61bc4509` and `d4ab72cd5610`. The live database was observed at `a1de49fa2387`. An earlier local branch reused migration IDs for different schemas. The migration guard intentionally stops that mismatch. Do not bypass it with `flask db stamp`, manual revision edits, `db.create_all()` or table deletion. Compare the actual schema and reconcile it explicitly before proceeding.

From the isolated installation, with staging configuration loaded:

```sh
.venv/bin/python -m flask --app wsgi:app db current
.venv/bin/python -m flask --app wsgi:app db upgrade
.venv/bin/python -m flask --app wsgi:app db current
```

Expected final revision: `d4ab72cd5610`. Verify customer/order counts, representative orders, product variants, media, login and administrative access. MySQL tests in this delivery used synthetic data; a restored-store rehearsal remains required.

## 3. Configure production privately

Use `.env.example` as a key inventory, not as ready production configuration. Restrict the real `.env` to the service owner and never include it in an archive, ticket or repository.

| Setting | Production decision |
| --- | --- |
| `FLASK_CONFIG` | `production`; debug and test mode off |
| `SECRET_KEY` | Unique cryptographically random value, at least 32 characters; rotation signs users out |
| `DATABASE_URL` | Existing MySQL database, dedicated least-privilege account; URL-encode password characters |
| `UPLOAD_DIR` | Absolute persistent directory; service account can write; excluded from release replacement |
| `SESSION_COOKIE_SECURE` | `true`; also secures remember cookies |
| `PUBLIC_BASE_URL` | `https://aurk.in` |
| `TRUSTED_PROXY_COUNT` | `1` only with Gunicorn inaccessible except through the single trusted Nginx proxy |
| `RATELIMIT_STORAGE_URI` | Reachable private Redis URL, shared by all web workers |
| `SEARCH_INDEXING_ENABLED` | `false` during staging; `true` only for the approved public store |
| `MAIL_*`, `ORDER_ALERT_EMAIL` | Verified sender/recipient and TLS SMTP settings; choose TLS or SSL, not both |
| `CUSTOMER_EMAILS_ENABLED` | Enable after controlled-inbox delivery and worker checks |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Leave all blank for this scope. Password/phone login remains available. Configure Google later if desired |
| WhatsApp and payment gateway secrets | Leave disabled/unset for the agreed manual COD workflow |
| Business fields | Enter confirmed facts in Admin > Business & delivery; do not invent GST registration or addresses |

Run `python -m flask --app wsgi:app check-deployment --technical-only` during preparation and the same command without the flag for business launch sign-off. The technical-only flag deliberately defers business disclosures; it is not approval to open orders. The full check still cannot certify TLS, actual email arrival, backups, legal applicability or all operational settings.

## 4. Publish the approved release

**Before scheduling:** the observed 8 GiB root volume is 84% full (about 1.1 GiB free), unencrypted and configured for deletion on termination. No recoverable store backup was demonstrated. Complete a verified private off-server backup and plan capacity/encryption/address protection before deploying. The preflight requires at least 2 GiB free. Capacity changes and Elastic IP allocation are later AWS writes, with costs to review; none have been made.


1. Announce a maintenance window and retain a maintenance response at the proxy. Stop writes and the notification scheduler. The existing scheduler is `aurk-customer-emails.timer`: disable/stop it during the reviewed handover and wait for its service to finish before enabling `aurk-notifications.timer`. Also inspect cron/other workers; only one scheduler should own each job.
2. Take a consistent database-and-uploads backup and verify a copy away from the server. Record the last order number and backup time.
3. Install the verified source into a separate release directory; attach the existing private configuration and persistent uploads. Install locked dependencies. Rehearse path changes before replacing the historical in-place layout.
4. Apply reviewed migrations once while writes are stopped. Never let multiple deployments migrate concurrently.
5. Run Gunicorn using `gunicorn.conf.py` behind Nginx. Use the existing app service only after checking its user, working directory, environment and restart policy. Do not serve production using Flask's development server. See [Flask deployment guidance](https://flask.palletsprojects.com/en/stable/deploying/).
6. Adapt `nginx/ar_drips.conf` to the verified certificate paths and static root; validate with `nginx -t` before reload. Serve the new static tree as well as Python/templates. Verify HTTPS, HTTP redirects, the chosen canonical hostname and certificate renewal. Restrict database, Redis and Gunicorn ports to private/local access.
7. Install the reviewed `aurk-notifications.service` and timer from `deploy/`; they assume `/home/ubuntu/Aurk` and user `ubuntu`. Confirm environment, paths and permissions, reload systemd and start the timer. Run one controlled batch and inspect logs and queue states.
8. Run readiness/smoke checks below before opening orders. Keep rollback available throughout.

The Compose file is an alternative deployment route. Do not run it alongside the host installation against the same live database. It enforces production configuration and secure cookies for web, migration and worker services, so customer use requires an HTTPS proxy. It deliberately does not migrate on web restart. After backup and stopping writes, build the release, start dependencies, migrate once, then start web/worker:

```sh
docker compose build
docker compose up -d db redis
docker compose --profile maintenance run --rm migrate
docker compose up -d web order-alerts
```

A Docker image build and Linux systemd/Nginx installation have not been executed. YAML parsing and local Gunicorn tests do not certify those deployment routes.

## 5. Backups, recovery and monitoring

`deploy/backup-maintenance.sh` temporarily stops the application and notification timer to create a consistent bundle. This causes a short outage; choose and communicate the maintenance window. The supplied daily timer is 21:30 UTC / 03:00 IST. Review all paths and any older workers before enabling it.

`scripts/backup_store.py` uses a private MySQL defaults file (mode 600), includes uploads and SQL, writes a checksum manifest, and checks S3 public-access blocking before encrypted upload. The backup destination and permissions are intentionally unconfigured. Read-only AWS inspection found a private deployment-artifact bucket, not verified store backups; do not assume it is a configured backup destination. If a different backup provider is chosen, implement and verify its private off-server copy before enabling unattended backup. A local archive alone is insufficient protection against server loss. Establish retention and space monitoring; this script does not prune old bundles. A suggested starting policy is 7 daily and 4 weekly copies, adjusted to the business's retention obligations and recovery goals.

Restore only trusted backups. `scripts/restore_drill.py` verifies the checksum, rejects unsafe archive paths and restores into a newly named local scratch database and folder. SQL backups are trusted executable database input; use an isolated recovery server/account. Example, with actual private paths substituted:

```sh
python scripts/restore_drill.py --bundle /private/download/store.tar.gz --manifest /private/download/manifest.json --scratch-parent /private/drills --mysql-defaults /private/mysql-drill.cnf
```

After restore, inspect counts, representative orders and uploads, run the reviewed migration and exercise the app with outgoing mail disabled. Record elapsed recovery time. Cleanup only the exact scratch schema and directory after verification. A successful backup upload is not a successful restore drill.

The health timer checks disk/upload access, `/api/ready` and notification queues. Local `aurk-alert@.service` and `scripts/operational_alert.py` templates now provide bounded failure email without depending on the application database. They remain uninstalled and unconfigured. After recipient/test-message approval, configure `/etc/aurk/alerts.env` from `deploy/alerts.env.example` and install the alert unit alongside the health/backup/notification units. The alert reads existing SMTP settings privately and suppresses repeated attempts for the same unit for one hour, including uncertain SMTP outcomes. This is not proof of inbox delivery and cannot report a whole-host or network outage when its own host is down. Configure an external uptime check and an alert destination, and test a failure. Alert on failed backups, database connectivity, disk pressure, queue age and worker failures. The supplied Gunicorn/Nginx access formats omit request URLs to avoid logging reset tokens. Validate Nginx configuration before reload and keep private error logs access restricted. Logs must not expose credentials, session tokens or unnecessary customer data. Apply log rotation and access restrictions.

Customer and order email workers use retry controls, but SMTP acceptance is not proof of inbox delivery and exactly-once delivery cannot be guaranteed across a process crash. Product-interest owner alerts now use bounded retries (five attempts), exponential backoff and a hold for uncertain SMTP outcomes. Run `flask --app wsgi:app check-operations` to detect stale/exhausted/uncertain queues without sending mail. After reviewing one failed alert against provider/inbox evidence, `flask --app wsgi:app retry-interest-alert ID --reviewed` requeues that alert for the worker; it does not send immediately. Never bulk-reset uncertain messages. Before manually resending an uncertain message, check provider logs and the recipient inbox. Do not send real customer test messages.

## 6. Public acceptance and rollback

After later deployment, run the read-only `python scripts/production_smoke.py --base-url https://aurk.in` and inspect its JSON evidence. Also verify `/api/ready`, robots/sitemap/feed, HTTPS redirects, secure cookie flags, private-page noindex, responsive layout, media range requests and caching. Test with a controlled account/inbox: registration, login, password recovery, cart changes, COD order, owner confirmation, shipment/tracking, cancellation and reconciliation. Use an approved test-order procedure so stock, courier requests and accounting are not confused with sales. Check real iOS/Safari and Android devices and slow connectivity; local Chromium emulation is incomplete coverage.

Rollback trigger: broken checkout/login, schema errors, lost media, serious security regression or persistent elevated failures. Stop writes and workers first. If schema-compatible, restore the previous source/configuration/static release and smoke-test. Do not blindly downgrade a database after accepting new orders. If restore is necessary, reconcile all writes after the backup with the business before replacing data. Record the incident, recovery time and corrective action.

Open the store only after the owner has confirmed disclosures, courier coverage workflow, support ownership, verified email, backup recovery and the live acceptance checks. Google submission is a separate later task; it is not required for customers to visit a working URL.
