"""
In-memory sliding-window IP attempt tracker for conditional reCAPTCHA.

Tracks attempts per (IP, action) pair using monotonic timestamps in a deque.
Same pattern as _buckets in app/auth/middleware/rate_limit_middleware.py.
Includes TTL/size eviction per CLAUDE.md requirements.
"""

import time
from collections import deque

from app.config.settings import settings


class IPAttemptTracker:
    def __init__(self, max_tracked_ips: int = 10_000, eviction_age_seconds: int = 1800):
        self._buckets: dict[str, deque[float]] = {}
        self._max_tracked_ips = max_tracked_ips
        self._eviction_age_seconds = eviction_age_seconds

    def _key(self, ip: str, action: str) -> str:
        return f"{ip}:{action}"

    def increment(self, ip: str, action: str) -> None:
        key = self._key(ip, action)
        now = time.monotonic()
        if key not in self._buckets:
            if len(self._buckets) >= self._max_tracked_ips:
                self._evict_stale_buckets(now)
            self._buckets[key] = deque()
        self._buckets[key].append(now)

    def get_count(self, ip: str, action: str, window_seconds: int) -> int:
        key = self._key(ip, action)
        bucket = self._buckets.get(key)
        if not bucket:
            return 0
        cutoff = time.monotonic() - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if not bucket:
            del self._buckets[key]
            return 0
        return len(bucket)

    def reset(self, ip: str, action: str) -> None:
        key = self._key(ip, action)
        self._buckets.pop(key, None)

    def _evict_stale_buckets(self, now: float) -> None:
        stale_keys = [
            k for k, dq in self._buckets.items()
            if not dq or (now - dq[-1]) > self._eviction_age_seconds
        ]
        for k in stale_keys:
            del self._buckets[k]


ip_tracker = IPAttemptTracker(
    max_tracked_ips=settings.CAPTCHA_MAX_TRACKED_IPS,
    eviction_age_seconds=settings.CAPTCHA_EVICTION_AGE_SECONDS,
)
