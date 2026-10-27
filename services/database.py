import sqlite3
from contextlib import contextmanager
from pathlib import Path

class Database:
    def __init__(self, path): self.path = Path(path)
    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.path)); con.row_factory = sqlite3.Row
        try: yield con; con.commit()
        except Exception: con.rollback(); raise
        finally: con.close()
    def initialize(self):
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS runs (execution_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, trading_date TEXT, status TEXT NOT NULL, mode TEXT NOT NULL, ai_mode TEXT, error TEXT, complete INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS digests (execution_id TEXT PRIMARY KEY REFERENCES runs(execution_id), pdf_path TEXT, created_at TEXT NOT NULL, disclosures TEXT);
            CREATE TABLE IF NOT EXISTS education_terms (term TEXT PRIMARY KEY, used_at TEXT NOT NULL, source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS email_deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL REFERENCES runs(execution_id), attempted_at TEXT NOT NULL, status TEXT NOT NULL, recipient TEXT NOT NULL, error TEXT);
            CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);''')
    def start_run(self, execution_id, started, mode):
        with self.connect() as c: c.execute("INSERT INTO runs(execution_id,started_at,status,mode) VALUES(?,?,?,?)", (execution_id, started, "running", mode))
    def finish_run(self, execution_id, ended, trading_date, status, complete, error=None, ai_mode="offline"):
        with self.connect() as c: c.execute("UPDATE runs SET ended_at=?,trading_date=?,status=?,complete=?,error=?,ai_mode=? WHERE execution_id=?", (ended, str(trading_date) if trading_date else None,status,int(complete),error,ai_mode,execution_id))
    def save_digest(self, execution_id, path, created, disclosures):
        with self.connect() as c: c.execute("INSERT OR REPLACE INTO digests VALUES(?,?,?,?)", (execution_id,str(path),created," | ".join(disclosures)))
    def latest_digest(self):
        with self.connect() as c: return c.execute("SELECT r.execution_id, r.trading_date, d.pdf_path FROM runs r JOIN digests d USING(execution_id) WHERE r.status='completed' AND r.complete=1 AND d.pdf_path IS NOT NULL ORDER BY r.started_at DESC LIMIT 1").fetchone()
    def record_email_delivery(self, execution_id, attempted_at, status, recipient, error=None):
        with self.connect() as c: c.execute("INSERT INTO email_deliveries(execution_id,attempted_at,status,recipient,error) VALUES(?,?,?,?,?)", (execution_id,attempted_at,status,recipient,error))
    def latest(self):
        with self.connect() as c: return c.execute("SELECT r.*, d.pdf_path FROM runs r LEFT JOIN digests d USING(execution_id) ORDER BY started_at DESC LIMIT 1").fetchone()
    def history(self, limit=10):
        with self.connect() as c: return c.execute("SELECT execution_id,started_at,trading_date,status,mode,complete FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
