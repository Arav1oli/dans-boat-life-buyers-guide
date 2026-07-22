from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import settings


def send_email(recipient: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP is not configured; message remains in the database outbox")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
