"""
Expired-membership VM purge service.

Checks all VMs whose owner's membership (cotisation) has expired.
- Sends a monthly warning email to the owner (at most once per 30 days).
- After 6 months of expired membership, deletes the VM from Proxmox and DB.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.templates import jinja_env
from app.db.models.vm_purge_mail import VMPurgeMail
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import fetch_keycloak_group_members_async, fetch_keycloak_user_profile_async
from app.services.discord import notify_vm_purge_deleted
from app.services.dns import DnsService
from app.services.email import send_email_async
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway

logger = logging.getLogger(__name__)

# 6 months minus 1 day in seconds (deletion threshold)
_SIX_MONTHS_S = (6 * 30 - 1) * 24 * 3600
# Minimum interval between warning emails
_WARN_INTERVAL = timedelta(days=30)


def _cotise_end_from_profile(profile: dict[str, Any] | None, claim_key: str, departure_claim_key: str = "departureDate") -> int | None:
    """Extract the membership expiry timestamp (ms) from a Keycloak user profile.

    Tries ``departure_claim_key`` (departureDate) first as it is more reliable,
    then falls back to ``claim_key`` (cotise_end) and the pre-computed
    ``cotise_end_ms`` field.
    """
    if not profile:
        return None

    attrs = profile.get("attributes") or {}

    for raw in (
        profile.get(departure_claim_key),
        attrs.get(departure_claim_key),
        profile.get("cotise_end_ms"),
        profile.get(claim_key),
        attrs.get(claim_key),
    ):
        if raw is None:
            continue
        try:
            return int(raw[0] if isinstance(raw, list) else raw)
        except (ValueError, TypeError):
            continue

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

    html = jinja_env.get_template("emails/vm_warning.html").render(
        base_url=base_url,
        prenom=prenom,
        nom=nom,
        days_expired=days_expired,
        vm_name=vm_name,
        vm_id=vm_id,
        days_remaining=days_remaining,
    )

    return subject, plain, html


async def _last_warning_sent_at(db: AsyncSession, vm_id: int) -> datetime | None:
    """Return the timestamp of the most recent warning email for this VM, or None."""
    result = await db.execute(
        select(func.max(VMPurgeMail.sent_at)).where(
            VMPurgeMail.vm_id == vm_id,
            VMPurgeMail.mail_type == "warning",
        )
    )
    return result.scalar_one_or_none()


async def _record_mail(db: AsyncSession, vm_id: int, mail_type: str) -> None:
    """Insert a VMPurgeMail row and flush (caller commits)."""
    db.add(VMPurgeMail(vm_id=vm_id, mail_type=mail_type))
    await db.flush()


async def run_purge(
    *,
    db: AsyncSession,
    gateway: ProxmoxGateway | None,
    settings: Settings,
) -> dict[str, Any]:
    """Run one purge cycle.

    - Fetches members of the hosting/ended group (expired memberships).
    - For each, checks how long ago their membership expired.
    - Sends a warning email at most once per 30 days.
    - Deletes the VM if 6 months have passed (only when Proxmox is configured).

    Returns a summary dict.
    """
    now = datetime.now(tz=UTC)
    query_repo = VmQueryRepo(db)
    cmd_repo = VmCmdRepo(db)
    dns = DnsService(settings=settings)

    expired_members = await fetch_keycloak_group_members_async("/hosting/ended")
    if not expired_members:
        logger.info("purge: no expired members found")
        return {"warned": 0, "deleted": 0}

    expired_ids = {m["id"] for m in expired_members if m.get("id")}

    # Get only VMs owned by expired users
    all_vms = await query_repo.list_vms_by_owners(expired_ids)

    warned = 0
    deleted = 0

    for vm in all_vms:
        owner_id = vm.get("owner_id")
        if not owner_id:
            continue

        vm_id = vm["vm_id"]
        vm_name = vm["name"]

        # Find the member info
        member = next((m for m in expired_members if m.get("id") == owner_id), None)
        if not member:
            continue

        username = member.get("username")
        profile = await fetch_keycloak_user_profile_async(username) if isinstance(username, str) else None
        cotise_end_ms = _cotise_end_from_profile(profile, settings.auth_cotise_end_claim.strip(), settings.auth_departure_date_claim.strip())

        if cotise_end_ms is None:
            logger.warning(
                "purge: cannot determine cotise_end for user %s, skipping vm %s",
                owner_id, vm_id,
            )
            continue

        cotise_end = datetime.fromtimestamp(cotise_end_ms / 1000, tz=UTC)
        elapsed_seconds = (now - cotise_end).total_seconds()
        days_expired = max(0, int(elapsed_seconds / 86400))
        days_remaining = max(0, int((_SIX_MONTHS_S - elapsed_seconds) / 86400))

        email = member.get("email")
        prenom = member.get("first_name") or "Utilisateur"
        nom = member.get("last_name") or ""

        if elapsed_seconds >= _SIX_MONTHS_S:
            last_sent = await _last_warning_sent_at(db, vm_id)

            # Never received any mail — send a 24h notice and skip deletion
            if last_sent is None:
                if email:
                    subject = f"Hosting MiNET — Votre VM « {vm_name} » sera supprimée dans 24h"
                    plain = (
                        f"Bonjour {prenom} {nom},\n\n"
                        f"Votre cotisation MiNET a expiré il y a {days_expired} jours.\n"
                        f"Votre machine virtuelle « {vm_name} » (ID {vm_id}) sera supprimée automatiquement dans 24h.\n\n"
                        "Si vous souhaitez conserver votre VM, renouvelez votre cotisation sur https://adh6.minet.net\n\n"
                        "— L'équipe MiNET"
                    )
                    html_notice = jinja_env.get_template("emails/vm_deletion_notice.html").render(
                        prenom=prenom,
                        nom=nom,
                        vm_name=vm_name,
                        vm_id=vm_id,
                        days_expired=days_expired,
                    )
                    await send_email_async(to_email=email, subject=subject, plain=plain, html=html_notice, settings=settings)
                    try:
                        await _record_mail(db, vm_id, "warning")
                        await db.commit()
                    except SQLAlchemyError:
                        await db.rollback()
                        logger.warning("purge: failed to record 24h notice for vm %s", vm_id)
                    warned += 1
                    logger.info("purge: sent 24h notice for vm %s (owner=%s, never warned before)", vm_id, owner_id)
                continue

            # Already warned at least once — proceed with deletion
            if gateway is None or not settings.proxmox_configured:
                logger.info(
                    "purge: vm %s eligible for deletion (owner=%s, expired %d days) but Proxmox not configured — skipping",
                    vm_id, owner_id, days_expired,
                )
                continue

            logger.info("purge: deleting vm %s (owner=%s, expired %d days ago)", vm_id, owner_id, days_expired)

            if email:
                subject = f"Hosting MiNET — Votre VM « {vm_name} » a été supprimée"
                plain = (
                    f"Bonjour {prenom} {nom},\n\n"
                    f"Votre cotisation MiNET a expiré il y a {days_expired} jours (plus de 6 mois).\n"
                    f"Votre machine virtuelle « {vm_name} » (ID {vm_id}) a été supprimée automatiquement.\n\n"
                    "— L'équipe MiNET"
                )
                html_del = jinja_env.get_template("emails/vm_deleted.html").render(
                    prenom=prenom, nom=nom, vm_name=vm_name, vm_id=vm_id,
                )
                await send_email_async(to_email=email, subject=subject, plain=plain, html=html_del, settings=settings)
                try:
                    await _record_mail(db, vm_id, "deletion")
                    await db.commit()
                except SQLAlchemyError:
                    await db.rollback()
                    logger.warning("purge: failed to record deletion mail for vm %s", vm_id)

            try:
                status_payload = await asyncio.to_thread(gateway.get_vm_status, vm_id=vm_id)
            except ProxmoxError:
                logger.exception("purge: failed to get status for vm %s, skipping", vm_id)
                continue

            if str(status_payload.get("status", "")).lower() != "stopped":
                try:
                    await asyncio.to_thread(gateway.stop_vm, vm_id=vm_id)
                except ProxmoxError:
                    logger.exception("purge: failed to stop vm %s before deletion, skipping", vm_id)
                    continue

            try:
                await asyncio.to_thread(gateway.delete_vm, vm_id=vm_id)
            except ProxmoxError:
                logger.exception("purge: failed to delete vm %s from Proxmox", vm_id)
                continue

            try:
                await cmd_repo.release_ip_history(vm_id)
                await cmd_repo.delete_vm_with_related(vm_id)
                await db.commit()
            except (SQLAlchemyError, OSError):
                await db.rollback()
                logger.exception("purge: failed to delete vm %s from DB (Proxmox already deleted)", vm_id)
                continue

            await dns.delete_records(vm_id=vm_id)
            await notify_vm_purge_deleted(vm_id=vm_id, vm_name=vm_name, days_expired=days_expired)
            deleted += 1

        else:
            # Not yet 6 months — send warning email at most once per 30 days
            last_sent = await _last_warning_sent_at(db, vm_id)
            if last_sent is not None and (now - last_sent.replace(tzinfo=UTC)) < _WARN_INTERVAL:
                logger.debug(
                    "purge: skipping warning for vm %s — last sent %s days ago",
                    vm_id,
                    (now - last_sent.replace(tzinfo=UTC)).days,
                )
                continue

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
                await send_email_async(to_email=email, subject=subject, plain=plain, html=html, settings=settings)
                try:
                    await _record_mail(db, vm_id, "warning")
                    await db.commit()
                except SQLAlchemyError:
                    await db.rollback()
                    logger.warning("purge: failed to record warning mail for vm %s", vm_id)
                warned += 1
                logger.info(
                    "purge: warned user %s for vm %s (expired %d days, %d remaining)",
                    owner_id,
                    vm_id,
                    days_expired,
                    days_remaining,
                )

    await dns.close()
    result = {"warned": warned, "deleted": deleted}
    logger.info("purge: done — %s", result)
    return result
