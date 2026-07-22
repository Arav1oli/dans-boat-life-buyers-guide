from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .config import settings


def send_with_resend(recipient: str, subject: str, body: str) -> None:
    payload = json.dumps({
        "from": settings.smtp_from,
        "to": [recipient],
        "subject": subject,
        "text": body,
    }).encode()
    request = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "dans-boat-life-guide/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Resend returned HTTP {response.status}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Resend rejected the email (HTTP {exc.code}): {detail}") from exc


def send_with_smtp(recipient: str, subject: str, body: str) -> None:
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


def send_email(recipient: str, subject: str, body: str) -> None:
    if settings.resend_api_key:
        send_with_resend(recipient, subject, body)
        return
    if settings.smtp_host:
        send_with_smtp(recipient, subject, body)
        return
    raise RuntimeError("Email delivery is not configured; message remains in the database outbox")
