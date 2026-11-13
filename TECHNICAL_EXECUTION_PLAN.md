# AURK technical execution plan

> Status update 13 November 2026: the client approved proceeding but set the additional AWS budget to zero on 7 November. The chargeable resource proposal below is therefore on hold, not approved for execution. No AWS writes were completed before the session expired. [REMAINING_WORK.md](REMAINING_WORK.md) is the current task and constraint record.

Prepared 7 November 2026. This plan is based on the verified 6 November inspection; current resource state must be rechecked before any write. It supplements the client handover and release runbook. No AWS change is executed by this file.

## Proposed scope

The technical work can be carried out in the existing AWS account, in ap-south-2, with the current store preserved. The proposed resource envelope is one private backup bucket, one temporary staging instance (t3.small, 20 GiB encrypted storage), one stable public IP for the production endpoint, and a 20 GiB encrypted production root-volume replacement plus temporary recovery snapshots/volumes. These are proposed maximum resource counts for this approach, not a price quotation. Confirm regional pricing and the agreed spending limit before provisioning. If the limit cannot support the plan, stop and revise it.

## Execution sequence and acceptance criteria

| Stage | Concrete work | Evidence required before moving on |
| --- | --- | --- |
| 1. Recheck and preserve | Refresh instance/disk/schema/service observations. Record the live release and current DNS. Verify backup destination access. Create private encrypted/versioned backup storage if approved. | Resource inventory and a named recovery owner; approved cost scope. |
| 2. Consistent backup | During the approved write pause, stop writes and the legacy notification scheduler. Capture database and uploads, checksum the archive, store it privately outside the instance and resume the prior services. Preserve private configuration securely. | Verified remote copy and checksum; production service restored after the backup window. No fresh-start or table reset. |
| 3. Isolated rehearsal | Provision one temporary staging instance with encrypted storage and SSM access. Block real email/payment/courier calls and public indexing. Restore the backup privately, rehearse migrations, then run transactional/concurrency tests on a separate synthetic QA database. | Restore evidence, migration results, backend tests and exact installed runtime/dependencies. No test fixtures against the live/restored customer database. |
| 4. Production protection | Coordinate a stable public IP and DNS before any instance stop. Prepare encrypted 20 GiB replacement storage from verified recovery material. Preserve the original volume for rollback; review deletion/termination protection. | HTTPS/DNS correct, app/database/media intact, free space above the release threshold, encrypted storage verified. |
| 5. Application deployment | Install the verified 222-file source release and locked dependencies. Preserve environment/uploads. Apply migrations to d4ab72cd5610 during a controlled write pause. Configure private Redis, Nginx and the single trusted proxy. Replace the old email scheduler once. | Readiness succeeds, expected schema, public routes/media and anonymous access protections pass; rollback remains available. |
| 6. Operations | Enable reviewed notification/backup/health jobs. Configure disk, service, queue, backup and uptime alerts to the designated recipient. Define retention within the budget. | Scheduled jobs verified and a controlled failure notification acknowledged. Production email settings preserved until controlled delivery is verified. |
| 7. Acceptance | Use an approved test account/order/inbox to exercise the full COD workflow, email delivery, cancellation/restocking and reconciliation. Complete real-device and client fulfilment acceptance. | Test evidence and client sign-off. Stop/revise on any critical failure. |
| 8. Handover | Record final release, recovery procedure, billing/renewal owners and outstanding business requirements. Stop temporary compute when no longer needed; retain recovery data until approved cleanup. | Updated report and resource/cost inventory. No silent permanent deletion of original data or recovery artifacts. |

## Required decisions before execution

1. Authorization to go beyond the existing read-only AWS scope and perform the resource changes, backup/restore, deployment, DNS changes and service restarts described above.
2. Maximum additional recurring AWS spend per month, plus a total one-time allowance for staging/migration. Both amounts need a currency. Existing spend is separate. Provider costs must be checked before creating resources; no unlimited budget is assumed.
3. An allowed maintenance window in IST, including the maximum acceptable interruption and a contact who can approve extending it or rolling back. A window is not a promise of completion; stop safely if the work cannot finish in time.
4. The monitored alert inbox and a controlled test inbox. Explicit permission to send test notifications to those addresses is needed before messages are sent. Recipient confirmation may require the account owner to act.

Changes to sensitive IAM access or other actions requiring confirmation will be presented at the point of execution with the exact scope. Do not provide passwords or secret keys in chat. Existing authenticated sessions and secure service configuration are preferred.

## Work that still requires the client

Confirmed legal/business and return details, tax status, DTDC coverage, genuine catalogue approval, support ownership and final commercial acceptance remain client inputs. No active QA product will be silently deleted or archived. Google account access and submission remain separately deferred.

## Technical constraints

- The current 8 GiB production volume had about 1.1 GiB free. Do not install the full test stack or run a restore on that volume as a shortcut.
- Enabling EBS encryption by default does not encrypt an existing volume; replacement/copy work is required. See [AWS EBS encryption documentation](https://docs.aws.amazon.com/ebs/latest/userguide/encryption-by-default.html).
- Elastic IP allocation/association changes addressing and carries charges. DNS must be coordinated. See [AWS Elastic IP documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/working-with-eips.html).
- Docker and CI are optional delivery mechanisms. Validate the chosen host-service deployment path; do not add an unneeded parallel production stack.
- Previously passing local tests and read-only live data checks do not substitute for the isolated rehearsal or approved end-to-end live acceptance.

## Current status

Prepared for review. No new cloud resources, production writes, DNS changes, deployment, service restarts or external messages have been performed under this plan.
