"""High-level Proxmox gateway providing all VM lifecycle operations."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from proxmoxer import ProxmoxAPI

from app.core.config import Settings, get_settings
from app.services.proxmox.allocation import allocate_vm_id
from app.services.proxmox.cloudinit_ops import CloudInitService
from app.services.proxmox.errors import ProxmoxError, ProxmoxInvalidDiskSize, ProxmoxInvalidResponse, raise_mapped_proxmox_error
from app.services.proxmox.models import CloudInitPatchSpec
from app.services.proxmox.tasks import TaskService, clamp_task_limit, ensure_upid, normalize_vm_tasks
from app.services.proxmox.utils import (
    clone_node_for_template,
    disk_size_gb,
    least_loaded_node,
    node_for_vm,
    resolve_vm_mac,
    root_disk_key,
    task_timeout_seconds,
)


class ProxmoxGateway:
    """Facade over the Proxmox API providing VM lifecycle and administration operations.

    All public methods translate Proxmox exceptions into the appropriate
    :class:`~app.services.proxmox.errors.ProxmoxError` subclass via
    :meth:`_guard`.
    """

    def __init__(self, settings: Settings):
        """Initialise the gateway and connect to the Proxmox API.

        :param settings: Application settings used to configure the connection.
        :raises ProxmoxError: If the base URL, user, or password are not configured.
        """
        self._settings = settings
        self._client = ProxmoxAPI(
            host=self._host,
            user=self._user,
            password=self._password,
            verify_ssl=settings.proxmox_verify_tls,
            timeout=settings.proxmox_timeout_seconds,
            port=self._port,
            service=settings.proxmox_service,
        )
        self._tasks = TaskService(client=self._client)
        self._cloudinit = CloudInitService(client=self._client, task_service=self._tasks)

    @property
    def _host(self) -> str:
        """Extract the hostname from the configured Proxmox base URL.

        :returns: Hostname string.
        :rtype: str
        :raises ProxmoxError: If the base URL is missing or has an invalid scheme.
        """
        from urllib.parse import urlparse

        base_url = self._settings.proxmox_base_url
        if not base_url:
            raise ProxmoxError("Proxmox base URL is not configured")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ProxmoxError("Invalid Proxmox base URL")
        return parsed.hostname

    @property
    def _port(self) -> int:
        """Extract the port from the configured Proxmox base URL, defaulting to 8006.

        :returns: Port number.
        :rtype: int
        :raises ProxmoxError: If the base URL is missing.
        """
        from urllib.parse import urlparse

        base_url = self._settings.proxmox_base_url
        if not base_url:
            raise ProxmoxError("Proxmox base URL is not configured")
        parsed = urlparse(base_url)
        return parsed.port or 8006

    @property
    def _user(self) -> str:
        """Return the Proxmox username, appending ``@pam`` if no realm is given.

        :returns: Fully-qualified Proxmox username (e.g. ``root@pam``).
        :rtype: str
        :raises ProxmoxError: If no user is configured.
        """
        raw = (self._settings.proxmox_user or "root").strip()
        if not raw:
            raise ProxmoxError("Proxmox user is not configured")
        if "@" not in raw:
            raw = f"{raw}@pam"
        return raw

    @property
    def _password(self) -> str:
        """Return the Proxmox API password from settings.

        :returns: Password string.
        :rtype: str
        :raises ProxmoxError: If no password is configured.
        """
        password = self._settings.proxmox_password
        if not password:
            raise ProxmoxError("Proxmox password is not configured")
        return password

    def next_vm_id(self) -> int:
        """Allocate and return the next available VM ID.

        :returns: An unused VMID.
        :rtype: int
        :raises ProxmoxError: On API communication or configuration failures.
        """
        return self._guard(lambda: allocate_vm_id(client=self._client))

    def create_vm(
        self,
        *,
        vm_id: int,
        template_vmid: int,
        vm_ipv6: str,
        name: str,
        cpu_cores: int,
        ram_mb: int,
        username: str,
        password: str | None,
        ssh_public_key: str,
    ) -> str | None:
        """Clone a template and configure a new VM with the supplied parameters.

        :param vm_id: VMID to assign to the new VM.
        :param template_vmid: VMID of the Proxmox template to clone from.
        :param vm_ipv6: IPv6 address to assign via cloud-init.
        :param name: Hostname/display name for the new VM.
        :param cpu_cores: Number of CPU cores.
        :param ram_mb: RAM in megabytes.
        :param username: Cloud-init username.
        :param password: Cloud-init password, or ``None`` to omit.
        :param ssh_public_key: SSH public key to inject via cloud-init.
        :returns: The VM's MAC address, or ``None`` if it could not be resolved.
        :rtype: str | None
        :raises ProxmoxError: On API, configuration, or task failures.
        """
        return self._guard(
            lambda: self._create_vm(
                vm_id=vm_id,
                template_vmid=template_vmid,
                vm_ipv6=vm_ipv6,
                name=name,
                cpu_cores=cpu_cores,
                ram_mb=ram_mb,
                username=username,
                password=password,
                ssh_public_key=ssh_public_key,
            )
        )

    def _create_vm(
        self,
        *,
        vm_id: int,
        template_vmid: int,
        vm_ipv6: str,
        name: str,
        cpu_cores: int,
        ram_mb: int,
        username: str,
        password: str | None,
        ssh_public_key: str,
    ) -> str | None:
        """Internal implementation of VM creation.

        Clones the template, waits for completion, applies cloud-init settings,
        and returns the resulting VM's MAC address.

        :param vm_id: VMID for the new VM.
        :param template_vmid: Source template VMID.
        :param vm_ipv6: IPv6 address for cloud-init.
        :param name: VM display name.
        :param cpu_cores: CPU core count.
        :param ram_mb: RAM in megabytes.
        :param username: Cloud-init username.
        :param password: Cloud-init password or ``None``.
        :param ssh_public_key: SSH public key for cloud-init.
        :returns: MAC address string or ``None``.
        :rtype: str | None
        """
        clone_node = clone_node_for_template(client=self._client, template_vmid=template_vmid)
        target_node = least_loaded_node(client=self._client) or clone_node
        timeout = task_timeout_seconds()

        clone_params: dict[str, Any] = {"newid": vm_id, "name": name, "full": 1}
        if target_node != clone_node:
            clone_params["target"] = target_node

        upid = ensure_upid(self._client.nodes(clone_node).qemu(template_vmid).clone.post(**clone_params))
        self._tasks.wait_for_task(node=clone_node, upid=upid, timeout_seconds=timeout)

        from app.services.proxmox.allocation import ipv6_network_settings

        _, gw6, prefix = ipv6_network_settings()
        payload = self._cloudinit.build_initial_payload(
            cpu_cores=cpu_cores,
            ram_mb=ram_mb,
            ci_username=username,
            ci_password=password,
            ci_ssh_public_key=ssh_public_key,
            vm_ipv6=vm_ipv6,
            ipv6_prefix=prefix,
            ipv6_gateway=gw6,
        )
        self._client.nodes(target_node).qemu(vm_id).config.post(**payload)

        vm_config = self._get_config(node=target_node, vm_id=vm_id)
        return resolve_vm_mac(vm_config)

    def assign_vm_ipv4(self, *, vm_id: int, vm_ipv4: str) -> None:
        """Inject an IPv4 address into the VM's cloud-init network configuration.

        Reads the configured ``VM_IPV4_SUBNET`` and ``VM_IPV4_GATEWAY_HOST`` to
        derive the prefix length and gateway, then updates ``ipconfig0`` on Proxmox.

        :param vm_id: VMID of the target virtual machine.
        :type vm_id: int
        :param vm_ipv4: IPv4 address string to assign.
        :type vm_ipv4: str
        :raises ProxmoxError: On API or configuration failures.
        :raises ProxmoxConfigError: If ``VM_IPV4_SUBNET`` is not configured.
        """
        self._guard(lambda: self._do_assign_ipv4(vm_id=vm_id, vm_ipv4=vm_ipv4))

    def _do_assign_ipv4(self, *, vm_id: int, vm_ipv4: str) -> None:
        """Internal implementation of IPv4 assignment.

        :param vm_id: VMID of the target virtual machine.
        :type vm_id: int
        :param vm_ipv4: IPv4 address string to assign.
        :type vm_ipv4: str
        """
        from app.services.proxmox.allocation import ipv4_network_settings

        _, gw4, prefix = ipv4_network_settings()
        node = node_for_vm(client=self._client, vm_id=vm_id)
        self._cloudinit.assign_vm_ipv4(
            node=node,
            vm_id=vm_id,
            vm_ipv4=vm_ipv4,
            ipv4_prefix=prefix,
            ipv4_gateway=gw4,
        )

    def setup_vm_firewall(self, *, vm_id: int, vm_ipv6: str) -> None:
        """Enable the Proxmox firewall and IPv6 IP-set filter on a VM.

        :param vm_id: VMID of the target VM.
        :param vm_ipv6: IPv6 address to allow through the filter.
        :raises ProxmoxError: On API or configuration failures.
        """
        self._guard(lambda: self._do_setup_firewall(vm_id=vm_id, vm_ipv6=vm_ipv6))

    def _do_setup_firewall(self, *, vm_id: int, vm_ipv6: str) -> None:
        """Internal implementation of firewall setup.

        :param vm_id: VMID of the target VM.
        :param vm_ipv6: IPv6 address to allow.
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        vm_config = self._get_config(node=node, vm_id=vm_id)
        self._cloudinit.enable_vm_ipv6_ipfilter(node=node, vm_id=vm_id, vm_ipv6=vm_ipv6, vm_config=vm_config)

    def resize_vm_disk(self, *, vm_id: int, disk_gb: int) -> None:
        """Resize the root disk of a VM to at least *disk_gb* gigabytes.

        :param vm_id: VMID of the target VM.
        :param disk_gb: Desired disk size in gigabytes.
        :raises ProxmoxInvalidDiskSize: If *disk_gb* is below the current disk size.
        :raises ProxmoxError: On API or configuration failures.
        """
        self._guard(lambda: self._do_resize_disk(vm_id=vm_id, disk_gb=disk_gb))

    def _do_resize_disk(self, *, vm_id: int, disk_gb: int) -> None:
        """Internal implementation of disk resizing.

        :param vm_id: VMID of the target VM.
        :param disk_gb: Target disk size in gigabytes.
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        timeout = task_timeout_seconds()
        vm_config = self._get_config(node=node, vm_id=vm_id)
        self._resize_disk_if_needed(
            node=node,
            vm_id=vm_id,
            vm_config=vm_config,
            disk_gb=disk_gb,
            timeout_seconds=timeout,
        )

    def _get_config(self, *, node: str, vm_id: int) -> dict[str, Any]:
        """Fetch and validate a VM configuration dict from Proxmox.

        :param node: Proxmox node name.
        :param vm_id: VMID to fetch config for.
        :returns: VM configuration dictionary.
        :rtype: dict[str, Any]
        :raises ProxmoxInvalidResponse: If Proxmox does not return a dict.
        """
        config = self._client.nodes(node).qemu(vm_id).config.get()
        if isinstance(config, dict):
            return config
        raise ProxmoxInvalidResponse("Invalid VM config response from Proxmox")

    def _resize_disk_if_needed(
        self,
        *,
        node: str,
        vm_id: int,
        vm_config: dict[str, Any],
        disk_gb: int,
        timeout_seconds: int,
    ) -> None:
        """Resize the root disk of a VM if the requested size is larger than current.

        Does nothing if no root disk key is found or if the disk is already large
        enough. Raises if the requested size is smaller than the existing disk.

        :param node: Proxmox node name.
        :param vm_id: VMID of the target VM.
        :param vm_config: Current VM configuration dictionary.
        :param disk_gb: Desired disk size in gigabytes.
        :param timeout_seconds: Task wait timeout in seconds.
        :raises ProxmoxInvalidDiskSize: If *disk_gb* is below the current disk size.
        """
        disk_key = root_disk_key(vm_config)
        if not disk_key:
            return

        current = vm_config.get(disk_key)
        current_size = disk_size_gb(current) if isinstance(current, str) else None

        if current_size is not None and disk_gb < current_size:
            raise ProxmoxInvalidDiskSize(
                f"Requested disk ({disk_gb}G) is below template disk size ({current_size}G)",
            )
        if current_size is not None and disk_gb <= current_size:
            return

        result = self._client.nodes(node).qemu(vm_id).resize.put(disk=disk_key, size=f"{disk_gb}G")
        self._tasks.wait_if_async(node=node, result=result, timeout_seconds=timeout_seconds)

    def start_vm(self, *, vm_id: int) -> None:
        """Start a VM.

        :param vm_id: VMID of the VM to start.
        :raises ProxmoxError: On API failures.
        """
        self._guard(lambda: self._status_action(vm_id=vm_id, action="start"))

    def stop_vm(self, *, vm_id: int) -> None:
        """Stop a VM.

        :param vm_id: VMID of the VM to stop.
        :raises ProxmoxError: On API failures.
        """
        self._guard(lambda: self._status_action(vm_id=vm_id, action="stop"))

    def restart_vm(self, *, vm_id: int) -> None:
        """Reboot a VM.

        :param vm_id: VMID of the VM to reboot.
        :raises ProxmoxError: On API failures.
        """
        self._guard(lambda: self._status_action(vm_id=vm_id, action="reboot"))

    def _status_action(self, *, vm_id: int, action: str) -> None:
        """Execute a power-state action on a VM and wait for the resulting task.

        :param vm_id: VMID of the target VM.
        :param action: Proxmox status action name (e.g. ``"start"``, ``"stop"``,
            ``"reboot"``).
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        timeout = task_timeout_seconds()
        status = self._client.nodes(node).qemu(vm_id).status
        result = getattr(status, action).post()
        self._tasks.wait_if_async(node=node, result=result, timeout_seconds=timeout)

    def get_vm_status(self, *, vm_id: int) -> dict[str, Any]:
        """Return the current status payload for a VM.

        :param vm_id: VMID of the target VM.
        :returns: Status dictionary from Proxmox.
        :rtype: dict[str, Any]
        :raises ProxmoxError: On API failures.
        """
        return self._guard(lambda: self._status(vm_id=vm_id))

    def get_vm_mac(self, *, vm_id: int) -> str | None:
        """Return the MAC address of a VM's primary network interface.

        :param vm_id: VMID of the target VM.
        :returns: Lowercase MAC address string, or ``None`` if not found.
        :rtype: str | None
        :raises ProxmoxError: On API failures.
        """
        return self._guard(lambda: self._mac(vm_id=vm_id))

    def _status(self, *, vm_id: int) -> dict[str, Any]:
        """Internal implementation of VM status retrieval.

        :param vm_id: VMID of the target VM.
        :returns: Status dictionary, or a wrapper ``{"raw": ...}`` if the
            response is not a dict.
        :rtype: dict[str, Any]
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        payload = self._client.nodes(node).qemu(vm_id).status.current.get()
        if isinstance(payload, dict):
            return payload
        return {"raw": payload}

    def _mac(self, *, vm_id: int) -> str | None:
        """Internal implementation of MAC address lookup.

        :param vm_id: VMID of the target VM.
        :returns: Lowercase MAC address string or ``None``.
        :rtype: str | None
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        vm_config = self._get_config(node=node, vm_id=vm_id)
        return resolve_vm_mac(vm_config)

    def vm_rrddata(self, *, vm_id: int, timeframe: str = "hour", cf: str = "AVERAGE") -> list[dict[str, Any]]:
        """Return historical RRD metrics for a VM.

        :param vm_id: VMID of the target VM.
        :param timeframe: Time range — ``"hour"``, ``"day"``, ``"week"``,
            ``"month"``, or ``"year"``.
        :param cf: Consolidation function — ``"AVERAGE"`` or ``"MAX"``.
        :returns: List of data-point dicts, each containing ``time`` and
            metric fields (``cpu``, ``mem``, ``netin``, etc.).
        :rtype: list[dict[str, Any]]
        :raises ProxmoxError: On API failures.
        """
        return self._guard(lambda: self._vm_rrddata(vm_id=vm_id, timeframe=timeframe, cf=cf))

    def _vm_rrddata(self, *, vm_id: int, timeframe: str, cf: str) -> list[dict[str, Any]]:
        """Internal implementation of RRD data retrieval.

        :param vm_id: VMID of the target VM.
        :param timeframe: Time range string.
        :param cf: Consolidation function string.
        :returns: List of data-point dicts.
        :rtype: list[dict[str, Any]]
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        raw = self._client.nodes(node).qemu(vm_id).rrddata.get(timeframe=timeframe, cf=cf)
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def list_vm_tasks(self, *, vm_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent task records for a VM, sorted newest first.

        :param vm_id: VMID to fetch tasks for.
        :param limit: Maximum number of tasks to return (clamped to 1–100).
        :returns: List of normalised task dictionaries.
        :rtype: list[dict[str, Any]]
        :raises ProxmoxError: On API failures.
        """
        return self._guard(lambda: self._tasks_for_vm(vm_id=vm_id, limit=limit))

    def _tasks_for_vm(self, *, vm_id: int, limit: int) -> list[dict[str, Any]]:
        """Internal implementation of task listing for a VM.

        :param vm_id: VMID to fetch tasks for.
        :param limit: Maximum number of tasks to return.
        :returns: List of normalised task dictionaries.
        :rtype: list[dict[str, Any]]
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        safe_limit = clamp_task_limit(limit=limit)
        raw = self._client.nodes(node).tasks.get(vmid=vm_id, limit=safe_limit)
        return normalize_vm_tasks(raw_tasks=raw, vm_id=vm_id, limit=safe_limit)

    def update_vm_cloudinit(
        self,
        *,
        vm_id: int,
        username: str,
        password: str | None,
        ssh_public_key: str | None,
    ) -> None:
        """Update cloud-init credentials on an existing VM.

        :param vm_id: VMID of the target VM.
        :param username: New cloud-init username.
        :param password: New password, or ``None`` to leave unchanged.
        :param ssh_public_key: New SSH public key, or ``None`` to leave unchanged.
        :raises ProxmoxError: On API or task failures.
        """
        self._guard(
            lambda: self._cloudinit.update_vm_cloudinit(
                node=node_for_vm(client=self._client, vm_id=vm_id),
                vm_id=vm_id,
                spec=CloudInitPatchSpec(
                    ci_username=username,
                    ci_password=password,
                    ci_ssh_public_key=ssh_public_key,
                ),
                timeout_seconds=task_timeout_seconds(),
            )
        )

    def update_vm_resources(
        self,
        *,
        vm_id: int,
        cpu_cores: int | None,
        ram_mb: int | None,
        disk_gb: int | None,
    ) -> None:
        """Update CPU, RAM, and/or disk resources for an existing VM.

        Only parameters that are not ``None`` are applied. CPU and RAM changes
        are submitted in a single config POST; disk resizing is performed
        separately.

        :param vm_id: VMID of the target VM.
        :param cpu_cores: New CPU core count, or ``None`` to leave unchanged.
        :param ram_mb: New RAM in megabytes, or ``None`` to leave unchanged.
        :param disk_gb: New disk size in gigabytes, or ``None`` to leave unchanged.
        :raises ProxmoxInvalidDiskSize: If *disk_gb* is below the current disk size.
        :raises ProxmoxError: On API or task failures.
        """
        self._guard(
            lambda: self._update_resources(
                vm_id=vm_id,
                cpu_cores=cpu_cores,
                ram_mb=ram_mb,
                disk_gb=disk_gb,
            )
        )

    def _update_resources(
        self,
        *,
        vm_id: int,
        cpu_cores: int | None,
        ram_mb: int | None,
        disk_gb: int | None,
    ) -> None:
        """Internal implementation of VM resource updating.

        :param vm_id: VMID of the target VM.
        :param cpu_cores: CPU core count or ``None``.
        :param ram_mb: RAM in megabytes or ``None``.
        :param disk_gb: Disk size in gigabytes or ``None``.
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        timeout = task_timeout_seconds()

        if cpu_cores is not None or ram_mb is not None:
            payload: dict[str, Any] = {}
            if cpu_cores is not None:
                payload["cores"] = cpu_cores
            if ram_mb is not None:
                payload["memory"] = ram_mb
            result = self._client.nodes(node).qemu(vm_id).config.post(**payload)
            self._tasks.wait_if_async(node=node, result=result, timeout_seconds=timeout)

        if disk_gb is not None:
            vm_config = self._get_config(node=node, vm_id=vm_id)
            self._resize_disk_if_needed(
                node=node,
                vm_id=vm_id,
                vm_config=vm_config,
                disk_gb=disk_gb,
                timeout_seconds=timeout,
            )

    def get_pve_auth_ticket(self) -> str:
        """Return the current PVEAuthCookie value from the proxmoxer session."""
        return self._client._backend.auth.pve_auth_ticket

    def termproxy(self, *, vm_id: int) -> dict[str, Any]:
        """Create a terminal proxy session for a VM.

        :param vm_id: VMID of the target VM.
        :returns: Dictionary containing ``node``, ``port``, ``ticket``, ``upid``,
            and ``username`` for connecting to the terminal proxy.
        :rtype: dict[str, Any]
        :raises ProxmoxInvalidResponse: If Proxmox returns an unexpected payload.
        :raises ProxmoxError: On API failures.
        """
        return self._guard(lambda: self._termproxy(vm_id=vm_id))

    def _termproxy(self, *, vm_id: int) -> dict[str, Any]:
        """Internal implementation of terminal proxy session creation.

        :param vm_id: VMID of the target VM.
        :returns: Terminal proxy connection details.
        :rtype: dict[str, Any]
        :raises ProxmoxInvalidResponse: If the Proxmox response is not a dict.
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        result = self._client.nodes(node).qemu(vm_id).termproxy.post()
        if not isinstance(result, dict):
            raise ProxmoxInvalidResponse("Invalid termproxy response from Proxmox")
        return {
            "node": node,
            "port": int(result["port"]),
            "ticket": str(result["ticket"]),
            "upid": result.get("upid"),
            "username": self._user,
        }

    def delete_vm(self, *, vm_id: int) -> None:
        """Delete a VM and wait for the task to complete.

        :param vm_id: VMID of the VM to delete.
        :raises ProxmoxError: On API or task failures.
        """
        self._guard(lambda: self._delete(vm_id=vm_id))

    def _delete(self, *, vm_id: int) -> None:
        """Internal implementation of VM deletion.

        :param vm_id: VMID of the VM to delete.
        """
        node = node_for_vm(client=self._client, vm_id=vm_id)
        result = self._client.nodes(node).qemu(vm_id).delete()
        self._tasks.wait_if_async(node=node, result=result, timeout_seconds=task_timeout_seconds())

    def cluster_resources(self, *, type: str | None = None) -> list[dict[str, Any]]:
        """Return the raw Proxmox cluster resources list.

        Proxies ``GET /api2/json/cluster/resources`` optionally filtered by
        resource type (``vm``, ``storage``, ``node``, ``sdn``).

        :param type: Optional resource type filter passed to the Proxmox API.
        :type type: str | None
        :returns: List of resource entries as returned by Proxmox.
        :rtype: list[dict[str, Any]]
        :raises ProxmoxError: On API or communication failures.
        """
        return self._guard(lambda: self._cluster_resources(type=type))

    def _cluster_resources(self, *, type: str | None) -> list[dict[str, Any]]:
        """Internal implementation of cluster resource listing.

        :param type: Optional resource type filter.
        :type type: str | None
        :returns: List of resource entries.
        :rtype: list[dict[str, Any]]
        """
        kwargs = {"type": type} if type else {}
        raw = self._client.cluster.resources.get(**kwargs)
        return raw if isinstance(raw, list) else []

    def version(self) -> dict[str, Any]:
        """Return Proxmox version information.

        :returns: Version dictionary from the Proxmox API.
        :rtype: dict[str, Any]
        :raises ProxmoxError: On API failures.
        """
        return self._guard(self._version)

    def _version(self) -> dict[str, Any]:
        """Internal implementation of version retrieval.

        :returns: Version dict, or a wrapper ``{"raw": ...}`` if not a dict.
        :rtype: dict[str, Any]
        """
        payload = self._client.version.get()
        if isinstance(payload, dict):
            return payload
        return {"raw": payload}

    def nodes(self) -> list[dict[str, Any]]:
        """Return a list of cluster nodes with their status information.

        :returns: List of dicts containing ``node``, ``status``, and ``level``.
        :rtype: list[dict[str, Any]]
        :raises ProxmoxError: On API failures.
        """
        return self._guard(self._nodes)

    def _nodes(self) -> list[dict[str, Any]]:
        """Internal implementation of node listing.

        :returns: Filtered and normalised list of node dicts.
        :rtype: list[dict[str, Any]]
        """
        raw = self._client.nodes.get()
        if not isinstance(raw, list):
            return []
        result: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            node = item.get("node")
            if not isinstance(node, str) or not node.strip():
                continue
            result.append({"node": node.strip(), "status": item.get("status"), "level": item.get("level")})
        return result

    def _guard(self, fn):
        """Execute *fn* and map any non-:class:`ProxmoxError` exceptions.

        Re-raises :class:`ProxmoxError` instances as-is; translates all other
        exceptions via :func:`~app.services.proxmox.errors.raise_mapped_proxmox_error`.

        :param fn: Zero-argument callable to execute.
        :returns: Whatever *fn* returns.
        :raises ProxmoxError: Always on failure; specific subclass depends on the
            underlying exception.
        """
        try:
            return fn()
        except ProxmoxError:
            raise
        except Exception as exc:
            raise_mapped_proxmox_error(exc)


@lru_cache(maxsize=1)
def get_proxmox_gateway() -> ProxmoxGateway:
    """Return a shared, cached :class:`ProxmoxGateway` instance.

    The gateway is constructed once from the current application settings and
    reused for the lifetime of the process.

    :returns: Singleton :class:`ProxmoxGateway` instance.
    :rtype: ProxmoxGateway
    """
    return ProxmoxGateway(get_settings())
