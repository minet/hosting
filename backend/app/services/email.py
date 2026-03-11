"""Reusable SMTP email helper."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import Settings

logger = logging.getLogger(__name__)


def send_email(
    *,
    to_email: str,
    subject: str,
    plain: str,
    html: str,
    settings: Settings,
) -> bool:
    """Send an email via SMTP. Returns True on success, False on failure."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(host=settings.smtp_host, port=settings.smtp_port) as smtp:
            smtp.sendmail(settings.smtp_from, [to_email], msg.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s: %s", to_email, subject)
        return False
