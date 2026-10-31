"""One refresh by hand: uv run python -m backend.app.services.fresh --once (point MOVIES_DB at a copy)."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from backend.app.services.fresh.refresher import Refresher


def _once() -> None:
    from backend.app.settings import Settings
    from backend.app.userdb.pool import make_pool
    from backend.app.userdb import repo as userdb

    settings = Settings.from_env()
    pool = make_pool(settings.user_database_url) if settings.user_database_url else None

    def listed() -> set[int]:
        with pool.connection() as conn:
            return userdb.listed_movie_ids(conn)

    refresher = Refresher(settings.db_path, settings.tmdb_read_token, settings.fresh_min_popularity,
                          settings.fresh_ttl_s, listed if pool else None, lambda: datetime.now(timezone.utc))
    if not refresher.prepare():
        raise SystemExit("TMDB_READ_TOKEN is not set or the database can't be written")
    print(json.dumps(asyncio.run(refresher.run())))
    if pool:
        pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge the new and upcoming films into MOVIES_DB once.")
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    _once()
