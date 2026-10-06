"""Discord webhook notifications for VM requests and errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ROLE_REQUEST = "1089829786651730010"
ROLE_ERROR = "1029835701803569152"

def _base_url() -> str:
    return get_settings().backend_url.rstrip("/")


PINGUIN_ACCES_REFUSED = "/assets/pinguins/PinguinAccesRefused.png"
PINGUIN_HEUREUX = "/assets/pinguins/PenguinHeureux.png"
PINGUIN_CABLE = "/assets/pinguins/PinguinCable.png"

_ENV_LABELS: dict[str, tuple[str, int]] = {
    "prod": ("PROD", 0x2ECC71),
    "production": ("PROD", 0x2ECC71),
    "preprod": ("PRE-PROD", 0xF39C12),
    "pre-prod": ("PRE-PROD", 0xF39C12),
}


def _env_tag() -> str:
    """Return a short environment label for embed titles."""
    env = get_settings().app_env.lower()
    label, _ = _ENV_LABELS.get(env, (env.upper(), 0x95A5A6))
    return label


def _env_color(default: int) -> int:
    """Return the embed color matching the environment, or *default* for prod."""
    env = get_settings().app_env.lower()
    if env in {"prod", "production"}:
        return default
    _, color = _ENV_LABELS.get(env, (None, 0x95A5A6))
    return color


async def _send_webhook(content: str, embeds: list[dict] | None = None) -> None:
    """Send a message to the configured Discord webhook. Best-effort."""
    settings = get_settings()
    url = settings.discord_webhook_url
    if not url:
        return
    payload: dict = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception:
        logger.warning("Failed to send Discord webhook", exc_info=True)


async def notify_new_request(
    *,
    vm_id: int,
    user_id: str,
    request_type: str,
    request_id: int | None = None,
    dns_label: str | None = None,
) -> None:
    """Notify Discord that a new request has been created."""
    tag = _env_tag()
    base_url = _base_url()
    # Deep-link to the request itself so the admin page can auto-open the
    # validation modal; fall back to the VM anchor when the id is unknown.
    anchor = f"req-{request_id}" if request_id is not None else f"vm-{vm_id}"
    deep_link = f"{base_url}/admin#{anchor}"
    fields = [
        {"name": "VM", "value": f"[`#{vm_id}`]({deep_link})", "inline": True},
        {"name": "Type", "value": request_type.upper(), "inline": True},
    ]
    if dns_label:
        fields.append({"name": "DNS Label", "value": f"`{dns_label}`", "inline": True})

    embed = {
        "title": f"[{tag}] Nouvelle demande : {request_type.upper()}",
        "url": deep_link,
        "color": _env_color(0x3498DB),
        "thumbnail": {"url": f"{_base_url()}{PINGUIN_CABLE}"},
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content=f"<@&{ROLE_REQUEST}>", embeds=[embed])


async def notify_request_approved(
    *,
    vm_id: int,
    request_type: str,
    approved_by: str,
    dns_label: str | None = None,
) -> None:
    """Notify Discord that an admin approved a request."""
    tag = _env_tag()
    base_url = _base_url()
    fields = [
        {"name": "VM", "value": f"[`#{vm_id}`]({base_url}/vm/{vm_id})", "inline": True},
        {"name": "Type", "value": request_type.upper(), "inline": True},
        {"name": "Acceptée par", "value": f"`{approved_by}`", "inline": True},
    ]
    if dns_label:
        fields.append({"name": "DNS Label", "value": f"`{dns_label}`", "inline": True})

    embed = {
        "title": f"[{tag}] Demande acceptée : {request_type.upper()}",
        "color": _env_color(0x2ECC71),
        "thumbnail": {"url": f"{_base_url()}{PINGUIN_HEUREUX}"},
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_request_denied(
    *,
    vm_id: int,
    request_type: str,
    denied_by: str,
    dns_label: str | None = None,
) -> None:
    """Notify Discord that an admin denied (rejected) a request."""
    tag = _env_tag()
    base_url = _base_url()
    fields = [
        {"name": "VM", "value": f"[`#{vm_id}`]({base_url}/admin#vm-{vm_id})", "inline": True},
        {"name": "Type", "value": request_type.upper(), "inline": True},
        {"name": "Refusée par", "value": f"`{denied_by}`", "inline": True},
    ]
    if dns_label:
        fields.append({"name": "DNS Label", "value": f"`{dns_label}`", "inline": True})

    embed = {
        "title": f"[{tag}] Demande refusée : {request_type.upper()}",
        "color": _env_color(0xE74C3C),
        "thumbnail": {"url": f"{_base_url()}{PINGUIN_ACCES_REFUSED}"},
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_dns_revoked(
    *,
    vm_id: int,
    revoked_by: str,
    dns_label: str | None = None,
) -> None:
    """Notify Discord that an admin revoked a DNS record."""
    tag = _env_tag()
    base_url = _base_url()
    fields = [
        {"name": "VM", "value": f"[`#{vm_id}`]({base_url}/vm/{vm_id})", "inline": True},
        {"name": "Type", "value": "DNS", "inline": True},
        {"name": "Révoquée par", "value": f"`{revoked_by}`", "inline": True},
    ]
    if dns_label:
        fields.append({"name": "DNS Label", "value": f"`{dns_label}`", "inline": True})

    embed = {
        "title": f"[{tag}] Demande révoquée : DNS",
        "color": _env_color(0xE74C3C),
        "thumbnail": {"url": f"{_base_url()}{PINGUIN_ACCES_REFUSED}"},
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_purge_summary(
    *,
    mails_sent: list[tuple[str, str]],
    deleted_vms: list[tuple[int, int]],
) -> None:
    """Notify Discord with a single recap of one purge cycle.

    Sends nothing if the cycle did nothing (no mail, no deletion).

    :param mails_sent: ``(owner_id, label)`` pairs, one per mail sent this cycle.
    :param deleted_vms: ``(vm_id, days_expired)`` pairs, one per VM deleted this cycle.
    """
    if not mails_sent and not deleted_vms:
        return

    tag = _env_tag()

    def short_id(owner_id: str) -> str:
        return owner_id.rsplit(":", 1)[-1]

    fields = []
    if mails_sent:
        lines = "\n".join(
            f"`{i}.` #{short_id(owner_id)}, {label}"
            for i, (owner_id, label) in enumerate(mails_sent, start=1)
        )
        fields.append({"name": f"📧 Mails envoyés ({len(mails_sent)})", "value": lines, "inline": False})
    if deleted_vms:
        lines = "\n".join(
            f"`{i}.` VM #{vm_id}, expiré depuis {days_expired} jours"
            for i, (vm_id, days_expired) in enumerate(deleted_vms, start=1)
        )
        fields.append({"name": f"🗑️ Suppressions ({len(deleted_vms)})", "value": lines, "inline": False})

    embed = {
        "title": f"🧹 [{tag}] Purge des cotisations expirées",
        "description": f"Cycle terminé : {len(mails_sent)} mails envoyés, {len(deleted_vms)} VM supprimée(s).",
        "color": _env_color(0x5865F2),
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_ipv4_exhausted() -> None:
    """Notify Discord that the IPv4 pool is exhausted."""
    tag = _env_tag()
    embed = {
        "title": f"[{tag}] Pool IPv4 épuisé",
        "description": "La dernière adresse IPv4 disponible a été attribuée.",
        "color": _env_color(0xE74C3C),
        "thumbnail": {"url": f"{_base_url()}{PINGUIN_ACCES_REFUSED}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content=f"<@&{ROLE_ERROR}>", embeds=[embed])
