"""
Centralized VM status cache.

A single background poller fetches the status of ALL VMs from Proxmox
via one ``GET /cluster/resources?type=vm`` call every N seconds and
stores the results in an in-process dict.  SSE streams and individual
status queries read from this cache instead of making per-VM calls.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway

logger = logging.getLogger(__name__)

_POLL_INTERVAL: float = 5.0  # seconds


@dataclass
class VMStatusEntry:
    """Cached status for a single VM."""

    status: str | None = None
    uptime: int | None = None
    node: str | None = None
    updated_at: float = 0.0


class VMStatusCache:
    """In-process cache of VM statuses, refreshed by a background poller."""

    def __init__(self) -> None:
        self._cache: dict[int, VMStatusEntry] = {}
        self._task: asyncio.Task[None] | None = None
        self._gateway: ProxmoxGateway | None = None
        self._last_poll: float = 0.0

    def start(self, gateway: ProxmoxGateway) -> None:
        """Start the background polling loop."""
        self._gateway = gateway
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("vm_status_cache started (interval=%.1fs)", _POLL_INTERVAL)

    async def stop(self) -> None:
        """Stop the background polling loop."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("vm_status_cache stopped")

    def get(self, vm_id: int) -> VMStatusEntry | None:
        """Return the cached status for a VM, or None if unknown."""
        return self._cache.get(vm_id)

    def get_many(self, vm_ids: list[int]) -> dict[int, VMStatusEntry]:
        """Return cached statuses for a list of VM IDs."""
        return {vm_id: entry for vm_id in vm_ids if (entry := self._cache.get(vm_id)) is not None}

    def get_all(self) -> dict[int, VMStatusEntry]:
        """Return the full cache snapshot."""
        return dict(self._cache)

    async def _poll_loop(self) -> None:
        """Background loop: fetch all VM statuses in one call, update cache."""
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except (ProxmoxError, OSError, ValueError, KeyError) as exc:
                logger.warning("vm_status_cache poll error: %s", exc)
            await asyncio.sleep(_POLL_INTERVAL)

    async def _poll_once(self) -> None:
        if self._gateway is None:
            return
        try:
            resources: list[dict[str, Any]] = await asyncio.to_thread(
                self._gateway.cluster_resources, type="vm"
            )
        except ProxmoxError:
            logger.warning("vm_status_cache: proxmox unavailable, keeping stale data")
            return

        now = time.monotonic()
        seen: set[int] = set()
        for item in resources:
            vmid = item.get("vmid")
            if vmid is None:
                continue
            try:
                vmid = int(vmid)
            except (TypeError, ValueError):
                continue
            # Skip templates
            if item.get("template"):
                continue
            seen.add(vmid)
            self._cache[vmid] = VMStatusEntry(
                status=item.get("status"),
                uptime=item.get("uptime"),
                node=item.get("node"),
                updated_at=now,
            )

        # Remove VMs that no longer exist in Proxmox
        stale = set(self._cache) - seen
        for vm_id in stale:
            del self._cache[vm_id]

        self._last_poll = now


# ── Module-level singleton ────────────────────────────────────────────

_instance: VMStatusCache | None = None


def get_status_cache() -> VMStatusCache:
    """Return the global VMStatusCache singleton."""
    global _instance
    if _instance is None:
        _instance = VMStatusCache()
    return _instance
