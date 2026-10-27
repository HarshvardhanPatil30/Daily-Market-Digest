"""Send a generated digest PDF through Gmail SMTP using environment secrets."""
from email.message import EmailMessage
from pathlib import Path
import smtplib

from config import settings


def send_pdf_email(pdf_path, trading_date, config=settings):
    """Send one PDF. Credentials must be supplied via environment variables.

    Raises ValueError for missing configuration or an invalid attachment and
    propagates SMTP errors to the caller for logging/history.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise ValueError(f"PDF attachment does not exist: {path}")

    sender = config.email_from.strip()
    recipient = config.email_to.strip()
    password = config.gmail_app_password.replace(" ", "")
    if not sender or not recipient or not password:
        raise ValueError(
            "Email is not configured. Set EMAIL_FROM, EMAIL_TO, and "
            "GMAIL_APP_PASSWORD in the environment; do not put credentials in code."
        )
    if config.smtp_port not in (465, 587):
        raise ValueError("SMTP_PORT must be 465 (SSL) or 587 (STARTTLS)")

    message = EmailMessage()
    message["Subject"] = f"Daily Market Digest — {trading_date}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Attached is your Daily Market Digest for {trading_date}.\n\n"
        "This report is for internal information only, not investment advice. "
        "Please review source disclosures and data limitations in the PDF."
    )
    message.add_attachment(
        path.read_bytes(), maintype="application", subtype="pdf",
        filename=path.name
    )

    if config.smtp_port == 465:
        with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=config.timeout_seconds) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=config.timeout_seconds) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender, password)
            smtp.send_message(message)
    return recipient
