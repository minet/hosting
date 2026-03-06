"""Thread-pool executor for offloading blocking Proxmox API calls from the async event loop."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from typing import Callable, TypeVar

from app.core.config import get_settings

T = TypeVar("T")


@lru_cache(maxsize=1)
def get_proxmox_executor() -> ThreadPoolExecutor:
    """Return a shared :class:`~concurrent.futures.ThreadPoolExecutor` for Proxmox I/O.

    The executor is created once and cached for the lifetime of the process.
    Worker count is read from settings and clamped to at least 1.

    :returns: Shared thread-pool executor instance.
    :rtype: ThreadPoolExecutor
    """
    max_workers = max(int(get_settings().proxmox_executor_max_workers), 1)
    return ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="proxmox-io")


async def run_in_proxmox_executor(fn: Callable[..., T], /, *args, **kwargs) -> T:
    """Run a callable in the shared Proxmox thread-pool executor.

    Wraps *fn* in a :func:`~functools.partial` with the supplied arguments and
    submits it to the executor via the running event loop.

    :param fn: Synchronous callable to run off the event loop.
    :param args: Positional arguments forwarded to *fn*.
    :param kwargs: Keyword arguments forwarded to *fn*.
    :returns: The return value of *fn*.
    :rtype: T
    """
    loop = asyncio.get_running_loop()
    task = partial(fn, *args, **kwargs)
    return await loop.run_in_executor(get_proxmox_executor(), task)


def close_proxmox_executor() -> None:
    """Shut down the shared Proxmox executor and clear its cache entry.

    No-ops if the executor has not yet been initialised. Shuts down without
    waiting for in-flight tasks to complete (``wait=False``).
    """
    if get_proxmox_executor.cache_info().currsize == 0:
        return
    executor = get_proxmox_executor()
    get_proxmox_executor.cache_clear()
    executor.shutdown(wait=False)

