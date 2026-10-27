"""Run the digest backend under AWS scheduling or GitHub fallback."""

import argparse
import logging
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from services.automation_state import (  # noqa: E402
    AutomationState,
    LEASE_SECONDS,
)
from services.database import Database  # noqa: E402
from services.logging_service import configure_logging  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
FALLBACK_AFTER_HOUR = 16
FALLBACK_AFTER_MINUTE = 30


def run_with_lease(command, timeout, state, run_date, owner, token, log):
    """Run a child process while periodically renewing its DynamoDB lease."""
    process = subprocess.Popen(command, cwd=ROOT)
    started = time.monotonic()
    renew_interval = max(15, LEASE_SECONDS // 3)
    next_renewal = time.monotonic() + renew_interval

    try:
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= timeout:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise subprocess.TimeoutExpired(command, timeout)

            if time.monotonic() >= next_renewal:
                try:
                    state.renew_lease(run_date, owner, token)
                except Exception:
                    log.exception("Lease renewal failed; stopping child process.")
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise RuntimeError(
                        "Lost the run lease; child process was stopped."
                    )

                next_renewal = time.monotonic() + renew_interval

            time.sleep(2)

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)

    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cloud-first digest runner with GitHub fallback."
    )
    parser.add_argument(
        "--mode",
        choices=("aws", "github-fallback"),
        required=True,
    )
    args = parser.parse_args(argv)

    configure_logging()
    log = logging.getLogger("automation")
    now = datetime.now(IST)
    # Key fallback runs to the local market day, even after midnight UTC.
    run_date = now.astimezone(IST).date()
    owner = args.mode

    if now.weekday() >= 5:
        log.info("Not a weekday in Asia/Kolkata; skipping.")
        return 0

    if args.mode == "github-fallback" and (
        now.hour,
        now.minute,
    ) < (FALLBACK_AFTER_HOUR, FALLBACK_AFTER_MINUTE):
        log.info("Fallback deadline has not passed; skipping.")
        return 0

    state = AutomationState()

    if state.is_terminal(run_date):
        log.info(
            "A successful report/email is already recorded for %s; skipping.",
            run_date,
        )
        return 0

    token = state.claim(run_date, owner)
    if not token:
        current = state.get(run_date) or {}
        log.info(
            "Another run owns %s or the lease is active "
            "(status=%s owner=%s); skipping.",
            run_date,
            current.get("status"),
            current.get("owner"),
        )
        return 0

    db_path = settings.database_path
    email_attempted = False

    try:
        restored = state.restore_database(db_path)
        log.info(
            "SQLite history %s from S3.",
            "restored" if restored else "not found; initializing a new history",
        )
        Database(db_path).initialize()

        run_with_lease(
            [sys.executable, "main.py", "run"],
            25 * 60,
            state,
            run_date,
            owner,
            token,
            log,
        )

        row = Database(db_path).latest_digest()
        if not row:
            raise RuntimeError(
                "Report run returned success, but SQLite has no completed digest record."
            )

        pdf_path = Path(row["pdf_path"])
        if not pdf_path.is_absolute():
            pdf_path = ROOT / pdf_path

        trading_date = datetime.strptime(
            row["trading_date"], "%Y-%m-%d"
        ).date()

        pdf_key = state.save_pdf(pdf_path, trading_date)
        state.save_database(db_path)

        # Set a durable retry barrier before SMTP: an interrupted or failed
        # SMTP exchange may still have been accepted by the remote server.
        state.mark_email_pending(
            run_date, owner, token, row["execution_id"], row["trading_date"], pdf_key
        )
        email_attempted = True

        run_with_lease(
            [sys.executable, "main.py", "email-latest"],
            120,
            state,
            run_date,
            owner,
            token,
            log,
        )

        state.mark_email_sent(
            run_date,
            owner,
            token,
            row["execution_id"],
            row["trading_date"],
            pdf_key,
        )
        state.save_database(db_path)
        state.complete(run_date, owner, token)

        log.info(
            "Automation completed for %s; PDF stored at s3://%s/%s",
            run_date,
            state.bucket_name,
            pdf_key,
        )
        return 0

    except Exception as exc:
        log.exception("Automated run failed for %s", run_date)

        try:
            state.save_database(db_path)
        except Exception:
            log.exception("Could not persist SQLite database to S3")

        if email_attempted:
            log.critical(
                "Email delivery may be ambiguous. The run is blocked from automatic retry; "
                "check Gmail delivery and DynamoDB status before manual recovery."
            )
            try:
                state.mark_email_ambiguous(run_date, owner, token, f"{type(exc).__name__}: {exc}")
            except Exception:
                log.exception("Could not record ambiguous email outcome; email_pending remains a no-retry barrier")
        else:
            try:
                state.fail(run_date, owner, token, f"{type(exc).__name__}: {exc}")
            except Exception:
                log.exception("Could not record automation failure")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
