"""Utility helpers for Proxmox node resolution, disk parsing, and VM introspection."""

from __future__ import annotations

import re
import time
from typing import Any

from proxmoxer import ProxmoxAPI

from app.core.config import get_settings

# TTL cache for VM → node mapping to avoid repeated cluster/resources calls.
_vm_node_cache: dict[int, tuple[str, float]] = {}
_VM_NODE_TTL: float = 60.0  # seconds


def task_node() -> str:
    """Return the configured Proxmox node name, defaulting to ``"pve"``.

    :returns: The Proxmox node name.
    :rtype: str
    """
    return get_settings().proxmox_node.strip() or "pve"


def _any_online_node(*, client: ProxmoxAPI) -> str | None:
    """Return the name of any online node in the cluster.

    :param client: Proxmox API client instance.
    :returns: Name of an online node, or ``None`` if none are available.
    :rtype: str | None
    """
    raw_nodes = client.nodes.get()
    if not isinstance(raw_nodes, list):
        return None
    for item in raw_nodes:
        if (
            isinstance(item, dict)
            and item.get("status") == "online"
            and isinstance(item.get("node"), str)
            and item["node"].strip()
        ):
            return item["node"].strip()
    return None


def task_timeout_seconds() -> int:
    """Return the task timeout in seconds (at least 10).

    :returns: Timeout value in seconds.
    :rtype: int
    """
    value = get_settings().proxmox_task_timeout_seconds
    return max(int(value), 10)


def _cluster_vm_resources(*, client: ProxmoxAPI) -> list[dict[str, Any]]:
    """Fetch all VM-type resources from the Proxmox cluster.

    :param client: Proxmox API client instance.
    :returns: List of resource dicts for VMs.
    :rtype: list[dict[str, Any]]
    """
    resources = client.cluster.resources.get(type="vm")
    if not isinstance(resources, list):
        return []
    return [item for item in resources if isinstance(item, dict)]


def template_node_from_cluster(*, client: ProxmoxAPI, template_vmid: int) -> str | None:
    """Locate the node hosting a template VM.

    :param client: Proxmox API client instance.
    :param template_vmid: The VMID of the template to look up.
    :returns: The node name, or ``None`` if not found.
    :rtype: str | None
    """
    for item in _cluster_vm_resources(client=client):
        vmid = _as_int(item.get("vmid"))
        if vmid != template_vmid:
            continue
        node = item.get("node")
        if isinstance(node, str) and node.strip():
            return node.strip()
    return None


def clone_node_for_template(*, client: ProxmoxAPI, template_vmid: int) -> str:
    """Return the node hosting a template, falling back to any online node.

    :param client: Proxmox API client instance.
    :param template_vmid: The VMID of the template.
    :returns: The node name to use for cloning.
    :rtype: str
    :raises ProxmoxError: If no node can be resolved.
    """
    from app.services.proxmox.errors import ProxmoxError

    node = template_node_from_cluster(client=client, template_vmid=template_vmid)
    if node:
        return node
    node = _any_online_node(client=client)
    if node:
        return node
    raise ProxmoxError(f"Cannot resolve node for template {template_vmid}: no online nodes found")


def vm_node_from_cluster(*, client: ProxmoxAPI, vm_id: int) -> str | None:
    """Locate the node hosting a specific VM.

    :param client: Proxmox API client instance.
    :param vm_id: The VMID of the virtual machine to look up.
    :returns: The node name, or ``None`` if not found.
    :rtype: str | None
    """
    for item in _cluster_vm_resources(client=client):
        vmid = _as_int(item.get("vmid"))
        if vmid != vm_id:
            continue
        node = item.get("node")
        if isinstance(node, str) and node.strip():
            return node.strip()
    return None


def node_for_vm(*, client: ProxmoxAPI, vm_id: int) -> str:
    """Return the node hosting a VM, with a short TTL cache.

    :param client: Proxmox API client instance.
    :param vm_id: The VMID of the virtual machine.
    :returns: The node name to use for VM operations.
    :rtype: str
    :raises ProxmoxError: If no node can be resolved.
    """
    from app.services.proxmox.errors import ProxmoxError

    now = time.monotonic()
    cached = _vm_node_cache.get(vm_id)
    if cached is not None:
        node, ts = cached
        if (now - ts) < _VM_NODE_TTL:
            return node

    node = vm_node_from_cluster(client=client, vm_id=vm_id)
    if node:
        _vm_node_cache[vm_id] = (node, now)
        return node
    node = _any_online_node(client=client)
    if node:
        return node
    raise ProxmoxError(f"Cannot resolve node for VM {vm_id}: no online nodes found")


def least_loaded_node(*, client: ProxmoxAPI) -> str | None:
    """Return the online node with the fewest VMs (excluding templates).

    Fetches the list of online nodes and counts non-template VMs per node
    from the cluster resource list, then returns the node with the minimum
    VM count.

    :param client: Proxmox API client instance.
    :returns: Name of the least loaded online node, or ``None`` if no nodes
        are available.
    :rtype: str | None
    """
    raw_nodes = client.nodes.get()
    if not isinstance(raw_nodes, list):
        return None

    online_nodes = {
        item["node"]
        for item in raw_nodes
        if isinstance(item, dict)
        and item.get("status") == "online"
        and isinstance(item.get("node"), str)
        and item["node"].strip()
    }
    if not online_nodes:
        return None

    vm_count: dict[str, int] = {node: 0 for node in online_nodes}
    for item in _cluster_vm_resources(client=client):
        if item.get("template"):
            continue
        node = item.get("node")
        if isinstance(node, str) and node in vm_count:
            vm_count[node] += 1

    return min(vm_count, key=lambda n: vm_count[n])


def used_vm_ids(*, client: ProxmoxAPI) -> set[int]:
    """Retrieve the set of all VMID integers currently present in the cluster.

    :param client: Proxmox API client instance.
    :returns: Set of integer VMIDs that are in use.
    :rtype: set[int]
    """
    result: set[int] = set()
    for item in _cluster_vm_resources(client=client):
        vmid = _as_int(item.get("vmid"))
        if vmid is not None:
            result.add(vmid)
    return result


def root_disk_key(config: dict[str, Any]) -> str | None:
    """Identify the root disk key in a VM configuration dict.

    Checks preferred keys first (``scsi0``, ``virtio0``, ``sata0``, ``ide0``),
    then falls back to any disk-like key found in the config.

    :param config: Raw VM configuration dictionary from Proxmox.
    :returns: The key name of the root disk, or ``None`` if not found.
    :rtype: str | None
    """
    preferred = ("scsi0", "virtio0", "sata0", "ide0")
    for key in preferred:
        value = config.get(key)
        if isinstance(value, str) and ":" in value:
            return key

    disk_pattern = re.compile(r"^(scsi|virtio|sata|ide)\d+$")
    for key, value in config.items():
        if disk_pattern.match(str(key)) and isinstance(value, str) and ":" in value:
            return str(key)
    return None


def disk_size_gb(config_value: str) -> int | None:
    """Parse the disk size in gigabytes from a Proxmox disk configuration string.

    Supports ``G`` (gigabytes), ``M`` (megabytes, ceiling-divided to GB), and
    ``T`` (terabytes) suffixes in the ``size=`` field.

    :param config_value: Raw disk configuration string from a Proxmox VM config.
    :returns: Disk size in whole gigabytes, or ``None`` if no size field is found.
    :rtype: int | None
    """
    match = re.search(r"(?:^|,)size=(\d+(?:\.\d+)?)G(?:,|$)", config_value)
    if match:
        return int(float(match.group(1)))
    match = re.search(r"(?:^|,)size=(\d+)M(?:,|$)", config_value)
    if match:
        mb = int(match.group(1))
        return -(-mb // 1024)  # ceiling division to GB
    match = re.search(r"(?:^|,)size=(\d+)T(?:,|$)", config_value)
    if match:
        return int(match.group(1)) * 1024
    return None


def extract_mac_from_nic_config(nic_config: str) -> str | None:
    """Extract a MAC address from a Proxmox NIC configuration string.

    Supports ``virtio``, ``e1000``, ``rtl8139``, ``vmxnet3``, and ``hwaddr``
    style configuration entries.

    :param nic_config: Raw NIC configuration string from a Proxmox VM config.
    :returns: Lowercase MAC address string, or ``None`` if not found.
    :rtype: str | None
    """
    patterns = (
        r"(?:^|,)(?:virtio|e1000|rtl8139|vmxnet3)=([0-9a-fA-F:]{17})(?:,|$)",
        r"(?:^|,)hwaddr=([0-9a-fA-F:]{17})(?:,|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, nic_config)
        if match:
            return match.group(1).lower()
    return None


def resolve_vm_mac(vm_config: dict[str, Any]) -> str | None:
    """Resolve the first available MAC address from a VM configuration.

    Prefers the standard ``net0``–``net3`` keys, then falls back to any
    key prefixed with ``net``.

    :param vm_config: Raw VM configuration dictionary from Proxmox.
    :returns: Lowercase MAC address string, or ``None`` if not found.
    :rtype: str | None
    """
    for key in ("net0", "net1", "net2", "net3"):
        value = vm_config.get(key)
        if not isinstance(value, str):
            continue
        mac = extract_mac_from_nic_config(value)
        if mac:
            return mac

    for key, value in vm_config.items():
        if not isinstance(key, str) or not key.startswith("net"):
            continue
        if not isinstance(value, str):
            continue
        mac = extract_mac_from_nic_config(value)
        if mac:
            return mac
    return None


def _as_int(value: Any) -> int | None:
    """Safely convert a value to ``int``, returning ``None`` on failure.

    :param value: The value to convert.
    :returns: Integer representation of *value*, or ``None`` if conversion fails.
    :rtype: int | None
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "clone_node_for_template",
    "disk_size_gb",
    "least_loaded_node",
    "node_for_vm",
    "resolve_vm_mac",
    "root_disk_key",
    "task_node",
    "task_timeout_seconds",
    "used_vm_ids",
]
