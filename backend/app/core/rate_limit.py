"""Simple in-memory sliding-window rate limiter for FastAPI.

Usage as a dependency::

    from app.core.rate_limit import RateLimiter

    @router.post("/expensive")
    async def expensive_op(
        _rl=Depends(RateLimiter(max_calls=5, window_seconds=60)),
    ):
        ...

The limiter keys by client IP (from X-Forwarded-For or client.host).
Old entries are lazily purged on each check, and stale IPs are evicted
periodically to prevent unbounded memory growth.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

# Maximum number of distinct bucket keys before a full eviction pass is forced.
_MAX_BUCKET_KEYS = 10_000


class RateLimiter:
    """Callable FastAPI dependency that enforces per-IP rate limits."""

    _buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    _last_eviction: float = 0.0
    _EVICTION_INTERVAL: float = 300.0  # seconds between full eviction passes

    def __init__(self, *, max_calls: int, window_seconds: int) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._key = f"{max_calls}/{window_seconds}s"

    async def __call__(self, request: Request) -> None:
        ip = _client_ip(request)
        bucket_key = f"{self._key}:{ip}"
        now = time.monotonic()
        hits = self._buckets[self._key][bucket_key]

        # Purge expired entries for this IP
        cutoff = now - self._window
        while hits and hits[0] < cutoff:
            hits.pop(0)

        if len(hits) >= self._max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {self._window}s.",
            )
        hits.append(now)

        # Periodic eviction of stale IPs across all buckets
        self._maybe_evict(now)

    @classmethod
    def _maybe_evict(cls, now: float) -> None:
        """Remove empty bucket keys to prevent unbounded dict growth."""
        total_keys = sum(len(b) for b in cls._buckets.values())
        if total_keys < _MAX_BUCKET_KEYS and (now - cls._last_eviction) < cls._EVICTION_INTERVAL:
            return
        cls._last_eviction = now
        for rule_key, ip_buckets in list(cls._buckets.items()):
            for bucket_key in list(ip_buckets.keys()):
                if not ip_buckets[bucket_key]:
                    del ip_buckets[bucket_key]
            if not ip_buckets:
                del cls._buckets[rule_key]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
