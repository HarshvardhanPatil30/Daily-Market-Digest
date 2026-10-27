"""Configuration for the Daily Market Digest (no hosted AI credentials)."""
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent

def _bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    output_dir: Path = ROOT / os.getenv("OUTPUT_DIR", "reports")
    database_path: Path = ROOT / os.getenv("DATABASE_PATH", "data/market_digest.db")
    log_dir: Path = ROOT / os.getenv("LOG_DIR", "logs")
    timezone: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    strict_data_validation: bool = _bool("STRICT_DATA_VALIDATION", True)
    timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: str = os.getenv("EMAIL_TO", "")
    gmail_app_password: str = os.getenv("GMAIL_APP_PASSWORD", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))

settings = Settings()
