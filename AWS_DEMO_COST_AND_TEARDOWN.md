# AWS demo cost and teardown checklist

**Reviewed:** 2026-10-27. **Scope:** A short, 3–7 day educational demo of the existing Daily Market Digest AWS path. This is not a production approval or a cost quote.

## 1. Readiness and assumptions

- This review did not create an AWS account or resources and did not call AWS. Current account resources, region availability, quotas, subnet routes, security group rules, billing, and secret configuration are therefore **unverified**.
- The checklist reflects the current `infra/aws-cloudformation.yml` and GitHub workflows in this workspace. The working tree already contains other uncommitted project changes; this document is the only file added for this checklist.
- The stack expects existing subnet IDs, security group IDs, a Secrets Manager JSON secret, and a GitHub OIDC provider ARN. The template does not create a VPC, subnets, NAT gateway, internet gateway, or security group. Confirm who owns the supplied network and whether it is shared before touching it.
- The template's defaults are `ImageTag=latest` and `ScheduleState=ENABLED`. For a new demo, explicitly create the stack with `ImageTag=bootstrap` and `ScheduleState=DISABLED`. The current deploy workflow publishes a commit/run-specific immutable tag and updates the stack to that tag after tests pass. Confirm the workflow's AWS role secret, region variable, repository/branch trust, and stack parameters before using it.
- Keep the AWS schedule disabled for the whole demo unless demonstrating scheduled execution is essential. The GitHub fallback workflow has its own schedule and is independent of the AWS `ScheduleState`; disable that workflow in the GitHub Actions UI for the demo, or it may still run the digest and send email.
- A manual ECS task can send email. Use a controlled recipient mailbox and an explicitly approved test message. An `email_pending`/`email_ambiguous` run is a no-retry barrier: inspect delivery and state before any manual retry.
- The configured Nifty 50 constituent list has not been verified against the latest official NSE membership list in the project audit. Do not present constituent rankings as current membership-verified data until that verification is completed. Do not treat absent or stale market data as a valid value.
- `cfn-lint`/CloudFormation offline validation cannot prove that account-specific IDs, IAM trust, quotas, routes, secret keys, or service availability will work. Verify these in the intended account before deployment.

## 2. What may exist and what can cost money

The template creates the AWS resources below when deployed. External prerequisites and GitHub-hosted resources are called out separately. “Demo need” assumes the shortest safe demo: run one controlled ECS task manually and leave both schedules disabled.

| Resource or prerequisite | Cost drivers / risk | Needed for demo? | Cleanup method and retained data |
|---|---|---|---|
| CloudFormation stack `daily-market-digest` | No separate stack fee; resources continue billing while active. | Yes, to create/manage the stack. | Delete the stack after disabling schedules and stopping tasks. Deletion is not reversible once started. |
| ECR repository `daily-market-digest` and images | Stored image GB-months, image pulls/data transfer, and scanning. The current template sets `ImageScanningConfiguration.ScanOnPush: true`; verify current charges and regional details in [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/). Immutable releases accumulate; there is no repository lifecycle policy. | Yes, for the task image. | The repository has `DeletionPolicy: Retain`, so stack deletion leaves it. Review tags and rollback needs before deleting images or the repository: deletion can permanently remove image artifacts needed for rollback. |
| ECS cluster, task definition, Fargate task | Fargate vCPU and memory while the task runs (task is 1 vCPU/2 GiB), plus ephemeral storage above the included allowance if configured, and data transfer. Image pull and startup time contribute to task duration. A task definition/cluster do not mean a task is continuously running. | Yes. Run one task at a time and stop/confirm it exits. No ECS service is defined. | Stop any running task; confirm no task remains RUNNING. Cluster/task definition are stack resources. A task that exits is not billed as running after termination, but accrued usage remains. |
| Public task IPv4 and internet egress | Public IPv4 address-hours and data transfer out. A public IP is assigned to the task ENI while it runs. | Usually needed because the application fetches public market/news sources and sends SMTP. | Stop tasks and confirm task ENIs/public IPv4 allocations are released. This template does not create the VPC/network resources. |
| NAT gateway, if present in supplied network | Hourly gateway charge plus per-GB processing and data transfer; can dominate a short demo if left running. | No, if approved public subnets with public IP assignment and an internet gateway are used. | Not created by this stack. Do not delete a shared NAT gateway. If created solely for this demo, confirm owner, dependencies, and routes before deleting it. |
| CloudWatch log group `/ecs/daily-market-digest` | Log ingestion, storage, and queries. Retention is 30 days. | Yes for diagnosing the controlled task. | The log group has `DeletionPolicy: Retain`; after stack deletion, inspect/export anything needed, then delete the log group manually to stop ongoing storage charges. |
| DynamoDB run-state table | On-demand reads/writes, stored data, and point-in-time recovery (PITR). The table has PITR enabled and `DeletionPolicy: Retain`. | Yes, for duplicate-run coordination and delivery safety. | Stack deletion retains the table. If ending the demo, decide explicitly whether to retain history. If removing it, inspect state/backups first, then disable PITR/delete the table and review any on-demand backups. Deleting a table can create a recoverable system backup with its own retention behavior; verify current billing/docs. |
| S3 history bucket and objects | Current and noncurrent version storage, requests, retrieval, and data transfer. Versioning is on. Lifecycle expires noncurrent report versions after 180 days while preserving the newest three versions; it does not expire application state. | Yes for persisted history, PDF, and SQLite state. | Bucket has `DeletionPolicy: Retain`. Decide what to preserve. If removing, empty **all versions and delete markers** (the S3 console Empty action can do this), then delete the bucket. `aws s3 rm --recursive` alone does not remove all version history. Do not remove required state before the run-state/history retention decision. |
| Secrets Manager email secret (existing prerequisite) | Per-secret storage and API calls; customer-managed KMS keys, if used, may add charges. Rotation is not configured by this template. | Yes for AWS task email. | Not created/owned by this stack. After confirming no other consumer, schedule deletion in Secrets Manager (normally has a recovery window) or follow your organization's rotation/removal process. Never paste its value in logs or this document. |
| IAM task, execution, scheduler, and GitHub roles | No direct IAM role charge. Overbroad or misconfigured permissions are a security risk. | Yes for the AWS workflow/task. | Roles created by the stack should be removed with it; inspect dependencies if deletion fails. The AWS-managed ECS execution policy and GitHub OIDC provider may be shared/pre-existing—do not remove them casually. |
| EventBridge Scheduler schedule | Invocation count; this demo's weekday schedule is low-volume, but it can trigger Fargate work and email. | No for a manual-only demo. | Set `ScheduleState=DISABLED` before create and keep disabled. If enabled for a controlled test, disable it before teardown and verify it is disabled. |
| Supplied VPC, subnets, routes, security group, internet gateway | Existing network resources may have their own recurring charges, especially NAT, plus public IPv4/transfer. | Yes, appropriate egress is needed. | External to this stack. Never delete shared networking as part of stack teardown. The demo security group should have no inbound rules; allow only necessary outbound DNS/HTTPS/SMTP routes under the network owner's policy. |
| GitHub Actions and repository secrets | Hosted-runner minutes/artifacts are GitHub-side; AWS ECR/CloudFormation API use may create AWS usage. | Needed only to publish/update through the current workflow. | Disable the independent fallback workflow for the demo. Remove temporary repository secrets/variables only if they were created exclusively for this demo and no longer needed. No GitHub Actions changes are required for this checklist. |

CloudFormation explicitly retains the ECR repository, S3 bucket, DynamoDB table, and CloudWatch log group. Deleting the stack therefore does **not** mean all data-bearing or billable resources have been deleted. Retained resources continue to exist and can continue to incur charges.

## 3. Cost estimate approach and main risks

### Verified pricing mechanics and unknown costs

The resource settings and pricing references below confirm the cost categories and billing mechanics to account for; they do not establish what this demo will cost. For example, Fargate usage depends on task resources and runtime, versioned S3 data is stored per version, and DynamoDB PITR has a separate storage-related charge. Recheck the linked official pricing pages for current terms. The actual amount remains unknown until the region, run count and duration, traffic and stored data, route (including whether a NAT gateway is used), account-specific pricing/free-tier eligibility, and any shared resources are known. No total is estimated here.

Use the [AWS Pricing Calculator](https://calculator.aws/#/) for a 3–7 day estimate after those inputs are established, comparing candidate regions with the same assumptions. Include:

- One Fargate task at 1 vCPU and 2 GiB, with realistic image pull/startup plus task runtime; separately enter the number of runs. Fargate bills task resources by duration (with a minimum billing interval); check current rules and ephemeral-storage allowance for the selected region.
- Public IPv4 address-hours for the task ENI and expected internet egress. If using NAT, include gateway hours **and** processed GB; a NAT gateway can cost more than the workload for a small demo.
- CloudWatch log ingestion and 30-day retention; ECR image storage for every immutable tag retained; S3 current and noncurrent versions, requests, and transfer.
- DynamoDB on-demand requests, table storage, PITR based on protected table size, and any on-demand backups.
- Secrets Manager secret-months/API calls and any customer-managed KMS key; Scheduler invocations if enabled; cross-region or internet data transfer if applicable.
- Any shared network resources that the demo relies on. They may keep billing after this stack is deleted.

The least-cost safe demo is: one selected region, existing approved public subnet(s) with a public IP on the task, an outbound-only security group, no NAT gateway created solely for this demo, one manual task, both schedules disabled, short task/log inspection, and prompt teardown. This still has public IPv4, Fargate, storage, and transfer costs. Never use a public subnet/security group without the network owner's approval.

Create a small cost budget and actual-cost alert before deploying, if permitted. A budget is an alerting tool, **not a spending cap**; billing data and alerts can lag. Keep checking Cost Explorer/Billing during and after the demo. A one-time estimate is not a guarantee.

AWS Budgets are separate from this project's CloudFormation stack and are not automatically removed when the demo stack is deleted. AWS's current [Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/) says basic budgets without actions are free; optional budget actions or budget reports may incur charges. Check the account's existing budgets before creating one, and review any demo-only budget during teardown. Do not delete a shared or account-wide budget as part of demo cleanup.

## 4. Safe short-demo configuration

1. Choose a region where the required services and approved network are available. Use the region selector in the AWS Pricing Calculator; compare full resource/network prices rather than choosing from a generic “cheapest region” claim.
2. Review the template and current workflow. At stack creation explicitly set `ScheduleState=DISABLED` and `ImageTag=bootstrap`. `bootstrap` is a placeholder reference: do not start a task from it. The deploy workflow should run its tests, publish a reviewed immutable tag, then update the stack's `ImageTag`. Confirm the resulting task definition references that exact tag before running.
3. Check the current deploy workflow's inputs and OIDC role trust in the account/repository. The stack must exist before the deploy workflow can update it. Do not enable the email distribution or fallback merely to verify image publishing.
4. Use an existing approved subnet and security group. Require no inbound rules. Permit only required outbound traffic. The application needs public HTTPS sources and SMTP submission; DNS and SMTP port requirements must be confirmed with the network owner. A security group cannot express a domain-name allowlist, so agree on the practical egress policy first.
5. Keep the EventBridge schedule disabled. Disable the GitHub fallback schedule through the Actions UI as well; it is independent of the CloudFormation schedule parameter. Check that neither workflow is queued/running before testing.
6. Run exactly one ECS task manually after the immutable image is present. Watch CloudWatch logs and task exit status. Use a controlled mailbox and verify the intended message once. Do not automatically retry if logs/state show `email_pending` or `email_ambiguous`; first determine whether SMTP accepted the message and follow documented manual recovery.
7. If scheduled execution is an explicit demo objective, first complete the controlled manual test. Then enable the AWS schedule for the minimum necessary period, observe a single run, and disable it immediately after. Keep the GitHub fallback disabled unless intentionally testing the fallback path separately.
8. Keep a written record of stack name/region, resource names, the immutable image tag, start/end time, controlled recipient, and which retained history/backups are being kept. Do not record credentials.

## 5. Ordered teardown checklist

Perform in this order, in the same AWS account and region used for the demo. Confirm ownership before changing any shared resource. Resource deletion and data erasure are irreversible; retain required history first.

- [ ] **Disable triggers first.** Update the stack's `ScheduleState` to `DISABLED`; verify the Scheduler schedule is disabled in the console. In GitHub Actions, disable the Daily Market Digest fallback workflow and confirm no run is queued or active.
- [ ] **Stop compute.** In ECS, inspect the demo cluster's tasks. Stop any task still running and wait for it to reach STOPPED. Check for leftover task ENIs/public IPv4 addresses after the task releases them.
- [ ] **Capture what must be kept.** Export/download any required PDF/report/history and document the DynamoDB state and backup decision. Check S3 versions and delete markers. Never blindly clear the shared SQLite/history bucket.
- [ ] **Delete the CloudFormation stack.** In the correct region, open CloudFormation, select `daily-market-digest`, review the stack/resources and retained-resource behavior, then choose Delete. Wait for `DELETE_COMPLETE`; investigate and resolve `DELETE_FAILED` rather than force-deleting blindly. Stack deletion cannot be stopped after it starts.
- [ ] **Inspect resources retained by the stack.** The ECR repository, S3 bucket, DynamoDB table, and CloudWatch log group are retained. Verify each in its service console and remove only after the data-retention decision. Stack deletion may also leave resources after a failed deletion; inspect the stack events/resources.
- [ ] **Clean ECR if no longer needed.** Review image tags/digests and any deployment rollback need. Deleting images or the repository can permanently remove artifacts needed for rollback. Delete only after confirming they are no longer needed; then delete the repository if appropriate. Keep a reviewed image only if there is a concrete reason and owner for its ongoing storage.
- [ ] **Clean S3 only if history is no longer required.** In the S3 console, inspect current objects, noncurrent versions, and delete markers; use Empty to remove all versions and markers, then delete the bucket. This is permanent. If keeping history, leave the bucket and accept its continuing storage cost; existing lifecycle only expires noncurrent report versions after 180 days (keeping three) and does not delete state objects.
- [ ] **Resolve DynamoDB retention explicitly.** If retaining run history, leave the table and PITR and record an owner/review date. If deleting, inspect its contents and backup list, then disable PITR/delete the table and separately review/delete on-demand backups if no longer required. Do not assume CloudFormation removed it or that deleting PITR is harmless.
- [ ] **Delete retained logs if no longer needed.** Review/export necessary logs, then delete `/ecs/daily-market-digest`. The configured 30-day retention applies only while the group exists; retention does not remove the retained log group after stack deletion.
- [ ] **Review the email secret.** Confirm the secret was created for this demo and has no other consumer. Rotate or schedule deletion using the organization's policy; do not force-delete merely to get immediate cleanup.
- [ ] **Review identity resources.** Confirm stack-created IAM roles are gone. The GitHub OIDC provider and AWS-managed policies can be shared; remove a provider only if it was created solely for this demo and its owner approves. Remove demo-only GitHub variables/secrets from repository settings if no longer needed.
- [ ] **Review AWS Budgets separately.** Budgets are not part of this CloudFormation stack and stack deletion does not remove them. Review and remove only a demo-only budget after checking whether it has actions or reports; preserve shared/account-wide budgets. See [AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/).
- [ ] **Review external networking.** Check for NAT gateways, Elastic IPs/public IPv4 allocations, ENIs, or routes that were created specifically for this demo. This CloudFormation stack did not create them. Remove only demo-owned resources after confirming there are no dependencies; never remove shared VPC/subnets/routes/security groups.
- [ ] **Verify billing after cleanup.** Review Cost Explorer/Billing by service and region over the next several days. Billing data is delayed; investigate residual Fargate, NAT, IPv4, ECR, S3, DynamoDB/PITR/backup, CloudWatch, Secrets Manager, or transfer charges.

## 6. Before-deployment checks

- [ ] A human has reviewed the template, workflow, this cost plan, and the account's expected charges.
- [ ] A responsible account owner approved the region, network, outbound rules, and supplied subnet/security-group IDs.
- [ ] An estimate was prepared in the AWS Pricing Calculator using realistic runtime, storage, network, and retention inputs.
- [ ] A cost budget/alert and billing access are ready; all participants understand alerts do not cap spending and may be delayed.
- [ ] Secret JSON keys and IAM trust/permissions have been validated without exposing secret values.
- [ ] The initial stack parameters explicitly disable the AWS schedule and use the bootstrap image tag; no task will start until the workflow updates to an immutable reviewed tag.
- [ ] The independent GitHub fallback schedule is disabled for the demo, or its separate behavior and email risk have been deliberately reviewed.
- [ ] The market constituents have not been described as NSE-verified unless separately verified against the current official list. No fabricated market data is used.
- [ ] A controlled recipient and manual recovery owner are identified for the one-task email check.
- [ ] A teardown owner and calendar reminder for the exact demo end date are assigned.

## 7. Official references

Pricing changes by region, usage, and account eligibility. Recheck these pages and the calculator on the day of the demo; values shown in examples are not a quote.

- [AWS Pricing Calculator](https://calculator.aws/#/)
- [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/)
- [Amazon VPC pricing (NAT and public IPv4)](https://aws.amazon.com/vpc/pricing/)
- [Amazon DynamoDB pricing (including PITR and backups)](https://aws.amazon.com/dynamodb/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) and [S3 versioning workflows](https://docs.aws.amazon.com/AmazonS3/latest/userguide/versioning-workflows.html)
- [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/) and [deleting a secret](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html)
- [Amazon EventBridge pricing, including Scheduler](https://aws.amazon.com/eventbridge/pricing/)
- [CloudFormation DeletionPolicy and retained-resource behavior](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html)
- [Deleting a CloudFormation stack](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-delete-stack.html)
- [AWS Budgets best practices and update frequency](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html)
