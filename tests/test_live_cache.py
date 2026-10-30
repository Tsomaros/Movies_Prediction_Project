"""The live new/upcoming cache (V1.2): one refresh at a time, a stale copy when TMDB fails, a warm-up that never raises."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.live import RETRY_AFTER_FAILURE_S, LiveCache, LiveUnavailable, warm_up

START = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
TTL = 6 * 3600


class Clock:
    def __init__(self):
        self.t = START

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


class Fetch:
    def __init__(self):
        self.calls, self.fail, self.delay = 0, False, 0.0

    async def __call__(self, today):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise LiveUnavailable("down")
        film = lambda i: {"tmdb_id": i, "movie_id": None, "title": f"Film {i}", "original_title": f"Film {i}"}
        return [film(123), film(2)], [film(3)]


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fetch():
    return Fetch()


@pytest.fixture
def cache(fetch, clock):
    return LiveCache(fetch, lambda ids: {i for i in ids if i == 123}, TTL, now=clock)


async def test_a_fresh_hit_makes_no_call(cache, fetch):
    await cache.get()
    r = await cache.get()
    assert fetch.calls == 1 and r["stale"] is False and len(r["new"]) == 2 and len(r["upcoming"]) == 1


async def test_expiry_refreshes_once(cache, fetch, clock):
    await cache.get()
    clock.advance(hours=6, seconds=1)
    await cache.get()
    assert fetch.calls == 2


async def test_ten_concurrent_requests_make_one_refresh(cache, fetch):
    fetch.delay = 0.2
    await asyncio.gather(*[cache.get() for _ in range(10)])
    assert fetch.calls == 1


async def test_waiters_get_the_old_copy_while_a_refresh_runs(cache, fetch, clock):
    await cache.get()
    clock.advance(hours=7)
    fetch.delay = 0.2
    results = await asyncio.gather(*[cache.get() for _ in range(5)])
    assert fetch.calls == 2 and all(len(r["new"]) == 2 for r in results)


async def test_an_error_serves_the_stale_copy(cache, fetch, clock):
    await cache.get()
    clock.advance(hours=7)
    fetch.fail = True
    r = await cache.get()
    assert r["stale"] is True and len(r["new"]) == 2


async def test_an_error_without_a_copy_gives_empty_lists_and_is_not_retried_at_once(cache, fetch, clock):
    fetch.fail = True
    r = await cache.get()
    assert r["stale"] is True and r["new"] == [] and r["upcoming"] == [] and r["fetched_at"] is None
    await cache.get()
    assert fetch.calls == 1  # backing off
    clock.advance(seconds=RETRY_AFTER_FAILURE_S + 1)
    fetch.fail = False
    r = await cache.get()
    assert fetch.calls == 2 and r["stale"] is False and len(r["new"]) == 2


async def test_movie_id_is_filled_for_films_in_the_database(cache):
    r = await cache.get()
    assert next(f for f in r["new"] if f["tmdb_id"] == 123)["movie_id"] == 123
    assert next(f for f in r["new"] if f["tmdb_id"] == 2)["movie_id"] is None


async def test_a_warm_up_failure_does_not_raise(cache, fetch):
    fetch.fail = True
    await warm_up(cache)


async def test_a_slow_fetch_is_cut_off(clock):
    async def slow(today):
        await asyncio.sleep(30)

    import backend.app.services.live as live
    old = live.REFRESH_TIMEOUT_S
    live.REFRESH_TIMEOUT_S = 0.05
    try:
        r = await LiveCache(slow, lambda ids: set(), TTL, now=clock).get()
    finally:
        live.REFRESH_TIMEOUT_S = old
    assert r["stale"] is True and r["new"] == []


def test_peek_never_fetches(cache, fetch):
    assert cache.peek() is None and fetch.calls == 0
