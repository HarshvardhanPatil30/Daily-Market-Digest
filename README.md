# Daily Market Digest

An internal, Python-based prototype that produces a polished Indian market-digest PDF. It uses deterministic Python calculations and public data adapters; optional language generation is strictly local through Ollama. It contains no Gemini, OpenAI, or hosted-LLM integration or API key.

## Status and safety

- `run --demo` is a fully offline, clearly labelled fictional fixture workflow.
- `run` requires the installed public-source dependencies and currently accessible Yahoo Finance / Google News RSS. It refuses unverified index sessions rather than filling gaps.
- Values are calculated in Python from current/prior closes. The bundled Nifty 50 universe is a reference list and should be refreshed against the NSE before production use. `nsepython` is documented as an optional validation dependency; the working fallback is yfinance because public NSE endpoints can change.
- The report is a prototype for internal use, not investment advice or production financial infrastructure.

## Setup

Python 3.9+ is supported (3.12 is preferred when available).

### Run in VS Code

1. Extract `daily_market_digest_vscode.zip`, then open the extracted **daily_market_digest** folder in VS Code (`File` → `Open Folder`).
2. Install the Microsoft **Python** VS Code extension if prompted.
3. Open VS Code's terminal (`Terminal` → `New Terminal`) and create/select the project virtual environment:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate
```

4. In the VS Code status bar, select the interpreter in `.venv`, then run the install and demo commands below. The generated report opens from the `reports` folder.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For local AI, install [Ollama](https://ollama.com), then choose a model appropriate to your machine. For example, after reviewing disk/RAM impact:

```bash
ollama pull qwen2.5:3b
# put OLLAMA_MODEL=qwen2.5:3b in .env
```

The application does not download models automatically. Without Ollama, it uses conservative deterministic narrative and education fallbacks and records a disclosure.

## Commands

```bash
python main.py --help
python main.py run --demo
python main.py run
python main.py run --date 2026-10-20
python main.py validate-sources
python main.py status
python main.py history
```

Demo PDFs go to `reports/YYYY/MM/DD/market_digest_YYYY-MM-DD.pdf`, SQLite history to `data/market_digest.db`, and logs to `logs/` by default. Demo records are intentionally fictional and cannot be used by live mode.

## Tests

```bash
pytest -q
```

Tests mock or avoid external services; they do not require keys, internet, or Ollama.

## Windows scheduling (only after manual validation)

The target is Monday–Friday at 16:15 local Windows time. First inspect the generated command:

```bash
python main.py setup-task
```

On Windows only, after successfully generating and reviewing a manual report, explicitly create/replace the task:

```bash
python main.py setup-task --confirm
```

Normal runs never create or alter a scheduled task. The Task Scheduler task runs only while the computer is awake; use the Scheduler UI to inspect, run, disable, or delete **Daily Market Digest**. Missed runs require appropriate Task Scheduler settings and cannot occur while the computer is shut down. Keep `.env` next to the project; no secret is embedded in the task definition.

## Architecture

`Orchestrator` coordinates eight focused agents: index retrieval, Nifty movers, RSS news, company updates, factual narrative, financial education, report assembly, and workflow control. `services/validation.py` owns calculations/data checks; `services/pdf_generator.py` performs atomic PDF generation and heading/readability validation; `services/database.py` retains run and output metadata via parameterized SQLite queries.

## Troubleshooting

- `yfinance is not installed`: activate the venv and run `pip install -r requirements.txt`.
- No session for a date: choose an actual completed NSE trading session; public data can lag/omit exchange holidays.
- Ollama unavailable: start `ollama serve`, verify `ollama list`, and set `OLLAMA_MODEL` to an installed model. The report still runs with the disclosed fallback.
- RSS unavailable: check connectivity; live reports retain only verifiable data and may fail in strict mode when essential data is missing.

## Automated weekday email

The AWS primary scheduler with GitHub Actions fallback described below supersedes the earlier GitHub-only scheduler. Use that configuration if the MacBook may be off; do not enable a second independent GitHub workflow that generates the primary report at 16:00.

## AWS primary scheduler with GitHub Actions fallback

The normal market-data, agent, SQLite, and ReportLab backend is unchanged. The automation wrapper (`scripts/run_automated.py`) calls the existing `python main.py run` and `python main.py email-latest` commands. AWS EventBridge Scheduler starts an ECS Fargate task at 16:00 Asia/Kolkata on weekdays. GitHub Actions checks the shared DynamoDB status every 15 minutes after 16:30 and only takes over if no AWS run exists, AWS recorded a failure, or the AWS lease has expired. A completed/email-sent state prevents the normal duplicate fallback.

### AWS resources and first-time setup

1. Create a Gmail App Password (with Google 2-Step Verification enabled). Store a JSON secret in AWS Secrets Manager with keys `EMAIL_FROM`, `EMAIL_TO`, and `GMAIL_APP_PASSWORD`. Never commit these values.
2. Ensure the AWS account has the GitHub Actions OIDC identity provider `token.actions.githubusercontent.com` (audience `sts.amazonaws.com`).
3. Deploy `infra/aws-cloudformation.yml` in the same AWS region used by GitHub Actions. Supply subnet IDs with outbound internet access, an outbound-only security group, the Secrets Manager ARN, the OIDC provider ARN, and the GitHub repository (`owner/repo`). Public subnet/NAT egress is needed for Yahoo Finance, Google News and Gmail SMTP; no inbound rule is required.
   Example command (replace every placeholder; run from the project root after configuring AWS CLI credentials):

   ```bash
   aws cloudformation deploy \
     --template-file infra/aws-cloudformation.yml \
     --stack-name daily-market-digest \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       SubnetIds="subnet-PLACEHOLDER1,subnet-PLACEHOLDER2" \
       SecurityGroupIds="sg-PLACEHOLDER" \
       EmailSecretArn="arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET-NAME" \
       GitHubOidcProviderArn="arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com" \
       GitHubRepository="OWNER/REPO" \
       GitHubBranch="main"
   ```

   After deployment, get the outputs with `aws cloudformation describe-stacks --stack-name daily-market-digest --query 'Stacks[0].Outputs' --output table`.
4. Copy the CloudFormation output `GitHubActionsRoleArn` into GitHub repository secret `AWS_ROLE_ARN`. Add repository variables `AWS_REGION` for the stack region and `DMD_STATE_BUCKET` using the CloudFormation `HistoryBucketName` output. Add GitHub secrets `EMAIL_FROM`, `EMAIL_TO`, and `GMAIL_APP_PASSWORD` for the fallback runner.
5. Push the project to the configured `main` branch. The `Build and publish Daily Market Digest image` workflow publishes the container to ECR. The first image must be published before the first successful ECS run.
6. Check the EventBridge schedule, ECS task logs in CloudWatch (`/ecs/daily-market-digest`), GitHub Actions logs, the DynamoDB table `daily-market-digest-run-state`, and the S3 bucket output by CloudFormation. Trigger the fallback workflow manually only after 16:30 IST; before then it intentionally skips.

### Coordination and limits

- DynamoDB is the cross-run lock/status source. SQLite remains the application history and is downloaded/uploaded at `state/market_digest.db` in the private, versioned S3 bucket. Generated PDFs are also copied to S3.
- The GitHub fallback uses AWS OIDC, not long-lived AWS access keys. Its role is scoped to the configured repository branch and the project's state/storage/ECR resources.
- The GitHub watchdog checks every 15 minutes from 16:30 through 18:15 IST. If AWS is still within its 45-minute lease, it waits rather than starting a concurrent run.
- SMTP does not provide true exactly-once delivery. The shared state prevents normal duplicate runs, but a crash after Gmail accepts a message and before the success state is recorded can leave an ambiguous delivery outcome.
- The workflow runs only on weekdays, not on the Indian exchange holiday calendar. On holidays, live data validation may fail; the app must not invent missing prices.
- This AWS setup may incur charges for ECS/Fargate, CloudWatch, S3, DynamoDB and networking. Review AWS pricing and set billing alerts before enabling it.

