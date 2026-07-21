"""Webhook + email notification for a fired scheduled query. Both return
(sent, detail) rather than raising -- the job body decides how to combine
and report these, consistent with this project's "visible degradation,
never silent" posture for every other fallible external call.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Any

import requests

from app.core.config import get_settings

WEBHOOK_TIMEOUT_SECONDS = 10


def send_webhook(url: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        response = requests.post(url, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return True, None
    except Exception as exc:
        return False, f"webhook failed: {exc}"


def send_email(to_address: str, subject: str, body: str) -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.smtp_host:
        return False, "email not configured (SMTP_HOST unset)"
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_address or settings.smtp_username or "noreply@localhost"
        msg["To"] = to_address
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=WEBHOOK_TIMEOUT_SECONDS) as server:
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(msg["From"], [to_address], msg.as_string())
        return True, None
    except Exception as exc:
        return False, f"email failed: {exc}"
