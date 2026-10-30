"""The refresher (V1.2): when it is due, which films it pulls, and that a failure never breaks the file."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import backend.app.services.fresh as fresh
from backend.app.services.fresh import Refresher
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)
from tests.test_fresh_build import FakeTMDB, client_for, disc

START = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
WINDOW = [5001, 5002, 5010]


class Clock:
    def __init__(self):
        self.t = START

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fake():
    return FakeTMDB(released=[[disc(5001), disc(5002)]], upcoming=[[disc(5010)]])


@pytest.fixture
def refresher_factory(tmp_path, db, fake, clock):  # noqa: F811
    def make(**over) -> Refresher:
        args = dict(fresh_path=tmp_path / "fresh.db", main_db=db / "movies.db", token="t", min_popularity=5.0,
                    ttl_s=21600, listed=None, clock=clock, make_client=lambda token: client_for(fake))
        r = Refresher(**{**args, **over})
        make.last = r
        return r
    return make


def ids_in(path) -> set[int]:
    with sqlite3.connect(path) as con:
        return {r[0] for r in con.execute("SELECT id FROM movies")}


def test_due_rules(refresher_factory, clock):
    assert not refresher_factory(token=None).due()
    r = refresher_factory()
    assert r.due()
    asyncio.run(r.run())
    assert not r.due()
    clock.advance(hours=6, seconds=1)
    assert r.due()


def test_a_refresh_writes_the_windows_and_reports_its_status(refresher_factory):
    r = refresher_factory()
    out = asyncio.run(r.run())
    assert out == {"films": 3, "listed": 0, "skipped": 0} and ids_in(r.fresh_path) == set(WINDOW)
    assert r.status() == {"refreshed_at": "2026-10-30T12:00:00+00:00", "films": 3}


def test_refresh_keeps_a_listed_film_outside_the_window(refresher_factory):
    r = refresher_factory(listed=lambda: {777})  # a film not in movies.db
    out = asyncio.run(r.run())
    assert out["listed"] == 1 and ids_in(r.fresh_path) == {777, *WINDOW}


def test_a_listed_film_already_in_main_is_not_pulled(refresher_factory, fake):
    asyncio.run(refresher_factory(listed=lambda: {3}).run())  # film 3 is in the small movies.db
    assert 3 not in fake.detail_calls


def test_refresh_skips_a_missing_listed_film_and_still_swaps_the_file(refresher_factory, fake):
    fake.not_found.add(888)
    r = refresher_factory(listed=lambda: {888})
    out = asyncio.run(r.run())
    assert out["skipped"] == 1 and 888 not in ids_in(r.fresh_path) and ids_in(r.fresh_path) == set(WINDOW)


def test_postgres_trouble_still_refreshes_the_windows(refresher_factory):
    def broken():
        raise RuntimeError("no database")
    r = refresher_factory(listed=broken)
    assert asyncio.run(r.run())["films"] == 3


def test_a_failure_keeps_the_old_file_and_backs_off(refresher_factory, fake, clock):
    r = refresher_factory()
    asyncio.run(r.run())
    before = r.fresh_path.read_bytes()
    clock.advance(hours=7)
    fake.fail_discover = True
    assert "error" in asyncio.run(r.run())
    assert r.fresh_path.read_bytes() == before and not r.due()
    clock.advance(seconds=61)
    assert r.due()


def test_the_tmp_file_is_never_left_behind(refresher_factory, monkeypatch):
    def broken(records, cpi, path, meta):
        path.write_bytes(b"half a database")
        raise RuntimeError("disk full")
    monkeypatch.setattr(fresh, "build_fresh_db", broken)
    r = refresher_factory()
    asyncio.run(r.run())
    assert not r.tmp_path.exists() and not r.fresh_path.exists()


async def test_only_one_refresh_at_a_time(refresher_factory):
    r = refresher_factory()
    first = r.maybe_start()
    assert first is not None and r.maybe_start() is None  # running: a second call starts nothing
    await first
    assert r.maybe_start() is None  # and a fresh file is not due again
