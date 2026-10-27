from datetime import datetime as RealDatetime

from scripts import run_automated as runner


class FakeDatabase:
    row = {
        "execution_id": "execution-1",
        "trading_date": "2026-10-27",
        "pdf_path": "reports/market_digest_2026-10-27.pdf",
    }

    def __init__(self, path):
        self.path = path

    def initialize(self):
        pass

    def latest_digest(self):
        return self.row


class FakeState:
    bucket_name = "test-bucket"

    def __init__(self):
        self.status = "running"
        self.calls = []

    def is_terminal(self, run_date):
        return False

    def claim(self, run_date, owner):
        return "claim-token"

    def restore_database(self, path):
        return False

    def save_pdf(self, path, trading_date):
        return "reports/2026/10/27/digest.pdf"

    def save_database(self, path):
        pass

    def mark_email_pending(self, *args):
        self.status = "email_pending"
        self.calls.append("pending")

    def mark_email_sent(self, *args):
        assert self.status == "email_pending"
        self.status = "email_sent"
        self.calls.append("sent")

    def complete(self, *args):
        assert self.status == "email_sent"
        self.status = "completed"

    def fail(self, *args):
        raise AssertionError("success path must not mark failed")


def test_runner_records_no_retry_barrier_before_email_process(monkeypatch):
    fixed = RealDatetime(2026, 10, 27, 17, 0, tzinfo=runner.IST)

    class FixedDatetime:
        @staticmethod
        def now(tz=None):
            return fixed.astimezone(tz) if tz else fixed

        strptime = staticmethod(RealDatetime.strptime)

    state = FakeState()
    monkeypatch.setattr(runner, "datetime", FixedDatetime)
    monkeypatch.setattr(runner, "AutomationState", lambda: state)
    monkeypatch.setattr(runner, "Database", FakeDatabase)
    monkeypatch.setattr(runner, "configure_logging", lambda: None)

    def run_with_lease(command, *args):
        if command[-1] == "email-latest":
            assert state.status == "email_pending"
            state.calls.append("smtp")

    monkeypatch.setattr(runner, "run_with_lease", run_with_lease)

    assert runner.main(["--mode", "aws"]) == 0
    assert state.calls == ["pending", "smtp", "sent"]
    assert state.status == "completed"
