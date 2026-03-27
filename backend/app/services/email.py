"""Reusable SMTP email helper."""

from __future__ import annotations

import asyncio
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
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("Failed to send email to %s: %s — %s", to_email, subject, exc)
        return False


async def send_email_async(
    *,
    to_email: str,
    subject: str,
    plain: str,
    html: str,
    settings: Settings,
) -> bool:
    """Async wrapper around :func:`send_email` — runs SMTP in a thread."""
    return await asyncio.to_thread(
        send_email,
        to_email=to_email,
        subject=subject,
        plain=plain,
        html=html,
        settings=settings,
    )
