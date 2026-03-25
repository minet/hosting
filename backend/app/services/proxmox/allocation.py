"""VM ID and IPv4/IPv6 address allocation for new Proxmox virtual machines."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address

from proxmoxer import ProxmoxAPI

from app.core.config import get_settings
from app.services.proxmox.errors import ProxmoxConfigError, ProxmoxUnavailableError
from app.services.proxmox.utils import used_vm_ids


def vm_id_min() -> int:
    """Return the configured minimum VM ID.

    :returns: The minimum VM ID from application settings.
    :rtype: int
    :raises ProxmoxConfigError: If the configured minimum is less than 1.
    """
    settings = get_settings()
    minimum = int(settings.vm_id_min)
    if minimum < 1:
        raise ProxmoxConfigError("Invalid VM_ID_MIN configuration")
    return minimum


class VmIdAllocator:
    """
    Allocate VM IDs while reserving VMID 2000 for project internals.
    """

    def __init__(self, *, client: ProxmoxAPI, minimum: int):
        """Initialise the allocator.

        :param client: Proxmox API client instance.
        :param minimum: Desired minimum VM ID (clamped to at least 2001).
        """
        self._client = client
        self._minimum = max(minimum, 2001)

    def allocate(self) -> int:
        """Allocate the next available VM ID.

        :returns: An unused VM ID that is at least ``self._minimum``.
        :rtype: int
        """
        used = used_vm_ids(client=self._client)
        suggested = self._suggested_next_id()
        if self._is_usable_candidate(suggested=suggested, used=used):
            assert suggested is not None
            return suggested

        candidate = self._minimum
        while candidate in used:
            candidate += 1
        return candidate

    def _suggested_next_id(self) -> int | None:
        """Query the Proxmox cluster for its suggested next VM ID.

        :returns: The cluster-suggested ID, or ``None`` on failure.
        :rtype: int | None
        """
        try:
            return int(self._client.cluster.nextid.get())
        except Exception:
            return None

    def _is_usable_candidate(self, *, suggested: int | None, used: set[int]) -> bool:
        """Check whether *suggested* is a valid, unused candidate above the minimum.

        :param suggested: The candidate VM ID to evaluate.
        :param used: Set of VM IDs already in use.
        :returns: ``True`` if the candidate is usable, ``False`` otherwise.
        :rtype: bool
        """
        if suggested is None:
            return False
        if suggested < self._minimum:
            return False
        return suggested not in used


def allocate_vm_id(*, client: ProxmoxAPI) -> int:
    """Convenience wrapper: allocate a VM ID using settings-derived minimum.

    :param client: Proxmox API client instance.
    :returns: An unused VM ID.
    :rtype: int
    """
    return VmIdAllocator(client=client, minimum=vm_id_min()).allocate()


def ipv6_network_settings() -> tuple[IPv6Network, IPv6Address, int]:
    """Read and validate the IPv6 subnet configuration from settings.

    :returns: A tuple of (network, gateway address, prefix length).
    :rtype: tuple[IPv6Network, IPv6Address, int]
    :raises ProxmoxConfigError: If the subnet or gateway host configuration is invalid.
    """
    settings = get_settings()
    try:
        network = IPv6Network(settings.vm_ipv6_subnet, strict=False)
    except ValueError as exc:
        raise ProxmoxConfigError("Invalid VM_IPV6_SUBNET configuration") from exc

    host_space = (1 << (128 - network.prefixlen)) - 1
    gateway_host = max(int(settings.vm_ipv6_gateway_host), 1)
    if gateway_host > host_space:
        raise ProxmoxConfigError("Invalid VM_IPV6_GATEWAY_HOST for subnet")

    gateway_ip = network.network_address + gateway_host
    return network, gateway_ip, int(network.prefixlen)


def allocate_next_vm_ipv6(*, used_ipv6: set[str]) -> str:
    """Allocate the next free IPv6 address in the configured subnet.

    :param used_ipv6: Set of IPv6 address strings already in use.
    :returns: The allocated IPv6 address as a string.
    :rtype: str
    :raises ProxmoxUnavailableError: If no addresses remain in the subnet.
    """
    network, gateway_ip, _ = ipv6_network_settings()
    host_space = (1 << (128 - network.prefixlen)) - 1
    used_addresses = _parse_used_ipv6(used_ipv6=used_ipv6, network=network)

    for host in range(2, host_space + 1):
        candidate = network.network_address + host
        if candidate == gateway_ip:
            continue
        if candidate not in used_addresses:
            return str(candidate)

    raise ProxmoxUnavailableError("No available IPv6 in configured subnet")


def _parse_used_ipv6(*, used_ipv6: set[str], network: IPv6Network) -> set[IPv6Address]:
    """Parse raw IPv6 strings and keep only those belonging to *network*.

    :param used_ipv6: Raw IPv6 address strings.
    :param network: The IPv6 network to filter against.
    :returns: Set of parsed addresses that fall within *network*.
    :rtype: set[IPv6Address]
    """
    parsed: set[IPv6Address] = set()
    for raw in used_ipv6:
        try:
            value = ip_address(raw)
        except ValueError:
            continue
        if isinstance(value, IPv6Address) and value in network:
            parsed.add(value)
    return parsed


def ipv4_network_settings() -> list[tuple[IPv4Network, IPv4Address, int]]:
    """Read and validate the IPv4 subnet configuration from settings.

    Supports multiple comma-separated subnets in ``VM_IPV4_SUBNETS`` with
    matching gateway host indices in ``VM_IPV4_GATEWAY_HOSTS``.

    :returns: A list of (network, gateway address, prefix length) tuples.
    :rtype: list[tuple[IPv4Network, IPv4Address, int]]
    :raises ProxmoxConfigError: If ``VM_IPV4_SUBNETS`` is not configured or invalid.
    """
    settings = get_settings()
    if not settings.vm_ipv4_subnets:
        raise ProxmoxConfigError("VM_IPV4_SUBNETS is not configured")

    raw_subnets = [s.strip() for s in settings.vm_ipv4_subnets.split(",") if s.strip()]
    raw_gateways = [g.strip() for g in settings.vm_ipv4_gateway_hosts.split(",") if g.strip()]

    if not raw_subnets:
        raise ProxmoxConfigError("VM_IPV4_SUBNETS is empty")

    # If fewer gateway values than subnets, repeat the last one
    while len(raw_gateways) < len(raw_subnets):
        raw_gateways.append(raw_gateways[-1] if raw_gateways else "1")

    results: list[tuple[IPv4Network, IPv4Address, int]] = []
    for i, raw_subnet in enumerate(raw_subnets):
        try:
            network = IPv4Network(raw_subnet, strict=False)
        except ValueError as exc:
            raise ProxmoxConfigError(f"Invalid VM_IPV4_SUBNETS entry: {raw_subnet}") from exc

        host_space = (1 << (32 - network.prefixlen)) - 1
        try:
            gateway_host = max(int(raw_gateways[i]), 1)
        except ValueError as exc:
            raise ProxmoxConfigError(f"Invalid VM_IPV4_GATEWAY_HOSTS entry: {raw_gateways[i]}") from exc
        if gateway_host > host_space:
            raise ProxmoxConfigError(f"Invalid gateway host {gateway_host} for subnet {raw_subnet}")

        gateway_ip = network.network_address + gateway_host
        results.append((network, IPv4Address(gateway_ip), int(network.prefixlen)))

    return results


def ipv4_network_settings_for_ip(vm_ipv4: str) -> tuple[IPv4Network, IPv4Address, int]:
    """Find the subnet settings that contain the given IPv4 address.

    :param vm_ipv4: The IPv4 address to look up.
    :returns: A tuple of (network, gateway address, prefix length).
    :raises ProxmoxConfigError: If no configured subnet contains the address.
    """
    addr = IPv4Address(vm_ipv4)
    for network, gateway_ip, prefix in ipv4_network_settings():
        if addr in network:
            return network, gateway_ip, prefix
    raise ProxmoxConfigError(f"No configured subnet contains {vm_ipv4}")


def allocate_next_vm_ipv4(*, used_ipv4: set[str]) -> str:
    """Allocate the next free IPv4 address across all configured subnets.

    Iterates through subnets in order, skipping network address, gateway,
    and broadcast address in each.

    :param used_ipv4: Set of IPv4 address strings already in use.
    :type used_ipv4: set[str]
    :returns: The allocated IPv4 address as a string.
    :rtype: str
    :raises ProxmoxConfigError: If ``VM_IPV4_SUBNETS`` is not configured or invalid.
    :raises ProxmoxUnavailableError: If no addresses remain in any subnet.
    """
    all_used = _parse_all_used_ipv4(used_ipv4=used_ipv4)

    for network, gateway_ip, _ in ipv4_network_settings():
        host_space = (1 << (32 - network.prefixlen)) - 2
        broadcast = network.broadcast_address

        for host in range(2, host_space + 1):
            candidate = IPv4Address(int(network.network_address) + host)
            if candidate in (gateway_ip, broadcast):
                continue
            if candidate not in all_used:
                return str(candidate)

    raise ProxmoxUnavailableError("No available IPv4 in any configured subnet")


def _parse_all_used_ipv4(*, used_ipv4: set[str]) -> set[IPv4Address]:
    """Parse raw IPv4 strings into a set of addresses.

    :param used_ipv4: Raw IPv4 address strings.
    :returns: Set of parsed IPv4 addresses.
    :rtype: set[IPv4Address]
    """
    parsed: set[IPv4Address] = set()
    for raw in used_ipv4:
        try:
            value = ip_address(raw)
        except ValueError:
            continue
        if isinstance(value, IPv4Address):
            parsed.add(value)
    return parsed


__all__ = [
    "VmIdAllocator",
    "allocate_next_vm_ipv4",
    "allocate_next_vm_ipv6",
    "allocate_vm_id",
    "ipv4_network_settings",
    "ipv4_network_settings_for_ip",
    "ipv6_network_settings",
    "vm_id_min",
]
