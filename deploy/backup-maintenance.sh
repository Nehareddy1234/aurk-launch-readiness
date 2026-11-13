#!/usr/bin/env bash
set -Eeuo pipefail
: "${AURK_BACKUP_S3:?Set the private S3 backup prefix}"
: "${AURK_BACKUP_DATABASE:?Set the existing database name}"
: "${AURK_MYSQL_DEFAULTS:?Set the private MySQL client defaults file}"
# Install this only after replacing any older notification timer.
if systemctl is-active --quiet aurk-customer-emails.timer; then
  echo 'Replace the legacy customer email timer before enabling this backup job.' >&2
  exit 1
fi
app_was_active=false
timer_was_active=false
systemctl is-active --quiet aurk.service && app_was_active=true
systemctl is-active --quiet aurk-notifications.timer && timer_was_active=true
restore_services() {
  if "$app_was_active"; then systemctl start aurk.service; fi
  if "$timer_was_active"; then systemctl start aurk-notifications.timer; fi
}
trap restore_services EXIT
systemctl stop aurk-notifications.timer
systemctl stop aurk-notifications.service aurk.service
cd /home/ubuntu/Aurk
.venv/bin/python scripts/backup_store.py --mysql-defaults "$AURK_MYSQL_DEFAULTS" --database "$AURK_BACKUP_DATABASE" --uploads /home/ubuntu/Aurk/instance/uploads --destination /var/backups/aurk --s3 "$AURK_BACKUP_S3"
