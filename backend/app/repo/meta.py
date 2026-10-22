"""Read-only queries about the database itself, for /meta/options and /health.

    common_codes(con, column, n)   -> [{code, films}]: the n most common original languages or production countries
    build_info(con)                -> {built_at, films}: when data/movies.db was built and how many films it has
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

CODES = {  # what can be counted -> its SQL
    "language": "SELECT original_language, COUNT(*) FROM movies WHERE original_language IS NOT NULL "
                "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT ?",
    "country": "SELECT country, COUNT(*) FROM movie_countries GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT ?",
}


def common_codes(con: sqlite3.Connection, column: str, n: int) -> list[dict[str, Any]]:
    return [{"code": code, "films": films} for code, films in con.execute(CODES[column], (n,))]


def build_info(con: sqlite3.Connection) -> dict[str, Any]:
    row = con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()
    return {"built_at": json.loads(row[0]) if row else None,
            "films": con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]}
