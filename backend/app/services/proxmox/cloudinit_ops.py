"""Cloud-init configuration and VM firewall management for Proxmox VMs."""

from __future__ import annotations

import contextlib
from ipaddress import IPv4Address, IPv6Address
from typing import Any
from urllib.parse import quote

from proxmoxer import ProxmoxAPI

from app.services.proxmox.errors import (
    ProxmoxInvalidRequest,
    ProxmoxInvalidResponse,
    ResourceException,  # pyright: ignore[reportAttributeAccessIssue]
)
from app.services.proxmox.models import CloudInitPatchSpec
from app.services.proxmox.tasks import TaskService


class CloudInitService:
    """Cloud-init and VM firewall operations."""

    def __init__(self, *, client: ProxmoxAPI, task_service: TaskService):
        """Initialise the service with a Proxmox client and task tracker.

        :param client: Proxmox API client instance.
        :param task_service: Task tracking service for async Proxmox operations.
        """
        self._client = client
        self._tasks = task_service

    def build_initial_payload(
        self,
        *,
        cpu_cores: int,
        ram_mb: int,
        ci_username: str,
        ci_password: str | None,
        ci_ssh_public_key: str,
        vm_ipv6: str,
        ipv6_prefix: int,
        ipv6_gateway: IPv6Address,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Build the cloud-init configuration payload for a freshly cloned VM.

        :param cpu_cores: Number of CPU cores to assign.
        :param ram_mb: Amount of RAM in megabytes to assign.
        :param ci_username: Cloud-init username.
        :param ci_password: Cloud-init password, or ``None`` to omit.
        :param ci_ssh_public_key: SSH public key to inject.
        :param vm_ipv6: IPv6 address string for the VM.
        :param ipv6_prefix: Prefix length of the IPv6 network.
        :param ipv6_gateway: IPv6 gateway address.
        :returns: Dictionary suitable for posting to the Proxmox VM config endpoint.
        :rtype: dict[str, Any]
        :raises ProxmoxInvalidRequest: If the SSH public key is empty.
        """
        payload: dict[str, Any] = {
            "cores": cpu_cores,
            "memory": ram_mb,
            "ciuser": ci_username,
            "sshkeys": self._encode_cloudinit_ssh_keys(ci_ssh_public_key),
            "ipconfig0": f"ip6={vm_ipv6}/{ipv6_prefix},gw6={ipv6_gateway!s}",
        }
        if ci_password:
            payload["cipassword"] = ci_password
        if tags:
            payload["tags"] = tags
        return payload

    def update_vm_cloudinit(
        self,
        *,
        node: str,
        vm_id: int,
        spec: CloudInitPatchSpec,
        timeout_seconds: int,
    ) -> None:
        """Apply a cloud-init patch to an existing VM.

        Only fields present in *spec* are sent to Proxmox; ``None`` values are
        omitted so that existing settings are preserved.

        :param node: Proxmox node name hosting the VM.
        :param vm_id: VMID of the target virtual machine.
        :param spec: Cloud-init patch specification.
        :param timeout_seconds: Maximum seconds to wait for the task to complete.
        """
        payload: dict[str, Any] = {"ciuser": spec.ci_username}
        if spec.ci_password is not None:
            payload["cipassword"] = spec.ci_password
        if spec.ci_ssh_public_key is not None:
            payload["sshkeys"] = self._encode_cloudinit_ssh_keys(spec.ci_ssh_public_key)

        result = self._client.nodes(node).qemu(vm_id).config.post(**payload)
        self._tasks.wait_if_async(node=node, result=result, timeout_seconds=timeout_seconds)

    def enable_vm_ipv6_ipfilter(
        self,
        *,
        node: str,
        vm_id: int,
        vm_ipv6: str,
        vm_config: dict[str, Any],
    ) -> None:
        """Enable the Proxmox firewall on a VM and configure an IPv6 IP-set filter.

        Enables the NIC firewall flag, creates (or resets) the ``hosting`` IP
        set containing the VM's ``/128`` address, and installs matching
        ``ACCEPT``/``DROP`` rules for inbound and outbound traffic.

        :param node: Proxmox node name hosting the VM.
        :param vm_id: VMID of the target virtual machine.
        :param vm_ipv6: IPv6 address string to allow through the IP-set filter.
        :param vm_config: Raw VM configuration dictionary from Proxmox.
        :raises ProxmoxInvalidResponse: If the VM has no ``net0`` configuration.
        """
        net0 = self._net0_with_firewall(vm_config=vm_config)
        self._client.nodes(node).qemu(vm_id).config.post(net0=net0)

        firewall = self._client.nodes(node).qemu(vm_id).firewall
        firewall.options.put(enable=1)
        self._reset_ipset(firewall=firewall, vm_ipv6=vm_ipv6)
        self._reset_rules(firewall=firewall)

    def _net0_with_firewall(self, *, vm_config: dict[str, Any]) -> str:
        """Return the ``net0`` configuration string with ``firewall=1`` appended.

        Any existing ``firewall=`` entry is removed before the flag is added.

        :param vm_config: Raw VM configuration dictionary from Proxmox.
        :returns: Modified ``net0`` configuration string with firewall enabled.
        :rtype: str
        :raises ProxmoxInvalidResponse: If ``net0`` is absent or empty.
        """
        net0_raw = vm_config.get("net0")
        if not isinstance(net0_raw, str) or not net0_raw.strip():
            raise ProxmoxInvalidResponse("Missing net0 config on VM")

        parts = [part.strip() for part in net0_raw.split(",") if part.strip()]
        parts = [p for p in parts if not p.lower().startswith("firewall=")]
        parts.append("firewall=1")
        return ",".join(parts)

    def _reset_ipset(self, *, firewall: Any, vm_ipv6: str) -> None:
        """Delete and recreate the ``hosting`` IP set with the VM's ``/128`` CIDR.

        Silently ignores the deletion step if the IP set does not yet exist.

        :param firewall: Proxmox firewall resource object for the VM.
        :param vm_ipv6: IPv6 address to register in the IP set.
        """
        ipset_name = "hosting"
        vm_cidr = f"{vm_ipv6}/128"
        with contextlib.suppress(ResourceException):
            firewall.ipset(ipset_name).delete()
        firewall.ipset.post(name=ipset_name)
        firewall.ipset(ipset_name).post(cidr=vm_cidr)

    def _reset_rules(self, *, firewall: Any) -> None:
        """Remove all existing firewall rules and install the default hosting policy.

        The default policy accepts inbound/outbound traffic matching the
        ``hosting`` IP set and drops everything else.

        :param firewall: Proxmox firewall resource object for the VM.
        """
        raw = firewall.rules.get()
        rules = sorted(raw if isinstance(raw, list) else [], key=lambda rule: int(rule.get("pos", 0)), reverse=True)
        for rule in rules:
            pos = int(rule.get("pos", 0))
            firewall.rules(str(pos)).delete()

        # Proxmox inserts at pos=0 by default (pushing existing rules down),
        # so post in reverse desired order to end up with ACCEPT before DROP.
        firewall.rules.post(type="in", action="DROP", enable=1)
        firewall.rules.post(type="out", action="DROP", enable=1)
        firewall.rules.post(type="in", action="ACCEPT", dest="+hosting", enable=1)
        firewall.rules.post(type="out", action="ACCEPT", source="+hosting", enable=1)

    def assign_vm_ipv4(
        self,
        *,
        node: str,
        vm_id: int,
        vm_ipv4: str,
        ipv4_prefix: int,
        ipv4_gateway: IPv4Address,
    ) -> None:
        """Inject an IPv4 address into the VM's ``ipconfig0`` cloud-init setting.

        Reads the current ``ipconfig0`` from Proxmox, preserves any existing IPv6
        segments (``ip6=``, ``gw6=``), prepends the new IPv4 address and gateway,
        then posts the updated configuration.

        :param node: Proxmox node name hosting the VM.
        :type node: str
        :param vm_id: VMID of the target virtual machine.
        :type vm_id: int
        :param vm_ipv4: IPv4 address to assign.
        :type vm_ipv4: str
        :param ipv4_prefix: Prefix length of the IPv4 network (e.g. 24).
        :type ipv4_prefix: int
        :param ipv4_gateway: IPv4 gateway address.
        :type ipv4_gateway: IPv4Address
        :raises ProxmoxInvalidResponse: If the VM config cannot be retrieved.
        """
        config = self._client.nodes(node).qemu(vm_id).config.get()
        current_ipconfig0 = config.get("ipconfig0", "") if isinstance(config, dict) else ""
        new_ipconfig0 = self._build_ipconfig_with_ipv4(
            current=str(current_ipconfig0),
            vm_ipv4=vm_ipv4,
            ipv4_prefix=ipv4_prefix,
            ipv4_gateway=ipv4_gateway,
        )
        self._client.nodes(node).qemu(vm_id).config.post(ipconfig0=new_ipconfig0)

        firewall = self._client.nodes(node).qemu(vm_id).firewall
        self._add_ipv4_to_ipset(firewall=firewall, vm_ipv4=vm_ipv4)

    def _build_ipconfig_with_ipv4(
        self,
        *,
        current: str,
        vm_ipv4: str,
        ipv4_prefix: int,
        ipv4_gateway: IPv4Address,
    ) -> str:
        """Build an ``ipconfig0`` string containing both IPv4 and existing IPv6 segments.

        Any pre-existing ``ip=`` or ``gw=`` segments are discarded and replaced.

        :param current: The current raw ``ipconfig0`` value from Proxmox.
        :type current: str
        :param vm_ipv4: IPv4 address to assign.
        :type vm_ipv4: str
        :param ipv4_prefix: IPv4 prefix length.
        :type ipv4_prefix: int
        :param ipv4_gateway: IPv4 gateway address.
        :type ipv4_gateway: IPv4Address
        :returns: The updated ``ipconfig0`` string.
        :rtype: str
        """
        parts = [p.strip() for p in current.split(",") if p.strip()]
        ipv6_parts = [p for p in parts if p.startswith("ip6=") or p.startswith("gw6=")]
        new_parts = [f"ip={vm_ipv4}/{ipv4_prefix}", f"gw={ipv4_gateway}", *ipv6_parts]
        return ",".join(new_parts)

    def remove_vm_ipv4(self, *, node: str, vm_id: int, vm_ipv4: str) -> None:
        """Remove the IPv4 address from the VM's ``ipconfig0`` cloud-init setting.

        Reads the current ``ipconfig0``, strips any ``ip=`` and ``gw=`` segments
        while preserving IPv6 segments, posts the updated configuration, then
        removes the address from the ``hosting`` IP set.

        :param node: Proxmox node name hosting the VM.
        :type node: str
        :param vm_id: VMID of the target virtual machine.
        :type vm_id: int
        :param vm_ipv4: IPv4 address to remove.
        :type vm_ipv4: str
        """
        config = self._client.nodes(node).qemu(vm_id).config.get()
        current_ipconfig0 = config.get("ipconfig0", "") if isinstance(config, dict) else ""
        parts = [p.strip() for p in current_ipconfig0.split(",") if p.strip()]
        remaining = [p for p in parts if not p.startswith("ip=") and not p.startswith("gw=")]
        self._client.nodes(node).qemu(vm_id).config.post(ipconfig0=",".join(remaining))

        firewall = self._client.nodes(node).qemu(vm_id).firewall
        self._remove_ipv4_from_ipset(firewall=firewall, vm_ipv4=vm_ipv4)

    def _add_ipv4_to_ipset(self, *, firewall: Any, vm_ipv4: str) -> None:
        """Add the VM's IPv4 ``/32`` CIDR to the ``hosting`` IP set.

        If the IP set does not exist yet (e.g. firewall was not set up), the
        entry is silently skipped. If the entry already exists it is also ignored.

        :param firewall: Proxmox firewall resource object for the VM.
        :param vm_ipv4: IPv4 address to add to the IP set.
        :type vm_ipv4: str
        """
        ipset_name = "hosting"
        vm_cidr = f"{vm_ipv4}/32"
        with contextlib.suppress(ResourceException):
            firewall.ipset(ipset_name).post(cidr=vm_cidr)

    def _remove_ipv4_from_ipset(self, *, firewall: Any, vm_ipv4: str) -> None:
        """Remove the VM's IPv4 ``/32`` CIDR from the ``hosting`` IP set.

        Silently ignores errors if the entry or IP set does not exist.

        :param firewall: Proxmox firewall resource object for the VM.
        :param vm_ipv4: IPv4 address to remove from the IP set.
        :type vm_ipv4: str
        """
        ipset_name = "hosting"
        vm_cidr = f"{vm_ipv4}/32"
        with contextlib.suppress(ResourceException):
            firewall.ipset(ipset_name)(vm_cidr).delete()

    def _encode_cloudinit_ssh_keys(self, raw_key: str) -> str:
        """Normalise and URL-encode an SSH public key for the Proxmox API.

        Line endings are normalised to ``\\n`` and leading/trailing whitespace
        is stripped before percent-encoding.

        :param raw_key: Raw SSH public key string.
        :returns: URL-encoded SSH public key string.
        :rtype: str
        :raises ProxmoxInvalidRequest: If the key is empty after normalisation.
        """
        normalized = raw_key.replace("\r\n", "\n").strip()
        if not normalized:
            raise ProxmoxInvalidRequest("SSH public key is empty")
        return quote(normalized, safe="")


__all__ = ["CloudInitService"]
