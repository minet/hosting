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
    env = get_settings().app_env.lower()
    if env in {"preprod", "pre-prod"}:
        return "https://hosting-dev.minet.net"
    return "https://hosting.minet.net"


PINGUIN_ACCES_REFUSED = "/assets/pinguins/PinguinAccesRefused.png"

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
    dns_label: str | None = None,
) -> None:
    """Notify Discord that a new request has been created."""
    tag = _env_tag()
    fields = [
        {"name": "VM", "value": f"`{vm_id}`", "inline": True},
        {"name": "Type", "value": request_type.upper(), "inline": True},
    ]
    if dns_label:
        fields.append({"name": "DNS Label", "value": f"`{dns_label}`", "inline": True})

    embed = {
        "title": f"[{tag}] Nouvelle demande — {request_type.upper()}",
        "color": _env_color(0x3498DB),
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
        "title": f"[{tag}] Demande acceptée — {request_type.upper()}",
        "color": _env_color(0x2ECC71),
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"Hosting MiNET • {tag}"},
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_vm_purge_deleted(*, vm_id: int, vm_name: str, days_expired: int) -> None:
    """Notify Discord that a VM has been deleted by the purge (expired membership)."""
    tag = _env_tag()
    embed = {
        "title": f"[{tag}] VM supprimée — cotisation expirée",
        "description": f"La VM **{vm_name}** (`#{vm_id}`) a été supprimée automatiquement après {days_expired} jours de cotisation expirée.",
        "color": _env_color(0xE74C3C),
        "fields": [
            {"name": "VM", "value": f"`{vm_name}` (#{vm_id})", "inline": True},
            {"name": "Expiré depuis", "value": f"{days_expired} jours", "inline": True},
        ],
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
