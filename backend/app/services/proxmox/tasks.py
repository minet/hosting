"""Proxmox task polling, normalisation, and helper utilities."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from proxmoxer import ProxmoxAPI

from app.services.proxmox.errors import ProxmoxInvalidResponse, ProxmoxTaskFailed

logger = logging.getLogger(__name__)


def ensure_upid(raw: Any) -> str:
    """Validate and return a Proxmox UPID string.

    :param raw: Value returned by the Proxmox API after submitting a task.
    :returns: The stripped UPID string.
    :rtype: str
    :raises ProxmoxInvalidResponse: If *raw* is not a non-empty string.
    """
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise ProxmoxInvalidResponse("Unexpected Proxmox task response")


class TaskService:
    """Handle asynchronous Proxmox task tracking."""

    def __init__(self, *, client: ProxmoxAPI):
        """Initialise the task service with a Proxmox API client.

        :param client: Proxmox API client instance.
        """
        self._client = client

    def wait_for_task(self, *, node: str, upid: str, timeout_seconds: int) -> dict[str, Any]:
        """Synchronously block until the given Proxmox task completes or times out.

        Internally runs :meth:`wait_for_task_async` via :func:`asyncio.run`.

        :param node: Proxmox node name that owns the task.
        :param upid: Unique task identifier (UPID).
        :param timeout_seconds: Maximum seconds to wait before raising.
        :returns: Final task status payload from Proxmox.
        :rtype: dict[str, Any]
        :raises ProxmoxTaskFailed: If the task fails or the timeout is reached.
        :raises ProxmoxInvalidResponse: If Proxmox returns an unexpected payload.
        """
        return asyncio.run(self.wait_for_task_async(node=node, upid=upid, timeout_seconds=timeout_seconds))

    async def wait_for_task_async(self, *, node: str, upid: str, timeout_seconds: int) -> dict[str, Any]:
        """Asynchronously poll Proxmox until the task finishes or the deadline is reached.

        Polls every second and logs progress. Raises on non-``OK`` exit status
        or when the monotonic deadline expires.

        :param node: Proxmox node name that owns the task.
        :param upid: Unique task identifier (UPID).
        :param timeout_seconds: Maximum seconds to wait before raising.
        :returns: Final task status payload from Proxmox.
        :rtype: dict[str, Any]
        :raises ProxmoxTaskFailed: If the task fails or the timeout is reached.
        :raises ProxmoxInvalidResponse: If Proxmox returns an unexpected status payload.
        """
        logger.info("proxmox_task_wait_start node=%s upid=%s timeout_seconds=%s", node, upid, timeout_seconds)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = await asyncio.to_thread(self._client.nodes(node).tasks(upid).status.get)
            if not isinstance(status, dict):
                raise ProxmoxInvalidResponse("Invalid task status payload from Proxmox")
            if status.get("status") != "stopped":
                await asyncio.sleep(1)
                continue
            exit_status = status.get("exitstatus")
            if exit_status != "OK":
                logger.warning(
                    "proxmox_task_failed node=%s upid=%s status=%s exitstatus=%s",
                    node,
                    upid,
                    status.get("status"),
                    exit_status,
                )
                raise ProxmoxTaskFailed(f"Proxmox task failed ({exit_status})")
            logger.info("proxmox_task_wait_done node=%s upid=%s", node, upid)
            return status
        logger.warning("proxmox_task_timeout node=%s upid=%s timeout_seconds=%s", node, upid, timeout_seconds)
        raise ProxmoxTaskFailed("Proxmox task timeout")

    def wait_if_async(self, *, node: str, result: Any, timeout_seconds: int) -> None:
        """Wait for a task only if *result* looks like a UPID string.

        If *result* is not a non-empty string the call is a no-op, allowing
        callers to pass raw Proxmox API responses without pre-checking them.

        :param node: Proxmox node name that owns the task.
        :param result: Raw API response that may contain a UPID string.
        :param timeout_seconds: Maximum seconds to wait for the task.
        """
        if not isinstance(result, str) or not result.strip():
            return
        self.wait_for_task(node=node, upid=result.strip(), timeout_seconds=timeout_seconds)

    async def wait_if_async_async(self, *, node: str, result: Any, timeout_seconds: int) -> None:
        """Asynchronously wait for a task only if *result* looks like a UPID string.

        Async counterpart of :meth:`wait_if_async`.

        :param node: Proxmox node name that owns the task.
        :param result: Raw API response that may contain a UPID string.
        :param timeout_seconds: Maximum seconds to wait for the task.
        """
        if not isinstance(result, str) or not result.strip():
            return
        await self.wait_for_task_async(node=node, upid=result.strip(), timeout_seconds=timeout_seconds)


def clamp_task_limit(*, limit: int) -> int:
    """Clamp a task list limit to the range ``[1, 100]``.

    :param limit: Requested task list limit.
    :returns: The clamped limit value.
    :rtype: int
    """
    return max(1, min(int(limit), 100))


def normalize_vm_tasks(*, raw_tasks: Any, vm_id: int, limit: int) -> list[dict[str, Any]]:
    """Filter, normalise, and sort raw Proxmox task records for a specific VM.

    Returns up to *limit* task records belonging to *vm_id*, sorted by start
    time descending (most recent first).

    :param raw_tasks: Raw task list returned by the Proxmox API.
    :param vm_id: VMID to filter tasks for.
    :param limit: Maximum number of tasks to return.
    :returns: List of normalised task dictionaries.
    :rtype: list[dict[str, Any]]
    """
    if not isinstance(raw_tasks, list):
        return []

    filtered: list[dict[str, Any]] = []
    for item in raw_tasks:
        normalized = _normalize_task_item(item=item, vm_id=vm_id)
        if normalized is not None:
            filtered.append(normalized)

    filtered.sort(key=lambda row: int(row.get("starttime") or 0), reverse=True)
    return filtered[:limit]


def _normalize_task_item(*, item: Any, vm_id: int) -> dict[str, Any] | None:
    """Normalise a single raw task record if it belongs to *vm_id*.

    :param item: Raw task record from the Proxmox API.
    :param vm_id: Expected VMID the task must belong to.
    :returns: Normalised task dict, or ``None`` if the record is invalid or
        does not belong to *vm_id*.
    :rtype: dict[str, Any] | None
    """
    if not isinstance(item, dict):
        return None
    if not _task_belongs_to_vm(item=item, vm_id=vm_id):
        return None

    return {
        "upid": item.get("upid"),
        "type": item.get("type"),
        "status": item.get("status"),
        "exitstatus": item.get("exitstatus"),
        "id": item.get("id"),
        "node": item.get("node"),
        "user": item.get("user"),
        "starttime": item.get("starttime"),
        "endtime": item.get("endtime"),
    }


def _task_belongs_to_vm(*, item: dict[str, Any], vm_id: int) -> bool:
    """Determine whether a task record is associated with a given VM ID.

    Checks, in order: the ``vmid`` field, the ``id`` field (``qemu/<vmid>``
    format), and the ``upid`` field (``:<vmid>:`` substring).

    :param item: Raw task record dictionary.
    :param vm_id: VMID to match against.
    :returns: ``True`` if the task belongs to *vm_id*, ``False`` otherwise.
    :rtype: bool
    """
    raw_item_vmid = item.get("vmid")
    if raw_item_vmid is not None:
        try:
            return int(raw_item_vmid) == vm_id
        except (TypeError, ValueError):
            return False

    task_id = item.get("id")
    if isinstance(task_id, str) and task_id.startswith("qemu/"):
        try:
            return int(task_id.split("/", maxsplit=1)[1]) == vm_id
        except (TypeError, ValueError):
            return False

    upid = item.get("upid")
    if isinstance(upid, str):
        return f":{vm_id}:" in upid
    return False


__all__ = ["ensure_upid", "TaskService", "clamp_task_limit", "normalize_vm_tasks"]
