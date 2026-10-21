"""Async TMDB API client.

- Auth with the v4 API Read Access Token (Bearer header), read from `.env`.
- Throttled to about 20 requests/second, with a cap on requests in flight.
- Retries 429 (honouring Retry-After), 5xx and network errors with exponential backoff.
- A 404 returns None so callers can skip that film; other 4xx errors raise.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.themoviedb.org/3"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_DELAY = 60.0


class TMDBError(Exception):
    """Raised when a request still fails after all retries."""


class RateLimiter:
    """Spaces request starts at least `1 / rate` seconds apart."""

    def __init__(self, rate: float) -> None:
        self.interval = 1.0 / rate
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        # Reserve the next free slot under the lock, then sleep outside it,
        # so waiting callers don't block each other from reserving.
        async with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self.interval
        delay = start - now
        if delay > 0:
            await asyncio.sleep(delay)


class TMDBClient:
    def __init__(
        self,
        token: str,
        *,
        rate: float = 20.0,
        max_concurrency: int = 10,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        timeout: float = 30.0,
        base_url: str = BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._limiter = RateLimiter(rate)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls, **kwargs: Any) -> TMDBClient:
        load_dotenv()
        token = os.getenv("TMDB_READ_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TMDB_READ_TOKEN is not set. Copy .env.example to .env and add your token.")
        return cls(token, **kwargs)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """GET `path` and return the JSON body, or None on 404."""
        last_problem = ""
        for attempt in range(1, self.max_retries + 1):
            response = None
            async with self._semaphore:
                await self._limiter.wait()
                try:
                    response = await self._http.get(path, params=params)
                except httpx.TransportError as exc:
                    last_problem = f"{type(exc).__name__}: {exc}"

            if response is not None:
                if response.status_code == 404:
                    return None
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()
                    return response.json()
                last_problem = f"HTTP {response.status_code}"

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay(response, attempt))

        raise TMDBError(f"GET {path} failed after {self.max_retries} attempts ({last_problem})")

    def retry_delay(self, response: httpx.Response | None, attempt: int) -> float:
        """Seconds to wait before the next attempt."""
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return min(float(retry_after), MAX_RETRY_DELAY)
                except ValueError:
                    pass
        delay = self.backoff_base * 2 ** (attempt - 1) + random.uniform(0, self.backoff_base)
        return min(delay, MAX_RETRY_DELAY)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> TMDBClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
