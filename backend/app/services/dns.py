"""
DNS provisioning service.

Manages A and AAAA records on a PowerDNS authoritative server via its
REST API.  Each VM gets a record ``{sanitized_name}-{vm_id}.{zone}``
pointing to its IPv4 and/or IPv6 address.

All errors are logged and swallowed — DNS is best-effort and must never
block VM creation or deletion.
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import struct

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
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> DnsService:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit the async context manager, closing the HTTP client."""
        await self.close()

    def _get_client(self) -> httpx.AsyncClient:
        """Return a shared async HTTP client, creating it lazily."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=self._headers(), timeout=5.0)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def _enabled(self) -> bool:
        return bool(self._api_url and self._api_key and self._zone)

    def _fqdn(self, vm_id: int) -> str:
        return f"{vm_dns_label(vm_id)}.{self._zone}."

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key or "", "Content-Type": "application/json"}

    def _zone_url(self) -> str:
        return f"{self._api_url}/api/v1/servers/localhost/zones/{self._zone}."

    async def _ensure_zone(self, client: httpx.AsyncClient) -> None:
        """Create the zone in PowerDNS if it does not already exist."""
        resp = await client.get(self._zone_url())
        if resp.status_code == 200:
            zone = resp.json()
            if zone.get("soa_edit_api") != "INCREASE":
                await client.put(self._zone_url(), json={"kind": "Native", "soa_edit_api": "INCREASE"})
            return
        await client.post(
            f"{self._api_url}/api/v1/servers/localhost/zones",
            json={
                "name": f"{self._zone}.",
                "kind": "Native",
                "nameservers": self._nameservers,
                "soa_edit_api": "INCREASE",
            },
        )

    async def create_records(
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
            c = self._get_client()
            await self._ensure_zone(c)
            resp = await c.patch(self._zone_url(), json={"rrsets": rrsets})
            resp.raise_for_status()
            logger.info("dns_create_ok fqdn=%s", fqdn)
            await self.notify()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("dns_create_failed fqdn=%s: %s", fqdn, exc)

    async def create_custom_label(
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
            c = self._get_client()
            await self._ensure_zone(c)
            resp = await c.patch(self._zone_url(), json={"rrsets": rrsets})
            resp.raise_for_status()
            logger.info("dns_custom_label_ok label=%s target=%s", custom_fqdn, target_fqdn)
            await self.notify()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("dns_custom_label_failed label=%s: %s", custom_fqdn, exc)
            if raise_on_error:
                raise

    async def delete_custom_label(
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
            c = self._get_client()
            await self._ensure_zone(c)
            resp = await c.patch(self._zone_url(), json={"rrsets": rrsets})
            resp.raise_for_status()
            logger.info("dns_custom_label_deleted label=%s", custom_fqdn)
            await self.notify()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("dns_custom_label_delete_failed label=%s: %s", custom_fqdn, exc)
            if raise_on_error:
                raise

    async def create_and_verify_custom_dns(
        self,
        *,
        dns_label: str,
        vm_id: int,
        db: Any,
    ) -> None:
        """Create a custom DNS CNAME and verify it appears in the PowerDNS DB.

        Raises on any failure so the admin caller sees what went wrong.

        :param dns_label: Custom DNS label chosen by the user.
        :param vm_id: Numeric VM identifier.
        :param db: SQLAlchemy async session for verification query.
        :raises RuntimeError: If PowerDNS is not configured.
        :raises Exception: On DNS API failure.
        """
        if not dns_label:
            raise ValueError("DNS label is required")
        await self.create_custom_label(dns_label=dns_label, vm_id=vm_id, raise_on_error=True)

        # Verify the CNAME is now visible in the DB
        from sqlalchemy import text

        expected_name = f"{dns_label}.{self._zone}"
        row = (await db.execute(
            text("SELECT name, type, content FROM records WHERE type = 'CNAME' AND name = :name"),
            {"name": expected_name},
        )).first()
        if row:
            logger.info("dns_cname_verified name=%s content=%s", row[0], row[2])
        else:
            logger.warning(
                "dns_cname_NOT_FOUND after creation: expected name=%s",
                expected_name,
            )

    async def notify(self) -> None:
        """Send DNS NOTIFY packets directly to BIND secondaries via UDP."""
        if not self._enabled:
            return
        targets = _nameserver_ips(self._nameservers)
        if not targets:
            logger.warning("dns_notify_no_targets zone=%s", self._zone)
            return
        packet = _build_notify_packet(self._zone)
        loop = asyncio.get_running_loop()
        for ip in targets:
            try:
                await loop.run_in_executor(None, _send_udp, ip, 53, packet)
                logger.info("dns_notify_sent zone=%s target=%s", self._zone, ip)
            except OSError as exc:
                logger.warning("dns_notify_failed zone=%s target=%s: %s", self._zone, ip, exc)

    async def delete_records(self, *, vm_id: int) -> None:
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
            c = self._get_client()
            # Find CNAMEs pointing to this VM's FQDN
            resp = await c.get(self._zone_url())
            if resp.status_code == 200:
                zone_data = resp.json()
                for rrset in zone_data.get("rrsets", []):
                    if rrset.get("type") == "CNAME":
                        for rec in rrset.get("records", []):
                            target = rec.get("content", "").rstrip(".")
                            if target == fqdn_no_dot:
                                rrsets.append({"name": rrset["name"], "type": "CNAME", "changetype": "DELETE"})
            resp = await c.patch(self._zone_url(), json={"rrsets": rrsets})
            resp.raise_for_status()
            logger.info("dns_delete_ok fqdn=%s rrsets=%d", fqdn, len(rrsets))
            await self.notify()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("dns_delete_failed fqdn=%s: %s", fqdn, exc)


def _nameserver_ips(nameservers: list[str]) -> list[str]:
    """Extract IPs from nameserver FQDNs by resolving them."""
    ips = []
    for ns in nameservers:
        ns = ns.rstrip(".")
        try:
            results = socket.getaddrinfo(ns, None, socket.AF_INET, socket.SOCK_DGRAM)
            for _, _, _, _, addr in results:
                if addr[0] not in ips:
                    ips.append(addr[0])
        except socket.gaierror:
            logger.warning("dns_notify_resolve_failed ns=%s", ns)
    return ips


def _build_notify_packet(zone: str) -> bytes:
    """Build a minimal DNS NOTIFY packet for the given zone."""
    # Header: ID=0x1234, flags=0x2400 (opcode NOTIFY + AA), QDCOUNT=1
    header = struct.pack("!HHHHHH", 0x1234, 0x2400, 1, 0, 0, 0)
    # Question: zone name, type SOA (6), class IN (1)
    qname = b""
    for label in zone.split("."):
        qname += struct.pack("!B", len(label)) + label.encode()
    qname += b"\x00"
    question = qname + struct.pack("!HH", 6, 1)
    return header + question


def _send_udp(ip: str, port: int, data: bytes) -> None:
    """Send a UDP packet."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.sendto(data, (ip, port))


def _rrset(name: str, rtype: str, content: str, ttl: int = 300) -> dict:
    return {
        "name": name,
        "type": rtype,
        "ttl": ttl,
        "changetype": "REPLACE",
        "records": [{"content": content, "disabled": False}],
    }


