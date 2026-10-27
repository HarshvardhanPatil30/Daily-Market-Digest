"""Shared AWS state for cloud-first scheduling and GitHub Actions failover.

The DynamoDB row is the cross-run lock. SQLite remains the application's
report history; its file is synchronized to S3 between executions.
"""
from datetime import datetime, timezone
import os

import boto3
from botocore.exceptions import ClientError

TERMINAL_STATUSES = {"completed", "email_sent"}
LEASE_SECONDS = int(os.getenv("DMD_RUN_LEASE_SECONDS", "2700"))  # 45 minutes


class AutomationState:
    def __init__(self, table_name=None, bucket_name=None, region_name=None):
        self.table_name = table_name or os.getenv("DMD_STATE_TABLE", "")
        self.bucket_name = bucket_name or os.getenv("DMD_STATE_BUCKET", "")
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
        if not self.table_name or not self.bucket_name:
            raise RuntimeError("Set DMD_STATE_TABLE and DMD_STATE_BUCKET for automated runs.")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
        self.table = self.dynamodb.Table(self.table_name)
        self.s3 = boto3.client("s3", region_name=self.region_name)

    def get(self, run_date):
        return self.table.get_item(Key={"run_date": str(run_date)}).get("Item")

    def is_terminal(self, run_date):
        item = self.get(run_date)
        return bool(item and item.get("status") in TERMINAL_STATUSES)

    def claim(self, run_date, owner, now_epoch=None):
        """Claim a date once, or recover a failed/stale AWS-owned execution."""
        now_epoch = int(now_epoch or datetime.now(timezone.utc).timestamp())
        now_iso = datetime.now(timezone.utc).isoformat()
        values = {
            ":running": "running", ":failed": "failed", ":aws": "aws",
            ":owner": owner, ":now": now_epoch, ":lease": now_epoch + LEASE_SECONDS,
            ":updated": now_iso, ":one": 1,
        }
        try:
            self.table.update_item(
                Key={"run_date": str(run_date)},
                UpdateExpression=(
                    "SET #status=:running, #owner=:owner, started_at=:updated, "
                    "updated_at=:updated, lease_until=:lease ADD attempt_count :one"
                ),
                ConditionExpression=(
                    "attribute_not_exists(run_date) OR "
                    "(#status=:failed AND #owner=:aws) OR "
                    "(#status=:running AND lease_until < :now AND #owner=:aws)"
                ),
                ExpressionAttributeNames={"#status": "status", "#owner": "owner"},
                ExpressionAttributeValues=values,
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def mark_email_sent(self, run_date, owner, execution_id, trading_date, pdf_key):
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={"run_date": str(run_date)},
            UpdateExpression=(
                "SET #status=:sent, updated_at=:now, email_sent_at=:now, "
                "execution_id=:execution, trading_date=:trading, pdf_key=:pdf REMOVE lease_until"
            ),
            ConditionExpression="#owner=:owner AND #status=:running",
            ExpressionAttributeNames={"#status": "status", "#owner": "owner"},
            ExpressionAttributeValues={
                ":sent": "email_sent", ":now": now, ":execution": execution_id,
                ":trading": str(trading_date), ":pdf": pdf_key, ":owner": owner,
                ":running": "running",
            },
        )

    def complete(self, run_date, owner):
        self.table.update_item(
            Key={"run_date": str(run_date)},
            UpdateExpression="SET #status=:completed, updated_at=:now REMOVE lease_until",
            ConditionExpression="#owner=:owner AND #status=:sent",
            ExpressionAttributeNames={"#status": "status", "#owner": "owner"},
            ExpressionAttributeValues={
                ":completed": "completed", ":sent": "email_sent", ":owner": owner,
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )

    def fail(self, run_date, owner, error):
        # Never overwrite a known successful email outcome with a later sync error.
        item = self.get(run_date)
        if item and item.get("owner") == owner and item.get("status") == "email_sent":
            return
        try:
            self.table.update_item(
                Key={"run_date": str(run_date)},
                UpdateExpression="SET #status=:failed, updated_at=:now, error=:error REMOVE lease_until",
                ConditionExpression="#owner=:owner AND #status=:running",
                ExpressionAttributeNames={"#status": "status", "#owner": "owner"},
                ExpressionAttributeValues={
                    ":failed": "failed", ":now": datetime.now(timezone.utc).isoformat(),
                    ":error": str(error)[:2000], ":owner": owner, ":running": "running",
                },
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def restore_database(self, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.s3.download_file(self.bucket_name, "state/market_digest.db", str(local_path))
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def save_database(self, local_path):
        if local_path.is_file():
            self.s3.upload_file(str(local_path), self.bucket_name, "state/market_digest.db")

    def save_pdf(self, local_path, trading_date):
        if not local_path.is_file():
            raise FileNotFoundError(f"Generated PDF not found: {local_path}")
        key = f"reports/{trading_date:%Y/%m/%d}/{local_path.name}"
        self.s3.upload_file(str(local_path), self.bucket_name, key,
                           ExtraArgs={"ContentType": "application/pdf"})
        return key
