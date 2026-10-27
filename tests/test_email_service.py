from dataclasses import replace
import pytest

from config import settings
from services import email_service


class FakeSMTP:
    last_message = None
    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def login(self, user, password):
        assert user == 'sender@gmail.com'
        assert password == 'apppassword'
    def send_message(self, message):
        FakeSMTP.last_message = message


def test_sends_pdf_attachment(monkeypatch, tmp_path):
    pdf = tmp_path / 'digest.pdf'; pdf.write_bytes(b'%PDF-1.4 test')
    config = replace(settings, email_from='sender@gmail.com', email_to='reader@example.com',
                     gmail_app_password='app password', smtp_host='smtp.gmail.com', smtp_port=465)
    monkeypatch.setattr(email_service.smtplib, 'SMTP_SSL', FakeSMTP)
    recipient = email_service.send_pdf_email(pdf, '2026-10-21', config)
    assert recipient == 'reader@example.com'
    message = FakeSMTP.last_message
    assert message['Subject'] == 'Daily Market Digest — 2026-10-21'
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == 'digest.pdf'
    assert attachments[0].get_payload(decode=True) == b'%PDF-1.4 test'


def test_missing_email_credentials_fail_without_sending(tmp_path):
    pdf = tmp_path / 'digest.pdf'; pdf.write_bytes(b'%PDF-test')
    config = replace(settings, email_from='', email_to='', gmail_app_password='')
    with pytest.raises(ValueError, match='Email is not configured'):
        email_service.send_pdf_email(pdf, '2026-10-21', config)

def test_missing_pdf_fails(tmp_path):
    config = replace(settings, email_from='sender@gmail.com', email_to='reader@example.com', gmail_app_password='x')
    with pytest.raises(ValueError, match='does not exist'):
        email_service.send_pdf_email(tmp_path/'missing.pdf', '2026-10-21', config)
