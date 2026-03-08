"""
DNS provisioning service.

Manages A and AAAA records on a PowerDNS authoritative server via its
REST API.  Each VM gets a record ``{sanitized_name}-{vm_id}.{zone}``
pointing to its IPv4 and/or IPv6 address.

All errors are logged and swallowed — DNS is best-effort and must never
block VM creation or deletion.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_INVALID_LABEL_CHARS = re.compile(r"[^a-z0-9-]+")


def _sanitize(name: str) -> str:
    """Lowercase and strip characters invalid in a DNS label.

    :param name: Raw VM name.
    :returns: DNS-safe label (lowercase alphanumeric + hyphens).
    :rtype: str
    """
    label = name.lower()
    label = _INVALID_LABEL_CHARS.sub("-", label)
    return label.strip("-") or "vm"


class DnsService:
    """Thin client around the PowerDNS HTTP API for VM record management."""

    def __init__(self, *, settings: Settings) -> None:
        """
        Initialise the DNS service.

        :param settings: Application settings providing PowerDNS connection
            details and the managed DNS zone.
        """
        self._api_url = settings.pdns_api_url
        self._api_key = settings.pdns_api_key
        self._zone = settings.dns_zone.rstrip(".")

    @property
    def _enabled(self) -> bool:
        return bool(self._api_url and self._api_key and self._zone)

    def _fqdn(self, vm_name: str, vm_id: int) -> str:
        label = f"{_sanitize(vm_name)}-{vm_id}"
        return f"{label}.{self._zone}."

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key, "Content-Type": "application/json"}

    def _zone_url(self) -> str:
        return f"{self._api_url}/api/v1/servers/localhost/zones/{self._zone}."

    def _ensure_zone(self, client: httpx.Client) -> None:
        """Create the zone in PowerDNS if it does not already exist."""
        resp = client.get(self._zone_url())
        if resp.status_code == 200:
            return
        client.post(
            f"{self._api_url}/api/v1/servers/localhost/zones",
            json={
                "name": f"{self._zone}.",
                "kind": "Native",
                "nameservers": [f"ns1.{self._zone}."],
            },
        )

    def create_records(
        self,
        *,
        vm_name: str,
        vm_id: int,
        ipv4: str | None,
        ipv6: str | None,
    ) -> None:
        """Create A and/or AAAA records for a new VM.

        :param vm_name: Human-readable VM name (will be sanitized).
        :param vm_id: Numeric VM identifier (makes the label unique).
        :param ipv4: IPv4 address, or ``None`` if not assigned.
        :param ipv6: IPv6 address (CIDR or plain), or ``None``.
        """
        if not self._enabled:
            return
        fqdn = self._fqdn(vm_name, vm_id)
        rrsets = []
        if ipv4:
            rrsets.append(_rrset(fqdn, "A", ipv4.split("/")[0]))
        if ipv6:
            rrsets.append(_rrset(fqdn, "AAAA", ipv6.split("/")[0]))
        if not rrsets:
            return
        try:
            with _client(self._headers()) as c:
                self._ensure_zone(c)
                resp = c.patch(self._zone_url(), json={"rrsets": rrsets})
                resp.raise_for_status()
            logger.info("dns_create_ok fqdn=%s", fqdn)
        except Exception:
            logger.warning("dns_create_failed fqdn=%s", fqdn, exc_info=True)

    def delete_records(self, *, vm_name: str, vm_id: int) -> None:
        """Remove all DNS records for a VM.

        :param vm_name: Human-readable VM name.
        :param vm_id: Numeric VM identifier.
        """
        if not self._enabled:
            return
        fqdn = self._fqdn(vm_name, vm_id)
        rrsets = [
            {"name": fqdn, "type": "A",    "changetype": "DELETE"},
            {"name": fqdn, "type": "AAAA", "changetype": "DELETE"},
        ]
        try:
            with _client(self._headers()) as c:
                resp = c.patch(self._zone_url(), json={"rrsets": rrsets})
                resp.raise_for_status()
            logger.info("dns_delete_ok fqdn=%s", fqdn)
        except Exception:
            logger.warning("dns_delete_failed fqdn=%s", fqdn, exc_info=True)


def _rrset(name: str, rtype: str, content: str, ttl: int = 300) -> dict:
    return {
        "name": name,
        "type": rtype,
        "ttl": ttl,
        "changetype": "REPLACE",
        "records": [{"content": content, "disabled": False}],
    }


def _client(headers: dict[str, str]) -> httpx.Client:
    return httpx.Client(headers=headers, timeout=5.0)
