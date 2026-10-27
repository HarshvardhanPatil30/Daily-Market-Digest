from datetime import date
from pathlib import Path

from botocore.exceptions import ClientError

from services.automation_state import AutomationState


class FakeTable:
    def __init__(self):
        self.kwargs = None
        self.item = None
    def update_item(self, **kwargs):
        self.kwargs = kwargs
    def get_item(self, **kwargs):
        return {"Item": self.item} if self.item else {}


class FakeS3:
    def __init__(self):
        self.uploads = []
    def upload_file(self, *args, **kwargs):
        self.uploads.append((args, kwargs))
    def download_file(self, bucket, key, target):
        raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")


class FakeDynamo:
    def __init__(self, table): self._table = table
    def Table(self, name): return self._table


def test_claim_uses_conditional_shared_lock(monkeypatch):
    table = FakeTable()
    s3 = FakeS3()
    monkeypatch.setattr("services.automation_state.boto3.resource", lambda *a, **k: FakeDynamo(table))
    monkeypatch.setattr("services.automation_state.boto3.client", lambda *a, **k: s3)
    state = AutomationState(table_name="table", bucket_name="bucket", region_name="us-east-1")
    assert state.claim(date(2026, 10, 22), "github-fallback", now_epoch=1000)
    assert "ConditionExpression" in table.kwargs
    assert "lease_until < :now" in table.kwargs["ConditionExpression"]
    assert table.kwargs["ExpressionAttributeValues"][":owner"] == "github-fallback"


def test_missing_database_object_is_first_run(monkeypatch, tmp_path):
    table = FakeTable()
    s3 = FakeS3()
    monkeypatch.setattr("services.automation_state.boto3.resource", lambda *a, **k: FakeDynamo(table))
    monkeypatch.setattr("services.automation_state.boto3.client", lambda *a, **k: s3)
    state = AutomationState(table_name="table", bucket_name="bucket", region_name="us-east-1")
    assert state.restore_database(tmp_path / "data" / "market_digest.db") is False


def test_pdf_upload_uses_trading_date_partition(monkeypatch, tmp_path):
    table = FakeTable()
    s3 = FakeS3()
    monkeypatch.setattr("services.automation_state.boto3.resource", lambda *a, **k: FakeDynamo(table))
    monkeypatch.setattr("services.automation_state.boto3.client", lambda *a, **k: s3)
    state = AutomationState(table_name="table", bucket_name="bucket", region_name="us-east-1")
    pdf = tmp_path / "market_digest_2026-10-22.pdf"
    pdf.write_bytes(b"%PDF-test")
    key = state.save_pdf(pdf, date(2026, 10, 22))
    assert key == "reports/2026/10/22/market_digest_2026-10-22.pdf"
    assert s3.uploads[0][0][1:] == ("bucket", key)
