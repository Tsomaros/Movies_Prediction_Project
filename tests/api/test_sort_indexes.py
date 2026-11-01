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
    {"sort": "title", "page": 2}, {"sort": "newest", "page": 3, "page_size": 20}, {"sort": "newest", "language": "en"},
    {"sort": "score", "genre": "Drama", "year_from": 2009, "year_to": 2020, "page_size": 24},
    {"sort": "popularity", "year_from": 2015, "score_min": 5.0}, {"sort": "title", "q": "film"},
    {"sort": "newest", "q": "film 1"}, {"sort": "score", "q": "film", "genre": "Comedy"}, {"sort": "revenue", "q": "film"},
    {"sort": "soonest", "when": "upcoming"}, {"sort": "popularity", "q": "the"}, {"sort": "title", "q": "the"},
    {"sort": "newest", "q": "love", "page": 2}, {"language": "en", "score_min": 6.0, "sort": "newest", "page": 2},
    {"language": "en", "score_min": 6.0}, {"language": "fr", "score_min": 7.5, "sort": "title"},
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
    assert set(NAMES) <= have and len(NAMES) == 10


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
    assert "idx_movies_title" in plan(f"SELECT m.id FROM movies m WHERE {where} ORDER BY {repo.SORTS['title']} LIMIT 12")
    assert "idx_movies_newest" in plan(f"SELECT m.id FROM movies m WHERE {where} ORDER BY {repo.SORTS['newest']} LIMIT 12")
    assert "idx_movies_votes_year" in plan("SELECT COUNT(*) FROM movies m WHERE +m.release_date IS NOT NULL AND "
                                           "+m.year >= 2000 AND +m.year <= 2020 AND m.vote_count >= 500")
    assert "idx_movies_language_score" in plan(
        "SELECT COUNT(*) FROM movies m WHERE +m.release_date IS NOT NULL AND m.original_language = 'fr' "
        "AND +m.vote_count > 0 AND m.vote_average >= 7")
    memory = sqlite3.connect(":memory:")
    con.backup(memory)
    drop_sort_indexes(memory)
    assert answers(memory) == indexed


@pytest.mark.parametrize("sort", ["popularity", "score", "revenue", "title", "newest"])
def test_a_common_word_walks_the_sort_index_and_finds_the_same_films(db, monkeypatch, sort):  # noqa: F811
    """A text search matching WALK_MIN_MATCHES films walks the sort's index instead of sorting the matches."""
    got = {}
    with sqlite3.connect(db / "movies.db") as con:
        con.row_factory = sqlite3.Row
        for threshold in (10**9, 1):
            monkeypatch.setattr(repo, "WALK_MIN_MATCHES", threshold)
            got[threshold] = [repo.search(con, today=TODAY, q=q, sort=sort, page=page, page_size=10)
                              for q in ("film", "film 2", "fil") for page in (1, 2, 3)]
    assert got[1] == got[10**9]
    assert all(total > 0 and rows for rows, total in got[1][:2])
