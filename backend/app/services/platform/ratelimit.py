"""A per-client rate limit: at most `limit` requests in any `window` seconds (a sliding window, in memory).

    RateLimiter(limit, window=60).hit(key)  -> None if allowed, else the seconds until the next request is
                                               allowed (for Retry-After)

In memory is enough because the server runs one worker (Day 9). Each client keeps at most `limit`
timestamps, and clients idle for a whole window are dropped, so memory stays small.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Callable


class RateLimiter:
    def __init__(self, limit: int, window: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = clock()

    def hit(self, key: str) -> int | None:
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            if now - self._last_sweep > self.window:
                self._sweep(now)
            return None

    def _sweep(self, now: float) -> None:
        self._hits = {k: h for k, h in self._hits.items() if h and h[-1] > now - self.window}
        self._last_sweep = now

    def __len__(self) -> int:
        return len(self._hits)
