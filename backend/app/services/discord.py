"""Discord webhook notifications for VM requests and errors."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ROLE_REQUEST = "1089829786651730010"
ROLE_ERROR = "1029835701803569152"


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
    description = f"**VM** `{vm_id}`\n**Type:** {request_type}"
    if dns_label:
        description += f"\n**DNS Label:** `{dns_label}`"
    description += f"\n**User:** `{user_id}`"

    embed = {
        "title": f"Nouvelle request {request_type.upper()} — VM {vm_id}",
        "description": description,
        "color": 0x3498DB,
    }
    await _send_webhook(content="", embeds=[embed])


async def notify_ipv4_exhausted(*, vm_id: int, user_id: str) -> None:
    """Notify Discord that the IPv4 pool is exhausted."""
    embed = {
        "title": "Plus d'IPv4 disponibles !",
        "description": (
            f"**VM** `{vm_id}` — l'utilisateur `{user_id}` a tenté de demander "
            f"une IPv4 mais le pool est épuisé."
        ),
        "color": 0xE74C3C,
    }
    await _send_webhook(content=f"<@&{ROLE_ERROR}>", embeds=[embed])
