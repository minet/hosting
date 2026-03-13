"""
VM lifecycle action service (start / stop / restart / status / tasks).

Wraps the :class:`~app.services.proxmox.gateway.ProxmoxGateway` calls for
individual VM power-state operations and translates Proxmox errors into HTTP
exceptions via :func:`~app.services.vm.errors.raise_proxmox_as_http`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

_T = TypeVar("_T")

from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http


class VmActionService:
    """Service for executing power-state actions on a virtual machine."""

    def __init__(self, gateway: ProxmoxGateway):
        """
        Initialise the action service.

        :param gateway: Proxmox gateway used to send commands to the hypervisor.
        """
        self.gateway = gateway

    def start(self, vm_id: int) -> dict[str, Any]:
        """
        Start a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result dictionary with keys ``vm_id``, ``action``
            and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox communication or permission errors.
        """
        self._run(lambda: self.gateway.start_vm(vm_id=vm_id), unavailable="Unable to start VM on Proxmox")
        return {"vm_id": vm_id, "action": "start", "status": "ok"}

    def stop(self, vm_id: int) -> dict[str, Any]:
        """
        Stop (power off) a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result dictionary with keys ``vm_id``, ``action``
            and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox communication or permission errors.
        """
        self._run(lambda: self.gateway.stop_vm(vm_id=vm_id), unavailable="Unable to stop VM on Proxmox")
        return {"vm_id": vm_id, "action": "stop", "status": "ok"}

    def restart(self, vm_id: int) -> dict[str, Any]:
        """
        Restart a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result dictionary with keys ``vm_id``, ``action``
            and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox communication or permission errors.
        """
        self._run(lambda: self.gateway.restart_vm(vm_id=vm_id), unavailable="Unable to restart VM on Proxmox")
        return {"vm_id": vm_id, "action": "restart", "status": "ok"}

    def status(self, vm_id: int) -> dict[str, Any]:
        """
        Retrieve the current runtime status of a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Dictionary containing ``vm_id`` plus all runtime fields
            returned by the gateway.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox communication or permission errors.
        """
        runtime = self._run(
            lambda: self.gateway.get_vm_status(vm_id=vm_id), unavailable="Unable to fetch VM status from Proxmox"
        )
        return {"vm_id": vm_id, **runtime}

    def tasks(self, vm_id: int, limit: int = 20) -> dict[str, Any]:
        """
        List recent Proxmox tasks for a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :param limit: Maximum number of tasks to return. Defaults to 20.
        :returns: Dictionary with ``vm_id``, ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox communication or permission errors.
        """
        items = self._run(
            lambda: self.gateway.list_vm_tasks(vm_id=vm_id, limit=limit),
            unavailable="Unable to fetch VM tasks from Proxmox",
        )
        return {"vm_id": vm_id, "items": items, "count": len(items)}

    def _run(self, fn: Callable[[], _T], *, unavailable: str) -> _T:
        """
        Execute ``fn`` and translate any :class:`~app.services.proxmox.errors.ProxmoxError`
        into an :class:`~fastapi.HTTPException`.

        :param fn: Zero-argument callable to invoke.
        :param unavailable: Detail message used for generic 503 responses.
        :returns: The return value of ``fn``.
        :raises HTTPException: When ``fn`` raises a
            :class:`~app.services.proxmox.errors.ProxmoxError`.
        """
        try:
            return fn()
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable=unavailable)
