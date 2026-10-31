"""Read-only queries about the database itself, for /meta/options and /health.

    common_codes(con, column, n)   -> [{code, films}]: the n most common original languages or production countries
    build_info(con)                -> {built_at, films}: when data/movies.db was built and how many films it has
    year_range(con)                -> (first, last) release year in the database

All of them count the database's build only: a film the refresher added (fresh_films.added, V1.3) is left out, so
the numbers stay those of the data the models were trained beside.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

BUILT = "NOT IN (SELECT id FROM fresh_films WHERE added)"
CODES = {  # what can be counted -> its SQL
    "language": f"SELECT original_language, COUNT(*) FROM movies WHERE original_language IS NOT NULL AND id {BUILT} "
                "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT ?",
    "country": f"SELECT country, COUNT(*) FROM movie_countries WHERE movie_id {BUILT} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT ?",
}


def common_codes(con: sqlite3.Connection, column: str, n: int) -> list[dict[str, Any]]:
    return [{"code": code, "films": films} for code, films in con.execute(CODES[column], (n,))]


def build_info(con: sqlite3.Connection) -> dict[str, Any]:
    row = con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()
    return {"built_at": json.loads(row[0]) if row else None,
            "films": con.execute(f"SELECT COUNT(*) FROM movies WHERE id {BUILT}").fetchone()[0]}


def year_range(con: sqlite3.Connection) -> tuple[int, int]:
    first, last = con.execute(f"SELECT MIN(year), MAX(year) FROM movies WHERE id {BUILT}").fetchone()
    return int(first), int(last)
