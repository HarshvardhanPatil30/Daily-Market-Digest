"""Shared AWS state for cloud-first scheduling and GitHub Actions failover."""

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError


TERMINAL_STATUSES = {"completed", "email_sent"}
LEASE_SECONDS = int(os.getenv("DMD_RUN_LEASE_SECONDS", "2700"))


def utc_now():
    return datetime.now(timezone.utc)


class AutomationState:
    def __init__(self, table_name=None, bucket_name=None, region_name=None):
        self.table_name = table_name or os.getenv("DMD_STATE_TABLE", "")
        self.bucket_name = bucket_name or os.getenv("DMD_STATE_BUCKET", "")
        self.region_name = (
            region_name
            or os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("AWS_REGION")
        )

        if not self.table_name or not self.bucket_name:
            raise RuntimeError(
                "Set DMD_STATE_TABLE and DMD_STATE_BUCKET for automated runs."
            )

        self.dynamodb = boto3.resource(
            "dynamodb", region_name=self.region_name
        )
        self.table = self.dynamodb.Table(self.table_name)
        self.s3 = boto3.client("s3", region_name=self.region_name)

    def get(self, run_date):
        return self.table.get_item(
            Key={"run_date": str(run_date)}
        ).get("Item")

    def is_terminal(self, run_date):
        item = self.get(run_date)
        return bool(item and item.get("status") in TERMINAL_STATUSES)

    def claim(self, run_date, owner, now_epoch=None):
        """Atomically claim a run and return its unique token, or None."""
        if now_epoch is None:
            now_epoch = int(utc_now().timestamp())

        now_iso = utc_now().isoformat()
        token = str(uuid4())

        try:
            self.table.update_item(
                Key={"run_date": str(run_date)},
                UpdateExpression=(
                    "SET #status=:running, #owner=:owner, "
                    "claim_token=:token, started_at=:updated, "
                    "updated_at=:updated, lease_until=:lease "
                    "ADD attempt_count :one"
                ),
                ConditionExpression=(
                    "attribute_not_exists(run_date) OR "
                    "#status=:failed OR "
                    "(#status=:running AND lease_until < :now)"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#owner": "owner",
                },
                ExpressionAttributeValues={
                    ":running": "running",
                    ":failed": "failed",
                    ":owner": owner,
                    ":token": token,
                    ":now": now_epoch,
                    ":lease": now_epoch + LEASE_SECONDS,
                    ":updated": now_iso,
                    ":one": 1,
                },
            )
            return token

        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                return None
            raise

    def renew_lease(self, run_date, owner, token):
        """Extend the lease only while this exact attempt still owns it."""
        now_epoch = int(utc_now().timestamp())

        self.table.update_item(
            Key={"run_date": str(run_date)},
            UpdateExpression="SET lease_until=:lease, updated_at=:now",
            ConditionExpression=(
                "#status=:running AND #owner=:owner "
                "AND claim_token=:token AND lease_until >= :now_epoch"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#owner": "owner",
            },
            ExpressionAttributeValues={
                ":running": "running",
                ":owner": owner,
                ":token": token,
                ":lease": now_epoch + LEASE_SECONDS,
                ":now": utc_now().isoformat(),
                ":now_epoch": now_epoch,
            },
        )

    def mark_email_sent(
        self, run_date, owner, token, execution_id, trading_date, pdf_key
    ):
        """Record successful SMTP submission while the claim is still valid."""
        now = utc_now()
        now_epoch = int(now.timestamp())

        self.table.update_item(
            Key={"run_date": str(run_date)},
            UpdateExpression=(
                "SET #status=:sent, updated_at=:now, email_sent_at=:now, "
                "execution_id=:execution, trading_date=:trading, pdf_key=:pdf "
                "REMOVE lease_until"
            ),
            ConditionExpression=(
                "#owner=:owner AND #status=:running "
                "AND claim_token=:token AND lease_until >= :now_epoch"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#owner": "owner",
            },
            ExpressionAttributeValues={
                ":sent": "email_sent",
                ":now": now.isoformat(),
                ":execution": execution_id,
                ":trading": str(trading_date),
                ":pdf": pdf_key,
                ":owner": owner,
                ":token": token,
                ":running": "running",
                ":now_epoch": now_epoch,
            },
        )

    def complete(self, run_date, owner, token):
        self.table.update_item(
            Key={"run_date": str(run_date)},
            UpdateExpression=(
                "SET #status=:completed, updated_at=:now REMOVE lease_until"
            ),
            ConditionExpression=(
                "#owner=:owner AND #status=:sent AND claim_token=:token"
            ),
            ExpressionAttributeNames={
                "#status": "status",
                "#owner": "owner",
            },
            ExpressionAttributeValues={
                ":completed": "completed",
                ":sent": "email_sent",
                ":owner": owner,
                ":token": token,
                ":now": utc_now().isoformat(),
            },
        )

    def fail(self, run_date, owner, token, error):
        """Record failure only if this attempt still owns the active claim."""
        try:
            self.table.update_item(
                Key={"run_date": str(run_date)},
                UpdateExpression=(
                    "SET #status=:failed, updated_at=:now, #error=:error "
                    "REMOVE lease_until"
                ),
                ConditionExpression=(
                    "#owner=:owner AND #status=:running AND claim_token=:token"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#owner": "owner",
                    "#error": "error",
                },
                ExpressionAttributeValues={
                    ":failed": "failed",
                    ":now": utc_now().isoformat(),
                    ":error": str(error)[:2000],
                    ":owner": owner,
                    ":token": token,
                    ":running": "running",
                },
            )
        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code")
                != "ConditionalCheckFailedException"
            ):
                raise

    def restore_database(self, local_path):
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.s3.download_file(
                self.bucket_name,
                "state/market_digest.db",
                str(local_path),
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def save_database(self, local_path):
        local_path = Path(local_path)
        if local_path.is_file():
            self.s3.upload_file(
                str(local_path),
                self.bucket_name,
                "state/market_digest.db",
            )

    def save_pdf(self, local_path, trading_date):
        local_path = Path(local_path)
        if not local_path.is_file():
            raise FileNotFoundError(
                f"Generated PDF not found: {local_path}"
            )

        key = f"reports/{trading_date:%Y/%m/%d}/{local_path.name}"
        self.s3.upload_file(
            str(local_path),
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
        return key