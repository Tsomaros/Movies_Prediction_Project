"""End-to-end tests for ml/data/build_db.py: a tiny raw pull -> SQLite, then query it."""

import json
import sqlite3

import pytest

import ml.data.build_db as build_db
from tests.factories import TEST_CPI, film


def director(person_id: int, name: str) -> dict:
    return {"cast": [{"id": 900, "name": "Lead", "character": "Hero", "order": 0}],
            "crew": [{"id": person_id, "name": name, "job": "Director"}]}


RECORDS = [
    # Revenue, budget and score training.
    film(1, title="Amélie", overview="A shy waitress in Montmartre.", credits=director(1, "Jean-Pierre Jeunet")),
    film(2, title="Heat", overview="A crew pulls off a bank heist.", credits=director(2, "Michael Mann")),
    film(3, title="Thief", overview="A safecracker takes one last job.", credits=director(2, "Michael Mann")),
    # Budget only.
    film(4, revenue=0, credits=director(2, "Michael Mann")),
    # Placeholder budget: no money training.
    film(5, budget=7, credits=director(3, "Someone")),
    # Token box office: suspect, kept for display.
    film(6, budget=65_500_000, revenue=1_281, credits=director(3, "Someone")),
    # Too few votes for the score model.
    film(7, vote_count=12, credits=director(3, "Someone")),
]


@pytest.fixture
def paths(tmp_path):
    raw = tmp_path / "tmdb_movies.jsonl"
    raw.write_text("".join(json.dumps(r) + "\n" for r in RECORDS), encoding="utf-8")
    cpi = tmp_path / "cpi.csv"
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in TEST_CPI.items()), encoding="utf-8")
    return raw, cpi, tmp_path / "movies.db"


@pytest.fixture
def db(paths):
    raw, cpi, out = paths
    build_db.build(raw, cpi, out)
    con = sqlite3.connect(out)
    yield con
    con.close()


def ids(con: sqlite3.Connection, sql: str, *args) -> list[int]:
    return [row[0] for row in con.execute(sql, args)]


def test_training_views(db):
    assert ids(db, "SELECT id FROM v_train_revenue ORDER BY id") == [1, 2, 3, 7]
    assert ids(db, "SELECT id FROM v_train_budget ORDER BY id") == [1, 2, 3, 4, 7]
    assert ids(db, "SELECT id FROM v_train_score ORDER BY id") == [1, 2, 3, 4, 5, 6]
    assert db.execute("SELECT DISTINCT split FROM v_train_score").fetchall() == [("test",)]


def test_every_film_is_kept_for_browsing(db):
    assert db.execute("SELECT COUNT(*) FROM movies").fetchone() == (7,)
    assert db.execute("SELECT budget, money_suspect FROM movies WHERE id = 6").fetchone() == (65_500_000, 1)


def test_full_text_search(db):
    search = "SELECT rowid FROM movies_fts WHERE movies_fts MATCH ? ORDER BY rank"
    assert ids(db, search, "bank") == [2]
    assert ids(db, search, "amelie") == [1]  # accents don't matter
    assert ids(db, search, "safecrack*") == [3]


def test_autocomplete_ranks_by_number_of_films(db):
    rows = db.execute("SELECT name, n_films FROM v_directors").fetchall()
    assert rows[:2] == [("Michael Mann", 3), ("Someone", 3)]
    assert db.execute("SELECT name FROM v_directors WHERE name LIKE 'jean%'").fetchall() == [("Jean-Pierre Jeunet",)]
    assert db.execute("SELECT name, n_films FROM v_actors").fetchall() == [("Lead", 7)]


def test_meta(db):
    meta = {k: json.loads(v) for k, v in db.execute("SELECT key, value FROM meta")}
    assert meta["vote_threshold"] == 50
    assert meta["cpi_base_year"] == 2025
    assert meta["built_at"].startswith("20")
    report = meta["cleaning_report"]
    assert report["films"] == 7 and report["money_suspect_low_ratio"] == 1


def test_failed_build_keeps_the_old_database(paths, monkeypatch):
    raw, cpi, out = paths
    build_db.build(raw, cpi, out)
    built_at = sqlite3.connect(out).execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(build_db, "write_db", broken)
    with pytest.raises(RuntimeError, match="disk full"):
        build_db.build(raw, cpi, out)

    con = sqlite3.connect(out)
    assert con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone() == built_at
    assert con.execute("SELECT COUNT(*) FROM movies").fetchone() == (7,)
    con.close()
    assert not out.with_name(out.name + ".tmp").exists()
