"""
Expired-membership VM purge service.

Checks all VMs whose owner's membership (cotisation) has expired.
- Sends a monthly warning email to the owner.
- After 6 months of expired membership, deletes the VM from Proxmox and DB.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import fetch_keycloak_group_members
from app.services.dns import DnsService
from app.services.email import send_email
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway

logger = logging.getLogger(__name__)

# 6 months minus 1 day in seconds (deletion threshold)
_SIX_MONTHS_S = (6 * 30 - 1) * 24 * 3600


def _cotise_end_from_profile(profile: dict[str, Any] | None, claim_key: str) -> int | None:
    """Extract cotise_end_ms from a Keycloak user profile dict."""
    if not profile:
        return None
    attrs = profile.get("attributes") or {}
    values = attrs.get(claim_key)
    if isinstance(values, list) and values:
        try:
            return int(values[0])
        except (ValueError, TypeError):
            return None
    # Also check flat key (fetch_keycloak_user_profile flattens attrs)
    raw = profile.get("cotise_end_ms")
    if raw is not None:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    return None


def _build_warning_email(
    *,
    prenom: str,
    nom: str,
    vm_name: str,
    vm_id: int,
    days_expired: int,
    days_remaining: int,
    settings: Settings,
) -> tuple[str, str, str]:
    """Return (subject, plain, html) for a warning email."""
    base_url = settings.backend_url.rstrip("/")
    subject = f"Hosting MiNET — Votre VM « {vm_name} » sera supprimée"

    plain = (
        f"Bonjour {prenom} {nom},\n\n"
        f"Votre cotisation MiNET a expiré il y a {days_expired} jours.\n"
        f"Votre machine virtuelle « {vm_name} » (ID {vm_id}) sera automatiquement "
        f"supprimée dans {days_remaining} jours si vous ne renouvelez pas votre cotisation.\n\n"
        "Rendez-vous sur https://adh6.minet.net pour renouveler.\n\n"
        "— L'équipe MiNET"
    )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <tr><td style="background:#dc2626;padding:28px 40px;text-align:center;">
          <img src="{base_url}/assets/logo_hosting.png" alt="Hosting MiNET" style="height:48px;">
        </td></tr>
        <tr><td style="padding:40px;">
          <h2 style="margin:0 0 8px;font-size:22px;color:#111827;">Suppression programmée</h2>
          <p style="margin:0 0 24px;font-size:15px;color:#6b7280;">Action requise</p>
          <p style="font-size:15px;color:#374151;">Bonjour <strong>{prenom} {nom}</strong>,</p>
          <p style="font-size:15px;color:#374151;">
            Votre cotisation MiNET a expiré il y a <strong>{days_expired} jours</strong>.
          </p>
          <table width="100%" style="background:#fef2f2;border-left:4px solid #dc2626;border-radius:4px;margin:24px 0;">
            <tr><td style="padding:16px 20px;">
              <p style="margin:0 0 4px;font-size:13px;color:#6b7280;text-transform:uppercase;">VM concernée</p>
              <p style="margin:0;font-size:15px;color:#991b1b;font-weight:bold;">{vm_name} (#{vm_id})</p>
              <p style="margin:8px 0 0;font-size:14px;color:#991b1b;">
                Suppression automatique dans <strong>{days_remaining} jours</strong>
              </p>
            </td></tr>
          </table>
          <p style="font-size:15px;color:#374151;">
            <a href="https://adh6.minet.net" style="color:#1a56db;font-weight:bold;">Renouvelez votre cotisation</a>
            pour conserver votre VM.
          </p>
        </td></tr>
        <tr><td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:24px 40px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#9ca3af;">© MiNET — Message automatique</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""

    return subject, plain, html


def run_purge(
    *,
    db: Session,
    gateway: ProxmoxGateway,
    settings: Settings,
) -> dict[str, Any]:
    """Run one purge cycle.

    - Fetches members of the hosting_ended group (expired memberships).
    - For each, checks how long ago their membership expired.
    - Sends a warning email if not yet at 6 months.
    - Deletes the VM if 6 months have passed.

    Returns a summary dict.
    """
    now = datetime.now(tz=UTC)
    query_repo = VmQueryRepo(db)
    cmd_repo = VmCmdRepo(db)
    dns = DnsService(settings=settings)

    # Get expired users from Keycloak group
    expired_members = fetch_keycloak_group_members("/hosting_ended")
    if not expired_members:
        logger.info("purge: no expired members found")
        return {"warned": 0, "deleted": 0}

    expired_ids = {m["id"] for m in expired_members if m.get("id")}

    # Get all VMs with their owners
    all_vms = query_repo.list_all_vms()

    warned = 0
    deleted = 0

    for vm in all_vms:
        owner_id = vm.get("owner_id")
        if not owner_id or owner_id not in expired_ids:
            continue

        vm_id = vm["vm_id"]
        vm_name = vm["name"]

        # Find the member info
        member = next((m for m in expired_members if m.get("id") == owner_id), None)
        if not member:
            continue

        # We need to find when the cotisation expired.
        # Use the Keycloak user profile to get cotise_end_ms.
        from app.services.auth.keycloak_admin import fetch_keycloak_user_profile

        username = member.get("username")
        profile = fetch_keycloak_user_profile(username) if isinstance(username, str) else None
        cotise_end_ms = _cotise_end_from_profile(profile, settings.auth_cotise_end_claim.strip())

        if cotise_end_ms is None:
            logger.warning("purge: cannot determine cotise_end for user %s, skipping vm %s", owner_id, vm_id)
            continue

        cotise_end = datetime.fromtimestamp(cotise_end_ms / 1000, tz=UTC)
        elapsed = now - cotise_end
        elapsed_seconds = elapsed.total_seconds()

        if elapsed_seconds <= 0:
            # Not actually expired
            continue

        days_expired = int(elapsed_seconds / 86400)
        days_remaining = max(0, int((_SIX_MONTHS_S - elapsed_seconds) / 86400))

        email = member.get("email")
        prenom = member.get("first_name") or "Utilisateur"
        nom = member.get("last_name") or ""

        if elapsed_seconds >= _SIX_MONTHS_S:
            # 6 months passed — delete the VM
            logger.info("purge: deleting vm %s (owner=%s, expired %d days ago)", vm_id, owner_id, days_expired)

            # Send final deletion email
            if email:
                subject = f"Hosting MiNET — Votre VM « {vm_name} » a été supprimée"
                plain = (
                    f"Bonjour {prenom} {nom},\n\n"
                    f"Votre cotisation MiNET a expiré il y a {days_expired} jours (plus de 6 mois).\n"
                    f"Votre machine virtuelle « {vm_name} » (ID {vm_id}) a été supprimée automatiquement.\n\n"
                    "— L'équipe MiNET"
                )
                html_del = f"""<!DOCTYPE html><html lang="fr"><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;">
<tr><td style="background:#111;padding:28px 40px;text-align:center;color:#fff;font-size:20px;font-weight:bold;">VM supprimée</td></tr>
<tr><td style="padding:40px;">
<p style="font-size:15px;color:#374151;">Bonjour <strong>{prenom} {nom}</strong>,</p>
<p style="font-size:15px;color:#374151;">Votre VM <strong>{vm_name}</strong> (#{vm_id}) a été supprimée après 6 mois de cotisation expirée.</p>
</td></tr></table></td></tr></table></body></html>"""
                send_email(to_email=email, subject=subject, plain=plain, html=html_del, settings=settings)

            try:
                gateway.delete_vm(vm_id=vm_id)
            except ProxmoxError:
                logger.exception("purge: failed to delete vm %s from Proxmox", vm_id)
                continue

            try:
                cmd_repo.delete_vm_with_related(vm_id)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("purge: failed to delete vm %s from DB (Proxmox already deleted)", vm_id)
                continue

            dns.delete_records(vm_id=vm_id)
            deleted += 1

        else:
            # Not yet 6 months — send warning email (once per run, meant to be run monthly)
            if email:
                subject, plain, html = _build_warning_email(
                    prenom=prenom,
                    nom=nom,
                    vm_name=vm_name,
                    vm_id=vm_id,
                    days_expired=days_expired,
                    days_remaining=days_remaining,
                    settings=settings,
                )
                send_email(to_email=email, subject=subject, plain=plain, html=html, settings=settings)
                warned += 1
                logger.info(
                    "purge: warned user %s for vm %s (expired %d days, %d remaining)",
                    owner_id,
                    vm_id,
                    days_expired,
                    days_remaining,
                )

    result = {"warned": warned, "deleted": deleted}
    logger.info("purge: done — %s", result)
    return result
