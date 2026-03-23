"""
Charter endpoints.

Provides routes to retrieve the hosting charter and to record a user's
digital signature, which triggers a confirmation email with a PDF attachment.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import UTC, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth import AuthCtx, require_user
from app.core.config import Settings, get_settings
from app.core.sessions import get_refresh_token, set_token_cookies
from app.services.auth.helpers import refresh_access_token
from app.services.auth.keycloak_admin import (
    fetch_keycloak_user_by_id_async,
    set_date_signed_hosting_async,
)
from app.services.auth.service import current_user_claims
from app.services.charter import generate_charter_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/charter", tags=["charter"])

_MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def _fmt_date(iso: str) -> str:
    """Formate une date ISO en français lisible : '09 mars 2026 à 01:41 UTC'."""
    try:
        dt = datetime.fromisoformat(iso)
        dt_paris = dt.astimezone(ZoneInfo("Europe/Paris"))
        offset = dt_paris.strftime("%z")
        offset_fmt = f"UTC{offset[:3]}:{offset[3:]}" if len(offset) == 5 else "UTC+1"
        return f"{dt_paris.day:02d} {_MOIS[dt_paris.month - 1]} {dt_paris.year} à {dt_paris.strftime('%H:%M')} ({offset_fmt})"
    except Exception:
        return iso


def _send_charter_email(
    *,
    to_email: str,
    prenom: str,
    nom: str,
    signed_at: str,
    pdf_bytes: bytes,
    settings: Settings,
) -> None:
    """Send the signed charter PDF by email via SMTP."""
    base_url = settings.backend_url.rstrip("/")
    logo_hosting_tag = f'<img src="{base_url}/assets/logo_hosting.png" alt="Hosting MiNET" style="height:48px;">'
    logo_minet_tag = f'<img src="{base_url}/assets/logo_minet.png" alt="MiNET" style="height:32px;">'
    signed_at_display = _fmt_date(signed_at)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#1a56db;padding:28px 40px;text-align:center;">
            {logo_hosting_tag}
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <h2 style="margin:0 0 8px;font-size:22px;color:#111827;">Charte signée ✓</h2>
            <p style="margin:0 0 24px;font-size:15px;color:#6b7280;">Confirmation de signature</p>

            <p style="margin:0 0 16px;font-size:15px;color:#374151;">Bonjour <strong>{prenom} {nom}</strong>,</p>
            <p style="margin:0 0 16px;font-size:15px;color:#374151;">
              Vous venez de signer la charte d'utilisation de la plateforme <strong>Hosting MiNET</strong>.
              Vous trouverez en pièce jointe un exemplaire PDF de la charte signée.
            </p>

            <!-- Info box -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#eff6ff;border-left:4px solid #1a56db;border-radius:4px;margin:24px 0;">
              <tr>
                <td style="padding:16px 20px;">
                  <p style="margin:0 0 4px;font-size:13px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">Date de signature</p>
                  <p style="margin:0;font-size:15px;color:#1e40af;font-weight:bold;">{signed_at_display}</p>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 24px;font-size:15px;color:#374151;">
              Pour toute question, ouvrez un ticket sur
              <a href="https://tickets.minet.net" style="color:#1a56db;text-decoration:none;font-weight:bold;">tickets.minet.net</a>.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:24px 40px;text-align:center;">
            {logo_minet_tag}
            <p style="margin:12px 0 0;font-size:12px;color:#9ca3af;">
              © MiNET — Ce message est envoyé automatiquement, merci de ne pas y répondre.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    plain = (
        f"Bonjour {prenom} {nom},\n\n"
        "Vous venez de signer la charte d'utilisation de la plateforme Hosting MiNET.\n"
        f"Date de signature : {signed_at}\n\n"
        "Veuillez trouver en pièce jointe un exemplaire PDF de la charte signée.\n\n"
        "Pour toute question, ouvrez un ticket sur https://tickets.minet.net/\n\n"
        "— L'équipe MiNET"
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = "Hosting MiNET — Confirmation de signature de la charte"
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Attach PDF in a mixed wrapper
    outer = MIMEMultipart("mixed")
    outer["From"] = settings.smtp_from
    outer["To"] = to_email
    outer["Subject"] = "Hosting MiNET — Confirmation de signature de la charte"
    outer.attach(msg)

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename="charte_hosting_minet.pdf")
    outer.attach(attachment)

    logger.info("Sending charter email to %s via %s:%s", to_email, settings.smtp_host, settings.smtp_port)
    with smtplib.SMTP(host=settings.smtp_host, port=settings.smtp_port) as smtp:
        smtp.sendmail(settings.smtp_from, [to_email], outer.as_string())
    logger.info("Charter email sent successfully to %s", to_email)


def _refresh_session_token(request: Request, response: Response, settings: Settings) -> None:
    """Refresh the access token and update cookies.

    Called after a Keycloak user attribute update so the new JWT immediately
    reflects the change (e.g. ``dateSignedHosting``).
    """
    refresh_tok = get_refresh_token(request)
    if not refresh_tok:
        return
    try:
        token_response = refresh_access_token(refresh_tok)
        new_access_token = token_response.get("access_token")
        new_refresh_token = token_response.get("refresh_token")
        if isinstance(new_access_token, str):
            set_token_cookies(
                response,
                access_token=new_access_token,
                refresh_token=new_refresh_token if isinstance(new_refresh_token, str) else None,
                settings=settings,
            )
    except Exception:
        logger.warning("Could not refresh token after charter signature — user may need to re-login")


@router.post("/sign")
async def sign_charter(
    request: Request,
    response: Response,
    ctx: AuthCtx = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Record the authenticated user's acceptance of the hosting charter.

    Sets ``dateSignedHosting`` on the Keycloak account, refreshes the session
    token so the change is immediately visible, generates a PDF of the charter
    and sends it to the user by email.

    :param request: The incoming HTTP request (used to refresh the session token).
    :param ctx: Authenticated user context (injected).
    :param settings: Application settings (injected).
    :returns: ``{"signed_at": "<ISO date>"}`` on success.
    :raises HTTPException: 500 if the Keycloak update fails.
    """
    claims = current_user_claims(ctx.payload)
    prenom = claims.get("prenom") or ""
    nom = claims.get("nom") or ""
    email = claims.get("email") or ""
    user_id = ctx.user_id

    # Fallback: fetch email from Keycloak admin if absent from token
    if not email:
        kc_profile = await fetch_keycloak_user_by_id_async(user_id)
        if kc_profile:
            email = kc_profile.get("email") or ""

    now = datetime.now(tz=UTC)
    signed_at_ms = int(now.timestamp() * 1000)
    signed_at = now.isoformat()

    ok = await set_date_signed_hosting_async(user_id=user_id, date_iso=str(signed_at_ms))
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record charter signature — please try again or contact an administrator.",
        )

    # Refresh the session token so the new dateSignedHosting attribute is
    # immediately present in the JWT for subsequent requests.
    _refresh_session_token(request, response, settings)

    try:
        pdf_bytes = generate_charter_pdf(prenom=prenom, nom=nom, signed_at=signed_at)
    except Exception:
        logger.exception("Failed to generate charter PDF for user_id=%s", user_id)
        pdf_bytes = None

    if not email:
        logger.warning("No email address for user_id=%s — skipping charter email", user_id)
    elif not pdf_bytes:
        logger.warning("PDF generation failed for user_id=%s — skipping charter email", user_id)
    else:
        try:
            _send_charter_email(
                to_email=email,
                prenom=prenom,
                nom=nom,
                signed_at=signed_at,
                pdf_bytes=pdf_bytes,
                settings=settings,
            )
        except Exception:
            logger.exception("Failed to send charter email to %s (user_id=%s)", email, user_id)

    return {"signed_at": signed_at}
