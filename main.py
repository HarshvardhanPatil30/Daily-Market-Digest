import argparse, sys
from datetime import date
from config import settings
from services.logging_service import configure_logging
from services.orchestrator import Orchestrator
from services.database import Database
from services.email_service import send_pdf_email
from datetime import datetime
from zoneinfo import ZoneInfo
from services.scheduler import setup_task, windows_task_command

def parse_date(value):
    try: return date.fromisoformat(value)
    except ValueError: raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD")
def main(argv=None):
    parser=argparse.ArgumentParser(description="AI-powered Indian daily market digest (Ollama-only local AI).")
    sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run",help="Generate a digest"); run.add_argument("--demo",action="store_true",help="Use clearly labelled fictional offline fixtures"); run.add_argument("--date",type=parse_date,help="Verified trading date (YYYY-MM-DD)")
    sub.add_parser("validate-sources",help="Inspect configured public sources")
    sub.add_parser("status",help="Show the latest run")
    sub.add_parser("email-latest",help="Email the latest completed PDF using configured SMTP credentials")
    history=sub.add_parser("history",help="Show recent runs"); history.add_argument("--limit",type=int,default=10)
    task=sub.add_parser("setup-task",help="Create Windows weekday 16:15 task only after explicit confirmation"); task.add_argument("--confirm",action="store_true")
    args=parser.parse_args(argv); configure_logging(); db=Database(settings.database_path); db.initialize()
    if args.command=="run":
        try: _,path=Orchestrator().run(args.demo,args.date); print(f"Generated: {path}"); return 0
        except Exception as e: print(f"Run failed: {e}",file=sys.stderr); return 2
    if args.command=="validate-sources":
        for k,v in Orchestrator().source_status().items(): print(f"{k}: {v}")
    elif args.command=="status":
        row=db.latest(); print(dict(row) if row else "No runs recorded.")
    elif args.command=="history":
        for row in db.history(args.limit): print(dict(row))
    elif args.command=="email-latest":
        row=db.latest_digest()
        if not row:
            print("No completed digest is recorded in SQLite.", file=sys.stderr); return 2
        try:
            recipient=send_pdf_email(row["pdf_path"], row["trading_date"])
            db.record_email_delivery(row["execution_id"], datetime.now(ZoneInfo(settings.timezone)).isoformat(), "sent", recipient)
            print(f"Emailed digest for {row['trading_date']} to {recipient}")
            return 0
        except Exception as e:
            try: db.record_email_delivery(row["execution_id"], datetime.now(ZoneInfo(settings.timezone)).isoformat(), "failed", settings.email_to, type(e).__name__ + ": " + str(e))
            except Exception: pass
            print(f"Email failed: {e}",file=sys.stderr); return 2
    else:
        try: print(setup_task(__file__.rsplit("/",1)[0],args.confirm) if args.confirm else "No task created. Review this command, then re-run with --confirm on Windows:\n"+windows_task_command(__file__.rsplit("/",1)[0]))
        except Exception as e: print(f"Scheduler setup failed: {e}",file=sys.stderr); return 2
    return 0
if __name__=="__main__": raise SystemExit(main())
