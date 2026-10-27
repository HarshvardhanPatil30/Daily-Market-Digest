"""Run the existing digest backend under AWS scheduling or GitHub fallback."""
import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from services.automation_state import AutomationState  # noqa: E402
from services.database import Database  # noqa: E402
from services.logging_service import configure_logging  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
FALLBACK_AFTER_HOUR = 16
FALLBACK_AFTER_MINUTE = 30


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cloud-first digest runner with GitHub fallback.")
    parser.add_argument("--mode", choices=("aws", "github-fallback"), required=True)
    args = parser.parse_args(argv)
    configure_logging()
    log = logging.getLogger("automation")
    now = datetime.now(IST)
    run_date = now.date()
    owner = args.mode

    if now.weekday() >= 5:
        log.info("Not a weekday in Asia/Kolkata; skipping.")
        return 0
    if args.mode == "github-fallback" and (now.hour, now.minute) < (FALLBACK_AFTER_HOUR, FALLBACK_AFTER_MINUTE):
        log.info("Fallback deadline has not passed; skipping.")
        return 0

    state = AutomationState()
    if state.is_terminal(run_date):
        log.info("A successful report/email is already recorded for %s; skipping.", run_date)
        return 0
    if not state.claim(run_date, owner):
        current = state.get(run_date) or {}
        log.info("Another run owns %s or the AWS lease is still active (status=%s owner=%s); skipping.",
                 run_date, current.get("status"), current.get("owner"))
        return 0

    db_path = settings.database_path
    email_sent = False
    try:
        restored = state.restore_database(db_path)
        log.info("SQLite history %s from S3.", "restored" if restored else "not found; initializing a new history")
        Database(db_path).initialize()

        subprocess.run([sys.executable, "main.py", "run"], cwd=ROOT, check=True, timeout=25 * 60)
        row = Database(db_path).latest_digest()
        if not row:
            raise RuntimeError("Report run returned success, but SQLite has no completed digest record.")
        pdf_path = Path(row["pdf_path"])
        if not pdf_path.is_absolute():
            pdf_path = ROOT / pdf_path
        pdf_key = state.save_pdf(pdf_path, datetime.strptime(row["trading_date"], "%Y-%m-%d").date())
        # Persist the successful run record before attempting email delivery.
        state.save_database(db_path)

        subprocess.run([sys.executable, "main.py", "email-latest"], cwd=ROOT, check=True, timeout=120)
        email_sent = True
        state.mark_email_sent(run_date, owner, row["execution_id"], row["trading_date"], pdf_key)
        # The email outcome is already durable in DynamoDB; this second sync preserves
        # the SQLite email-delivery row when S3 is available.
        state.save_database(db_path)
        state.complete(run_date, owner)
        log.info("Automation completed for %s; PDF stored at s3://%s/%s", run_date, state.bucket_name, pdf_key)
        return 0
    except Exception as exc:
        log.exception("Automated run failed for %s", run_date)
        try:
            state.save_database(db_path)
        except Exception:
            log.exception("Could not persist SQLite database to S3")
        if not email_sent:
            state.fail(run_date, owner, f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
