"""V1.5: the browse sorts' indexes (build_db.SORT_INDEXES) and the "+" in repo.search change speed, never the answer.

The same searches on a database with the indexes and on a copy without them must return the same ids and totals.
The real-data test also checks that the planner walks the sort's index for the home rows.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from backend.app.repo import movies as repo
from ml.data.build_db import SORT_INDEXES
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

TODAY = date(2026, 11, 1)
NAMES = re.findall(r"CREATE INDEX IF NOT EXISTS (\w+)", SORT_INDEXES)
SEARCHES = [
    {"sort": "popularity"}, {"sort": "popularity", "page": 2, "page_size": 7}, {"sort": "score"},
    {"sort": "revenue"}, {"sort": "popularity", "year_from": 2010, "year_to": 2012},
    {"sort": "popularity", "year_from": 1990, "year_to": 1999}, {"sort": "score", "genre": "Action"},
    {"sort": "revenue", "language": "en", "page_size": 48}, {"sort": "score", "score_min": 6.0},
    {"sort": "newest"}, {"sort": "title"}, {"sort": "popularity", "q": "film"},
    {"sort": "popularity", "when": "released"},
]
BASE = {"page": 1, "page_size": 12}


def answers(con: sqlite3.Connection) -> list[tuple[list[int], int]]:
    con.row_factory = sqlite3.Row
    out = []
    for kw in SEARCHES:
        rows, total = repo.search(con, today=TODAY, **{**BASE, **kw})
        out.append(([r["id"] for r in rows], total))
    return out


def drop_sort_indexes(con: sqlite3.Connection) -> None:
    for name in NAMES:
        con.execute(f"DROP INDEX IF EXISTS {name}")


def test_the_built_database_has_the_sort_indexes(db):  # noqa: F811
    with sqlite3.connect(db / "movies.db") as con:
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert set(NAMES) <= have and len(NAMES) == 6


def test_slim_db_adds_them_to_a_database_built_without(db, tmp_path):  # noqa: F811
    from scripts.slim_db import slim
    src = tmp_path / "old.db"
    with sqlite3.connect(db / "movies.db") as con, sqlite3.connect(src) as old:
        con.backup(old)
    with sqlite3.connect(src) as con:
        drop_sort_indexes(con)
    slim(src, tmp_path / "slim.db")
    with sqlite3.connect(tmp_path / "slim.db") as con:
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert set(NAMES) <= have


def test_the_same_answers_with_and_without_the_indexes(db):  # noqa: F811
    with sqlite3.connect(db / "movies.db") as con:
        indexed = answers(con)
        copy = sqlite3.connect(":memory:")
        con.backup(copy)
    drop_sort_indexes(copy)
    assert answers(copy) == indexed
    assert all(total > 0 for _, total in indexed[:4])


REAL = Path("build/movies.db")


@pytest.mark.real_data
@pytest.mark.slow
@pytest.mark.skipif(not REAL.exists(), reason="needs build/movies.db (make docker-build)")
def test_the_image_database_answers_the_same_and_the_planner_walks_the_sort_index():
    con = sqlite3.connect(f"file:{REAL.resolve().as_posix()}?mode=ro", uri=True)
    indexed = answers(con)
    plan = lambda sql: " ".join(r[3] for r in con.execute("EXPLAIN QUERY PLAN " + sql))
    where = "+m.release_date IS NOT NULL AND +m.release_date <= '2026-11-01'"
    assert "idx_movies_popularity" in plan(f"SELECT m.id FROM movies m WHERE {where} ORDER BY {repo.SORTS['popularity']} LIMIT 12")
    assert "idx_movies_score" in plan(f"SELECT m.id FROM movies m WHERE {where} AND m.vote_count >= 500 "
                                      f"ORDER BY {repo.SORTS['score']} LIMIT 12")
    assert "idx_movies_revenue" in plan(f"SELECT m.id FROM movies m WHERE {where} AND m.revenue_2025 IS NOT NULL "
                                        f"AND NOT m.money_suspect ORDER BY {repo.SORTS['revenue']} LIMIT 12")
    memory = sqlite3.connect(":memory:")
    con.backup(memory)
    drop_sort_indexes(memory)
    assert answers(memory) == indexed
