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
from app.services.wordgen import vm_dns_label

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
        self._nameservers = [ns.strip() for ns in settings.dns_nameservers.split(",") if ns.strip()]

    @property
    def _enabled(self) -> bool:
        return bool(self._api_url and self._api_key and self._zone)

    def _fqdn(self, vm_id: int) -> str:
        return f"{vm_dns_label(vm_id)}.{self._zone}."

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key or "", "Content-Type": "application/json"}

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
                "kind": "Master",
                "nameservers": self._nameservers,
            },
        )

    def create_records(
        self,
        *,
        vm_id: int,
        ipv4: str | None,
        ipv6: str | None,
    ) -> None:
        """Create A and/or AAAA records for a new VM.

        :param vm_id: Numeric VM identifier.
        :param ipv4: IPv4 address, or ``None`` if not assigned.
        :param ipv6: IPv6 address (CIDR or plain), or ``None``.
        """
        if not self._enabled:
            return
        fqdn = self._fqdn(vm_id)
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
                self._notify_zone(c)
            logger.info("dns_create_ok fqdn=%s", fqdn)
        except Exception:
            logger.warning("dns_create_failed fqdn=%s", fqdn, exc_info=True)

    def create_custom_label(
        self,
        *,
        dns_label: str,
        vm_id: int,
        raise_on_error: bool = False,
    ) -> None:
        """Create a CNAME record pointing a custom label to the default VM FQDN.

        :param dns_label: Custom DNS label chosen by the user (e.g. ``myapp``).
        :param vm_id: Numeric VM identifier.
        :param raise_on_error: If ``True``, exceptions are propagated to the caller
            instead of being swallowed.  Use this for admin-driven operations where
            the caller needs to know about failures.
        """
        if not self._enabled:
            if raise_on_error:
                raise RuntimeError("PowerDNS is not configured")
            return
        custom_fqdn = f"{dns_label}.{self._zone}."
        target_fqdn = self._fqdn(vm_id)
        rrsets = [_rrset(custom_fqdn, "CNAME", target_fqdn)]
        try:
            with _client(self._headers()) as c:
                self._ensure_zone(c)
                resp = c.patch(self._zone_url(), json={"rrsets": rrsets})
                resp.raise_for_status()
                self._notify_zone(c)
            logger.info("dns_custom_label_ok label=%s target=%s", custom_fqdn, target_fqdn)
        except Exception:
            logger.warning("dns_custom_label_failed label=%s", custom_fqdn, exc_info=True)
            if raise_on_error:
                raise

    def delete_custom_label(
        self,
        *,
        dns_label: str,
        raise_on_error: bool = False,
    ) -> None:
        """Remove a custom CNAME record.

        :param dns_label: The custom DNS label to remove.
        :param raise_on_error: If ``True``, propagate exceptions.
        """
        if not self._enabled:
            if raise_on_error:
                raise RuntimeError("PowerDNS is not configured")
            return
        custom_fqdn = f"{dns_label}.{self._zone}."
        rrsets = [{"name": custom_fqdn, "type": "CNAME", "changetype": "DELETE"}]
        try:
            with _client(self._headers()) as c:
                resp = c.patch(self._zone_url(), json={"rrsets": rrsets})
                resp.raise_for_status()
                self._notify_zone(c)
            logger.info("dns_custom_label_deleted label=%s", custom_fqdn)
        except Exception:
            logger.warning("dns_custom_label_delete_failed label=%s", custom_fqdn, exc_info=True)
            if raise_on_error:
                raise

    def _notify_zone(self, client: httpx.Client) -> None:
        """Trigger a NOTIFY to all zone secondaries so they pick up the change."""
        client.put(f"{self._api_url}/api/v1/servers/localhost/zones/{self._zone}./notify")

    def delete_records(self, *, vm_id: int) -> None:
        """Remove all DNS records for a VM, including CNAMEs pointing to it.

        :param vm_id: Numeric VM identifier.
        """
        if not self._enabled:
            return
        fqdn = self._fqdn(vm_id)
        # fqdn has trailing dot for the API, but PowerDNS stores without it
        fqdn_no_dot = fqdn.rstrip(".")
        rrsets = [
            {"name": fqdn, "type": "A", "changetype": "DELETE"},
            {"name": fqdn, "type": "AAAA", "changetype": "DELETE"},
        ]
        try:
            with _client(self._headers()) as c:
                # Find CNAMEs pointing to this VM's FQDN
                resp = c.get(self._zone_url())
                if resp.status_code == 200:
                    zone_data = resp.json()
                    for rrset in zone_data.get("rrsets", []):
                        if rrset.get("type") == "CNAME":
                            for rec in rrset.get("records", []):
                                target = rec.get("content", "").rstrip(".")
                                if target == fqdn_no_dot:
                                    rrsets.append({"name": rrset["name"], "type": "CNAME", "changetype": "DELETE"})
                resp = c.patch(self._zone_url(), json={"rrsets": rrsets})
                resp.raise_for_status()
                self._notify_zone(c)
            logger.info("dns_delete_ok fqdn=%s rrsets=%d", fqdn, len(rrsets))
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
