import logging
from config import settings

def configure_logging():
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(settings.log_dir / "market_digest.log", encoding="utf-8"), logging.StreamHandler()])
