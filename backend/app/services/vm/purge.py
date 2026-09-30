"""
Expired-membership VM purge service.

Checks all VMs whose owner's membership (cotisation) has expired.
- Sends three emails per expiry: one when the membership expires, one halfway
  to the deletion, and a final notice at least 24h before the deletion.
- After 1 month of expired membership, deletes the VM from Proxmox and DB.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.templates import jinja_env
from app.db.models.vm_purge_mail import VMPurgeMail
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import fetch_keycloak_group_members_async, fetch_keycloak_user_by_id_async
from app.services.discord import notify_purge_summary
from app.services.dns import DnsService
from app.services.email import send_email_async
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway

logger = logging.getLogger(__name__)

# Deletion threshold: 1 month (30 days) after the membership expired
DELETION_DELAY_S = 30 * 24 * 3600
# Halfway reminder threshold
_MIDWAY_S = DELETION_DELAY_S // 2
# Minimum delay between the final notice and the actual deletion
_DELETION_NOTICE_DELAY = timedelta(hours=24)

# Mail types stored in vm_purge_mails (mail_type)
MAIL_EXPIRY = "expiry"
MAIL_MIDWAY = "midway"
MAIL_FINAL = "final"
MAIL_DELETION = "deletion"


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


def _vms_subject(vms: list[dict[str, Any]]) -> str:
    """Return 'VM « name »' for one VM, or 'N VM' for several."""
    return f"VM « {vms[0]['name']} »" if len(vms) == 1 else f"{len(vms)} VM"


def _vms_lines(vms: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {vm['name']} (ID {vm['vm_id']})" for vm in vms)


def _build_warning_email(
    *,
    prenom: str,
    nom: str,
    vms: list[dict[str, Any]],
    days_expired: int,
    days_remaining: int,
    midway: bool,
    settings: Settings,
) -> tuple[str, str, str]:
    """Return (subject, plain, html) for an expiry/midway email covering all of a user's VMs."""
    many = len(vms) > 1
    base_url = settings.backend_url.rstrip("/")
    subject = f"Hosting MiNET — Votre cotisation a expiré : supprimez {'vos' if many else 'votre'} {_vms_subject(vms)}"

    followup = (
        "Il s'agit du rappel de mi-parcours. Un dernier préavis vous sera envoyé 24h avant la suppression."
        if midway
        else "Vous recevrez un rappel à mi-parcours, puis un dernier préavis 24h avant la suppression."
    )
    plain = (
        f"Bonjour {prenom} {nom},\n\n"
        f"Votre cotisation MiNET a expiré il y a {days_expired} jours.\n\n"
        f"{'Machines virtuelles concernées' if many else 'Machine virtuelle concernée'} :\n{_vms_lines(vms)}\n\n"
        f"Sans cotisation à jour, {'vos VM ne peuvent plus être hébergées' if many else 'votre VM ne peut plus être hébergée'} "
        f"par MiNET. C'est à vous de {'les' if many else 'la'} supprimer, après avoir récupéré vos données "
        "(fichiers, bases de données, configurations, sauvegardes). "
        f"Vous avez {days_remaining} jours pour le faire.\n\n"
        "Vous avez deux options :\n"
        f"1. Conserver {'vos VM' if many else 'la VM'} : renouvelez votre cotisation sur https://adh6.minet.net.\n"
        "2. Ne pas renouveler : récupérez vos données, puis supprimez vous-même "
        f"{'vos VM' if many else 'votre VM'} depuis l'interface Hosting.\n\n"
        f"Si vous ne faites rien, MiNET supprimera {'les VM' if many else 'la VM'} à l'échéance, "
        f"avec {'toutes leurs' if many else 'toutes ses'} données. "
        "Cette suppression est définitive et MiNET ne conserve aucune copie.\n\n"
        f"{followup}\n"
        "Si votre cotisation a déjà été renouvelée récemment, vous pouvez ignorer ce message.\n"
        "Une question ou besoin d'aide pour récupérer vos données ? Contactez MiNET via les canaux habituels.\n\n"
        "— L'équipe MiNET"
    )

    html = jinja_env.get_template("emails/vm_warning.html").render(
        base_url=base_url,
        prenom=prenom,
        nom=nom,
        days_expired=days_expired,
        vms=vms,
        days_remaining=days_remaining,
        midway=midway,
    )

    return subject, plain, html


def _build_final_notice_email(
    *, prenom: str, nom: str, vms: list[dict[str, Any]], days_expired: int
) -> tuple[str, str, str]:
    """Return (subject, plain, html) for the 24h deletion notice."""
    many = len(vms) > 1
    subject = f"Hosting MiNET — {'Vos' if many else 'Votre'} {_vms_subject(vms)} {'seront supprimées' if many else 'sera supprimée'} dans 24h"
    plain = (
        f"Bonjour {prenom} {nom},\n\n"
        f"Votre cotisation MiNET a expiré il y a {days_expired} jours.\n"
        f"{'Vos machines virtuelles suivantes seront supprimées' if many else 'Votre machine virtuelle suivante sera supprimée'} "
        f"automatiquement dans 24h, avec {'toutes leurs' if many else 'toutes ses'} données :\n{_vms_lines(vms)}\n\n"
        "Cette suppression est définitive et MiNET ne conserve aucune copie.\n\n"
        f"Dernière chance : récupérez dès maintenant vos données et supprimez vous-même {'vos VM' if many else 'votre VM'}, "
        f"ou renouvelez votre cotisation sur https://adh6.minet.net pour {'les' if many else 'la'} conserver.\n\n"
        "— L'équipe MiNET"
    )
    html = jinja_env.get_template("emails/vm_deletion_notice.html").render(
        prenom=prenom, nom=nom, vms=vms, days_expired=days_expired
    )
    return subject, plain, html


def _build_deleted_email(*, prenom: str, nom: str, vms: list[dict[str, Any]], days_expired: int) -> tuple[str, str, str]:
    """Return (subject, plain, html) for the post-deletion email."""
    many = len(vms) > 1
    subject = f"Hosting MiNET — {'Vos' if many else 'Votre'} {_vms_subject(vms)} {'ont été supprimées' if many else 'a été supprimée'}"
    plain = (
        f"Bonjour {prenom} {nom},\n\n"
        f"Votre cotisation MiNET a expiré il y a {days_expired} jours (plus d'un mois).\n"
        f"{'Vos machines virtuelles suivantes ont été supprimées' if many else 'Votre machine virtuelle suivante a été supprimée'} "
        f"automatiquement :\n{_vms_lines(vms)}\n\n"
        "— L'équipe MiNET"
    )
    html = jinja_env.get_template("emails/vm_deleted.html").render(prenom=prenom, nom=nom, vms=vms)
    return subject, plain, html


async def _last_mail_sent_at(db: AsyncSession, vm_id: int, mail_type: str, since: datetime) -> datetime | None:
    """Return when a mail of ``mail_type`` was last sent for this VM since ``since``, or None.

    ``since`` is the membership expiry date: mails from an earlier expiry
    (owner renewed, then expired again) must not count for the current one.
    """
    result = await db.execute(
        select(func.max(VMPurgeMail.sent_at)).where(
            VMPurgeMail.vm_id == vm_id,
            VMPurgeMail.mail_type == mail_type,
            VMPurgeMail.sent_at >= since,
        )
    )
    return result.scalar_one_or_none()


async def _record_mail(db: AsyncSession, vm_id: int | None, mail_type: str, *, vm_name: str, owner_id: str) -> None:
    """Insert a VMPurgeMail row and flush (caller commits).

    ``vm_name``/``owner_id`` are captured now because the row must stay
    meaningful even after the VM is deleted (vm_id is set to NULL then, or
    passed as None for mails recorded once the VM is already gone).
    """
    db.add(VMPurgeMail(vm_id=vm_id, mail_type=mail_type, vm_name=vm_name, owner_id=owner_id))
    await db.flush()


async def _delete_vm(
    vm_id: int,
    *,
    gateway: ProxmoxGateway,
    cmd_repo: VmCmdRepo,
    dns: DnsService,
    db: AsyncSession,
) -> bool:
    """Stop and delete one VM from Proxmox, DB and DNS. Return True if it is gone."""
    try:
        status_payload = await asyncio.to_thread(gateway.get_vm_status, vm_id=vm_id)
    except ProxmoxError:
        logger.exception("purge: failed to get status for vm %s, skipping", vm_id)
        return False

    if str(status_payload.get("status", "")).lower() != "stopped":
        try:
            await asyncio.to_thread(gateway.stop_vm, vm_id=vm_id)
        except ProxmoxError:
            logger.exception("purge: failed to stop vm %s before deletion, skipping", vm_id)
            return False

    try:
        await asyncio.to_thread(gateway.delete_vm, vm_id=vm_id)
    except ProxmoxError:
        logger.exception("purge: failed to delete vm %s from Proxmox", vm_id)
        return False

    try:
        await cmd_repo.release_ip_history(vm_id)
        await cmd_repo.delete_vm_with_related(vm_id)
        await db.commit()
    except (SQLAlchemyError, OSError):
        await db.rollback()
        logger.exception("purge: failed to delete vm %s from DB (Proxmox already deleted)", vm_id)
        return False

    await dns.delete_records(vm_id=vm_id)
    return True


async def run_purge(
    *,
    db: AsyncSession,
    gateway: ProxmoxGateway | None,
    settings: Settings,
) -> dict[str, Any]:
    """Run one purge cycle.

    - Fetches members of the hosting/ended group (expired memberships).
    - Groups their VMs by owner and checks how long ago the membership expired.
    - Sends each owner one expiry mail, one halfway mail and one final 24h notice
      (per expiry), each listing all of their VMs.
    - Deletes the VMs if 1 month has passed and the final notice is 24h old (only when Proxmox is configured).

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
    logger.info("purge: %d expired members, %d VMs to evaluate", len(expired_members), len(all_vms))

    warned = 0
    deleted = 0
    mails_sent: list[tuple[str, str]] = []
    deleted_vms: list[tuple[int, int]] = []

    members_by_id = {m["id"]: m for m in expired_members if m.get("id")}
    vms_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for vm in all_vms:
        if vm.get("owner_id"):
            vms_by_owner[vm["owner_id"]].append(vm)

    for owner_id, vms in vms_by_owner.items():
        member = members_by_id.get(owner_id)
        if not member:
            continue

        # Resolve by Keycloak id (already known via owner_id), not by username: the
        # federated user storage's username search is a substring match that ignores
        # Keycloak's `exact` flag, and can silently return an unrelated account whose
        # login merely contains the search string (see fetch_keycloak_user_by_id).
        profile = await fetch_keycloak_user_by_id_async(owner_id)
        cotise_end_ms = _cotise_end_from_profile(profile, settings.auth_cotise_end_claim.strip(), settings.auth_departure_date_claim.strip())

        if cotise_end_ms is None:
            logger.warning("purge: cannot determine cotise_end for user %s, skipping %d vm(s)", owner_id, len(vms))
            continue

        email = member.get("email")
        if not email:
            logger.error("purge: user %s has no email, skipping %d vm(s)", owner_id, len(vms))
            continue

        cotise_end = datetime.fromtimestamp(cotise_end_ms / 1000, tz=UTC)
        elapsed_seconds = (now - cotise_end).total_seconds()
        days_expired = max(0, int(elapsed_seconds / 86400))
        days_remaining = max(0, int((DELETION_DELAY_S - elapsed_seconds) / 86400))
        prenom = member.get("first_name") or "Utilisateur"
        nom = member.get("last_name") or ""

        logger.info(
            "purge: user %s (%d vm) cotise_end=%s days_expired=%d days_remaining=%d",
            owner_id, len(vms), cotise_end.date(), days_expired, days_remaining,
        )

        if elapsed_seconds >= DELETION_DELAY_S:
            # Final notice: one mail listing all of the user's VMs, recorded per VM.
            # A VM is only deleted once its notice is at least 24h old, so deletion
            # can never follow the notice too closely (restart, redeploy, drift).
            last_final = {vm["vm_id"]: await _last_mail_sent_at(db, vm["vm_id"], MAIL_FINAL, cotise_end) for vm in vms}
            unnotified = [vm for vm in vms if last_final[vm["vm_id"]] is None]

            if unnotified:
                subject, plain, html = _build_final_notice_email(prenom=prenom, nom=nom, vms=vms, days_expired=days_expired)
                await send_email_async(to_email=email, subject=subject, plain=plain, html=html, settings=settings)
                try:
                    for vm in unnotified:
                        await _record_mail(db, vm["vm_id"], MAIL_FINAL, vm_name=vm["name"], owner_id=owner_id)
                    await db.commit()
                except SQLAlchemyError:
                    await db.rollback()
                    logger.warning("purge: failed to record final notice for user %s", owner_id)
                warned += 1
                mails_sent.append((owner_id, f"préavis 24h avant suppression ({len(vms)} VM)"))
                logger.info("purge: sent final notice to user %s for %d vm(s)", owner_id, len(vms))

            deletable = [
                vm for vm in vms
                if last_final[vm["vm_id"]] is not None and (now - last_final[vm["vm_id"]]) >= _DELETION_NOTICE_DELAY
            ]
            if not deletable:
                continue

            if gateway is None or not settings.proxmox_configured:
                logger.info(
                    "purge: %d vm(s) of user %s eligible for deletion (expired %d days) but Proxmox not configured — skipping",
                    len(deletable), owner_id, days_expired,
                )
                continue

            deleted_here = [vm for vm in deletable if await _delete_vm(vm["vm_id"], gateway=gateway, cmd_repo=cmd_repo, dns=dns, db=db)]
            for vm in deleted_here:
                deleted += 1
                deleted_vms.append((vm["vm_id"], days_expired))
                logger.info("purge: vm %s deleted (owner=%s, expired %d days)", vm["vm_id"], owner_id, days_expired)

            # Mail only once the VMs are really gone, and only for those that were.
            if deleted_here:
                subject, plain, html = _build_deleted_email(prenom=prenom, nom=nom, vms=deleted_here, days_expired=days_expired)
                await send_email_async(to_email=email, subject=subject, plain=plain, html=html, settings=settings)
                try:
                    for vm in deleted_here:
                        # vm_id=None: the VM row is already deleted, so the FK would fail.
                        await _record_mail(db, None, MAIL_DELETION, vm_name=vm["name"], owner_id=owner_id)
                    await db.commit()
                except SQLAlchemyError:
                    await db.rollback()
                    logger.warning("purge: failed to record deletion mail for user %s", owner_id)

        else:
            # Not yet 1 month — one mail when the membership expired, one halfway.
            mail_type = MAIL_MIDWAY if elapsed_seconds >= _MIDWAY_S else MAIL_EXPIRY
            unnotified = [vm for vm in vms if await _last_mail_sent_at(db, vm["vm_id"], mail_type, cotise_end) is None]
            if not unnotified:
                logger.debug("purge: %s mail already sent to user %s, skipping", mail_type, owner_id)
                continue

            subject, plain, html = _build_warning_email(
                prenom=prenom,
                nom=nom,
                vms=vms,
                days_expired=days_expired,
                days_remaining=days_remaining,
                midway=mail_type == MAIL_MIDWAY,
                settings=settings,
            )
            await send_email_async(to_email=email, subject=subject, plain=plain, html=html, settings=settings)
            try:
                for vm in unnotified:
                    await _record_mail(db, vm["vm_id"], mail_type, vm_name=vm["name"], owner_id=owner_id)
                await db.commit()
            except SQLAlchemyError:
                await db.rollback()
                logger.warning("purge: failed to record %s mail for user %s", mail_type, owner_id)
            warned += 1
            mails_sent.append((owner_id, f"{'rappel à mi-parcours' if mail_type == MAIL_MIDWAY else 'avertissement'} ({len(vms)} VM)"))
            logger.info(
                "purge: sent %s mail to user %s for %d vm(s) (expired %d days, %d remaining)",
                mail_type, owner_id, len(vms), days_expired, days_remaining,
            )

    await dns.close()
    await notify_purge_summary(mails_sent=mails_sent, deleted_vms=deleted_vms)
    result = {"warned": warned, "deleted": deleted}
    logger.info("purge: done — %s", result)
    return result
