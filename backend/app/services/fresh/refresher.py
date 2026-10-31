"""Keeping the new and upcoming films fresh (V1.2): one background refresh at a time, every 6 hours.

    Refresher(db_path, token, min_popularity, ttl_s, listed, clock, make_client=TMDBClient)
        prepare()      -> before serving: one read-write open (rolls back a merge a crash left half done) and the
                          two tables; False, and the refresh off, without a token or when the file can't be written
        due()          -> True when a refresh should start: a token is set, none is running, the last success is
                          older than ttl_s (or there was none) and the last failure is over 60 s ago
        maybe_start()  -> starts run() as a background task when due() (never waits for it), else None
        await run()    -> {"films", "listed", "skipped", "removed"}: pulls the two windows plus every listed film (in
                          a user's list or notes) the build lacks and merges them. Any failure keeps the database as
                          it was, is logged once and backs off; nothing is raised
        status()       -> {"refreshed_at", "films"} (None before the first refresh)
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.app.services.fresh.merge import ensure_tables, merge_into, open_for_writing
from backend.app.services.fresh.pull import discover_ids, pull_details
from ml.data.clean import load_cpi
from ml.data.tmdb_client import TMDBClient

log = logging.getLogger("uvicorn.error")

BACKOFF_S = 60


class Refresher:
    def __init__(self, db_path: Path, token: str | None, min_popularity: float, ttl_s: int,
                 listed: Callable[[], set[int]] | None, clock: Callable[[], datetime],
                 make_client: Callable[[str], TMDBClient] = TMDBClient):
        self.db_path, self.token = Path(db_path), token
        self.min_popularity, self.ttl_s, self.listed, self.clock, self.make_client = min_popularity, ttl_s, listed, clock, make_client
        self._running, self._task = False, None
        self._last_ok: datetime | None = None
        self._failed_at: datetime | None = None
        self._status = {"refreshed_at": None, "films": None}

    def prepare(self) -> bool:
        """Before serving: open the database read-write once, so SQLite rolls back a merge a crash left half done
        (a read-only connection can't), and make the two tables. A file that can't be written turns the refresh off."""
        if not self.token:
            return False
        try:
            with closing(open_for_writing(self.db_path)) as con:
                ensure_tables(con)
        except (OSError, sqlite3.Error) as e:
            log.warning("fresh: %s can't be written (%s); new films are off", self.db_path, e)
            self.token = None
            return False
        return True

    def due(self) -> bool:
        if not self.token or self._running:
            return False
        now = self.clock()
        if self._failed_at is not None and (now - self._failed_at).total_seconds() < BACKOFF_S:
            return False
        return self._last_ok is None or (now - self._last_ok).total_seconds() >= self.ttl_s

    def maybe_start(self) -> asyncio.Task | None:
        if not self.due():
            return None
        self._running = True  # at once, so a second call before the task has started finds it running
        self._task = asyncio.get_running_loop().create_task(self.run())
        return self._task

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    def _listed(self) -> set[int]:
        if self.listed is None:
            return set()
        try:
            return set(self.listed())
        except Exception as e:  # Postgres down: the windows still refresh
            log.warning("fresh: the listed films could not be read: %s", e)
            return set()

    def _in_build(self, ids: set[int]) -> set[int]:
        """The ids among them that the database has from its build (a film the refresher added is pulled again)."""
        from backend.app.deps import connect_read_only
        from backend.app.repo.movies import ids_present

        found: set[int] = set()
        with closing(connect_read_only(self.db_path)) as con:
            wanted = sorted(ids)
            for i in range(0, len(wanted), 500):
                part = wanted[i:i + 500]
                found |= ids_present(con, part) - {r[0] for r in con.execute(
                    f"SELECT id FROM fresh_films WHERE added AND id IN ({','.join('?' * len(part))})", part)}
        return found

    def _write(self, records: list[dict[str, Any]], refreshed_at: str) -> dict[str, int]:
        with closing(open_for_writing(self.db_path)) as con:
            return merge_into(con, records, load_cpi(), refreshed_at)

    async def run(self) -> dict[str, Any]:
        self._running = True
        now = self.clock()
        try:
            async with self.make_client(self.token) as client:
                window = await discover_ids(client, now.date(), self.min_popularity)
                listed = await asyncio.to_thread(self._listed)
                known = await asyncio.to_thread(self._in_build, listed) if listed else set()
                extra = sorted(listed - known - set(window))
                wanted = window + extra
                records = await pull_details(client, wanted, now.isoformat(timespec="seconds"))
            merged = await asyncio.to_thread(self._write, records, now.isoformat(timespec="seconds"))
        except Exception as e:  # TMDB or disk trouble: the merge was rolled back; try again after the back-off
            log.warning("fresh: refresh failed (%s: %s)", type(e).__name__, e)
            self._failed_at = now
            return {"films": 0, "listed": 0, "skipped": 0, "removed": 0, "error": str(e)}
        finally:
            self._running = False
        self._last_ok, self._failed_at = now, None
        self._status = {"refreshed_at": now.isoformat(timespec="seconds"), "films": merged["films"]}
        skipped = len(wanted) - len(records) + merged["skipped"]  # not fetched, or dated 2025 or earlier
        log.info("fresh: %d films (%d listed, %d skipped, %d removed)", merged["films"], len(extra), skipped,
                 merged["removed"])
        return {"films": merged["films"], "listed": len(extra), "skipped": skipped, "removed": merged["removed"]}
