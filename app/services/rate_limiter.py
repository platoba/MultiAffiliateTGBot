"""
Rate limiter to prevent abuse.
Token-bucket algorithm per user.
"""

import time
from collections import defaultdict
from typing import NamedTuple


class RateLimit(NamedTuple):
    allowed: bool
    remaining: int
    reset_in: float


class RateLimiter:
    """Per-user rate limiter using token bucket."""

    def __init__(self, max_per_minute: int = 30, burst: int = 5):
        self.max_per_minute = max_per_minute
        self.burst = burst
        self.interval = 60.0 / max_per_minute
        self._buckets: dict[int, list[float]] = defaultdict(list)

    def check(self, user_id: int) -> RateLimit:
        """Check if a request is allowed."""
        now = time.time()
        window_start = now - 60.0

        # Clean old entries
        timestamps = self._buckets[user_id]
        self._buckets[user_id] = [t for t in timestamps if t > window_start]

        current_count = len(self._buckets[user_id])
        remaining = self.max_per_minute - current_count

        if current_count >= self.max_per_minute:
            oldest = min(self._buckets[user_id])
            reset_in = oldest + 60.0 - now
            return RateLimit(allowed=False, remaining=0, reset_in=max(0, reset_in))

        # Burst check - max N requests within 5 seconds
        burst_window = now - 5.0
        burst_count = sum(1 for t in self._buckets[user_id] if t > burst_window)
        if burst_count >= self.burst:
            return RateLimit(allowed=False, remaining=remaining, reset_in=5.0)

        self._buckets[user_id].append(now)
        return RateLimit(allowed=True, remaining=remaining - 1, reset_in=0)

    def reset(self, user_id: int):
        """Reset rate limit for a user."""
        self._buckets.pop(user_id, None)

    def reset_all(self):
        """Reset all rate limits."""
        self._buckets.clear()

    @property
    def active_users(self) -> int:
        """Number of users with active rate limit entries."""
        return len(self._buckets)
