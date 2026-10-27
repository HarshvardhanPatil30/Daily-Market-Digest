# Deployment readiness audit

**Reviewed:** 2026-10-27
**Status:** Not ready for unattended production deployment. No AWS resources were created, no GitHub push/workflow was triggered, and no email was sent. `.env` was not opened.

## Nifty 50 membership verification

- **Checked:** 2026-10-27.
- **Official NSE page:** https://www.nseindia.com/static/products-services/indices-nifty50-index. It links “Download List of Nifty 50 stocks (.csv)” and shows the page updated 22/04/2026.
- **Official CSV URL linked by NSE:** https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv.
- **Access limitation:** the available web retrieval tool rejected the NSE CSV response (`400 Unsupported content-type: text/csv`). The NSE tracker page did not expose its dynamically loaded constituent table in the retrieved page text.
- **Additional official source checked:** https://www.niftyindices.com/Factsheet/ind_nifty50.pdf, dated 30 September 2026. It confirms 50 constituents and names only the top 10 by weight, so it cannot establish membership for all configured symbols.
- **Result:** no additions, removals, renames, or symbol-format differences are claimed. The complete configured set could not be compared with an accessible current official list. No symbols were changed; refresh and verify from the NSE CSV before production use.

## Changes made

- Made the fallback runner's IST date derivation explicit. `datetime.now(IST)` was already IST-aware, so the previous audit overstated this as a functional bug fix; this expression documents the state key's timezone.
- Extended the watchdog schedule to run at 18:00 and 18:15 IST, matching the documented fallback window.
- Tightened `.dockerignore` to exclude local agent/config folders, virtual environments, tests, and all env files except the non-secret `.env.example`.
- Rejected non-finite prices and derived market values before they can enter calculations and reports.
- Replaced the placeholder CLI date test with an actual invalid-date check and added regression coverage for the IST boundary and non-finite prices.
- Added a test gate before image publication, pinned workflow actions to full commit SHAs, and preserved OIDC credentials for the publishing job.
- Replaced ECS's mutable `latest` reference with a CloudFormation `ImageTag` parameter, unique immutable image tags, and an image-publish-then-stack-update workflow. New stacks must explicitly disable the schedule and set the bootstrap tag; backward-compatible defaults preserve current stacks.
- Retained S3 history, DynamoDB run state, ECR, and CloudWatch log group on stack deletion/replacement. Added a 180-day noncurrent-version lifecycle for `reports/` that keeps the newest three older versions and never expires current reports or `state/` objects.
- Added an `email_pending` no-retry barrier before SMTP and an `email_ambiguous` state after caught failures. Both statuses prevent fallback auto-claims.
- Made live mover collection fail when any of the bundled 50 constituent rows is missing or is not for the requested date, rather than publishing rankings from partial coverage.
- Quoted the Scheduler `FlexibleTimeWindow.Mode` value as `'OFF'`; cfn-lint showed the unquoted YAML token was being interpreted as boolean `false`.
- Kept `latest` as the sole ECR mutability exclusion for existing deployment compatibility; release tags remain immutable and are the only tags used by the updated release workflow.

## Readiness findings

### Application and automation state

- The local SQLite history and local `email-latest` flow remain available. The AWS wrapper restores/saves SQLite in S3 and uses DynamoDB conditional claims with a lease and owner token.
- `email_pending` is written before invoking SMTP. A process crash leaves a blocking pending state; a caught SMTP/process failure becomes blocking `email_ambiguous`. Neither state is automatically retryable. Check recipient delivery and logs before a human authorizes recovery. SMTP still cannot guarantee exactly-once delivery.
- There is no built-in recovery command for pending/ambiguous rows. Recovery requires an operator to inspect delivery/log evidence and deliberately update the DynamoDB row; approve and record that procedure for the target account before operations begin.
- `state/market_digest.db` is a single shared object. Concurrent writes are prevented by the run claim in normal flow; manual or out-of-band edits can still cause divergence.
- The watchdog can only run its fallback if required GitHub variables/secrets, AWS OIDC trust, and network egress are configured correctly.

### AWS/GitHub coordination

- Both runners use the same DynamoDB run-date key, now explicitly based on IST. Fallback runs are serialized by GitHub Actions concurrency and DynamoDB conditional claims.
- GitHub's scheduled actions can be delayed or skipped by platform scheduling behavior. The manual workflow dispatch intentionally still honors the 16:30 IST deadline.
- ECR tags are immutable except the legacy `latest` alias, which remains mutable for migration compatibility and is not used by new CI releases. Releases use `<full-commit-sha>-<run-id>-<run-attempt>` so separate dispatches of the same commit cannot collide. ECS references the `ImageTag` CloudFormation parameter, and the release workflow updates that parameter only after tests pass and the image push succeeds. It explicitly passes all other stack parameters with `UsePreviousValue=true`, including `ScheduleState`.
- Bootstrap is intentionally staged: create a new stack with `ScheduleState=DISABLED` and `ImageTag=bootstrap`; set GitHub OIDC role/region; push reviewed code so CI publishes the initial immutable image and updates the task definition; inspect the update and a controlled ECS run; enable the schedule only after human approval. The template defaults preserve existing stack behavior (`ENABLED`/`latest`) so an upgrade does not silently disable an established schedule; new deployments must pass both bootstrap values explicitly.
- The release workflow requires the stack and role to exist first. It can update only the named stack through its scoped CloudFormation role statement; actual effective scope must still be reviewed in the target account.

### Docker and Actions

- Docker build context excludes `.env`, local credentials/config folders, git history, local state, generated reports/logs, tests, and virtual environments.
- Third-party actions in both workflows are pinned to full SHAs, with release comments. OIDC is limited to the publishing job and fallback job; the test job has read-only contents permission.
- Reviewed action pins use Node 24 compatible releases: `actions/checkout` v5.0.0 (`08c6903…`), `actions/setup-python` v6.0.0 (`e797f83…`), `aws-actions/configure-aws-credentials` v5.1.0 (`0094301…`), and `actions/upload-artifact` v7.0.2 (`cf430e0…`). Release/tag mappings were checked against upstream release material before pinning.
- The release workflow runs the test suite before image publishing. README-only changes and edits to the separate fallback workflow do not trigger the release workflow; tests and application/build changes do.

### CloudFormation, IAM, secrets, networking, and cost

- IAM is scoped to the run-state table, bucket objects, secret ARN, ECR repository, and task roles where practical. ECR authorization token access necessarily uses `Resource: '*'`. GitHub OIDC trust is limited to one repository branch.
- Verify the supplied security group permits outbound DNS/HTTPS and SMTP submission and has no inbound rules. Fargate tasks use public IPs in the supplied subnets; public egress is needed for market/RSS sources and Gmail. NAT gateways may add ongoing cost if used instead.
- The email secret is injected from Secrets Manager into the ECS container; GitHub fallback uses repository secrets. Keep the secret limited to the required sender, recipient, and Gmail app password, and rotate it if exposed.
- Cost categories: Fargate CPU/memory runtime; DynamoDB on-demand requests and point-in-time recovery; S3 current and retained noncurrent versions; CloudWatch ingestion/storage; ECR image storage/scanning; Secrets Manager storage/API calls; and public internet/NAT egress. Amounts depend on region and usage; estimate from task hours, log volume, stored versions/images, requests, and network topology before activation.
- S3 lifecycle removes only noncurrent `reports/` versions older than 180 days, retaining three newer noncurrent versions. Current reports and all `state/` object versions remain. This trades storage cost for history/rollback protection.
- CloudFormation retains the bucket, table, ECR repository, and log group on stack deletion/replacement. These require explicit manual cleanup and retention ownership. DynamoDB point-in-time recovery remains enabled.
- The fixed resource names and account/region-derived bucket name limit deploying multiple copies in the same account/region.

### Financial data integrity and errors

- Live mode does not synthesize prices. It requires one verified index session and a prior close, and will fail when the source cannot verify the requested session.
- Price arithmetic now rejects NaN and infinite inputs. Index/mover validators reject non-finite closes and percentage changes.
- Yahoo Finance and Google News RSS are public dependencies without a contractual availability guarantee. The bundled Nifty 50 symbols can become stale; refresh and verify the universe against NSE before relying on constituent rankings. Live movers now fail closed unless all 50 configured symbols have one requested-date row and a prior close, but that does not prove the bundled membership itself is current.
- Weekday scheduling does not account for Indian exchange holidays. Holiday runs should fail safely when source data does not match the requested date; monitor logs for repeated failures.
- `nsepython` is installed but the active adapter uses yfinance. Confirm this is intended before production; do not treat package presence as an independent validation source.

## Verification performed

- `.venv312/bin/python -m pytest -q`: **34 passed** on the current checkout. The previous 29 count was stale: a later numeric edge case raised that run to 30; this phase adds four automation/market-data regression cases.
- Isolated `/private/tmp/dmd-cfnlint-venv/bin/cfn-lint infra/aws-cloudformation.yml` with cfn-lint 1.46.0: **0 errors, 0 warnings** after the `OFF` fix.
- `git diff --check`: passed.
- Ruby YAML parser successfully parsed both GitHub workflows and the CloudFormation template. cfn-lint validates local CloudFormation structure, but does not verify deployed-account IAM permissions, OIDC provider configuration, subnet egress, secret existence/key layout, or costs.
- Direct `pytest` and system `python3 -m pytest` were unavailable; the workspace's `.venv312` interpreter ran the suite successfully.
- No live market request, SMTP request, AWS call, deployment, or GitHub push was performed.

## Ordered deployment checklist (stop before deployment)

1. Review this audit and decide whether the remaining delivery ambiguity, data-source limitations, and AWS costs are acceptable.
2. Refresh/verify Nifty membership from NSE and validate a live report for a completed session; inspect every source date, constituent coverage, calculations, and disclosures.
3. Review the pinned action releases and AWS role policy, especially CloudFormation update scope, ECR image push, OIDC branch trust, and runtime secret access.
4. Review subnet/security-group egress, stack retention, S3 lifecycle, DynamoDB recovery, log retention, and account-specific cost estimates. Configure a budget/billing alert.
5. Create the Gmail secret and AWS/GitHub OIDC prerequisites; keep credentials out of source control.
6. Authorized operator creates the stack with `ScheduleState=DISABLED` and `ImageTag=bootstrap`. No automatic scheduled run occurs at this stage.
7. Configure `AWS_ROLE_ARN`, `AWS_REGION`, `DMD_STATE_BUCKET`, and fallback email secrets in GitHub, then push reviewed code to `main`. CI tests, publishes the immutable image, and updates the stack's task definition.
8. Inspect workflow and stack update, run a controlled ECS task, check report/data/logs/state, and verify delivery to a controlled recipient. Do not retry pending/ambiguous email states until delivery is checked.
9. An authorized operator explicitly enables `ScheduleState=ENABLED` after reviewing the stack change set. Monitor schedule, fallback, costs, stored versions, and secret rotation.
