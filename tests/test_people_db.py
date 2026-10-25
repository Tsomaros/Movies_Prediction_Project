"""person_details in the movie database (Day 14.6): always created, filled by people.load (rerunnable) or the build."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date

import pytest

from ml.data import build_db, people
from tests.test_eval import CPI, RECORDS, db  # noqa: F401 (fixture: a small movies.db; actors 2001-2300)

TODAY = date(2026, 11, 1)


def rec(person_id, fetched_at="2026-10-25T10:00:00+00:00", **fields):
    return {"id": person_id, "name": f"Person {person_id}", "profile_path": f"/p{person_id}.jpg",
            "biography": "First line.\n\nSecond line.", "birthday": "1970-01-02", "deathday": None,
            "place_of_birth": "Athens, Greece", "known_for_department": "Acting", "imdb_id": "nm0000001",
            "homepage": None, "popularity": 3.5, "fetched_at": fetched_at, **fields}


@pytest.fixture
def con(db, tmp_path):
    shutil.copyfile(db / "movies.db", tmp_path / "movies.db")
    c = sqlite3.connect(tmp_path / "movies.db")
    yield c
    c.close()


def write(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def test_every_built_database_has_an_empty_person_details_table(con):
    assert con.execute("SELECT COUNT(*) FROM person_details").fetchone() == (0,)


def test_load_keeps_known_people_skips_unknown_ids_and_records_coverage(con, tmp_path):
    path = write(tmp_path / "p.jsonl", [rec(2001), rec(2002, profile_path=None, biography=" "), rec(999_999)])
    stats = people.load(con, path, TODAY)
    assert stats["people_with_details"] == 2 and stats["skipped_unknown_id"] == 1
    assert stats["pct_photo"] == 50.0 and stats["pct_biography"] == 50.0 and stats["pct_birthday"] == 100.0
    assert json.loads(con.execute("SELECT value FROM meta WHERE key = 'people_details'").fetchone()[0]) == stats
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    row = con.execute("SELECT person_id, tmdb_popularity, biography FROM person_details WHERE person_id = 2001").fetchone()
    assert row == (2001, 3.5, "First line.\n\nSecond line.")


def test_load_is_rerunnable_and_the_newest_record_wins(con, tmp_path):
    path = write(tmp_path / "p.jsonl", [rec(2001, biography="Old."),
                                        rec(2001, fetched_at="2026-10-26T10:00:00+00:00", biography="New.")])
    people.load(con, path, TODAY)
    people.load(con, path, TODAY)
    assert con.execute("SELECT biography FROM person_details").fetchall() == [("New.",)]


def test_load_leaves_the_build_stamp_alone(con, tmp_path):
    before = con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()
    people.load(con, write(tmp_path / "p.jsonl", [rec(2001)]), TODAY)
    assert con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone() == before


def test_bio_max_chars_cuts_biographies(con, tmp_path):
    people.load(con, write(tmp_path / "p.jsonl", [rec(2001, biography="One. " * 400)]), TODAY, bio_max_chars=1500)
    assert con.execute("SELECT MAX(LENGTH(biography)) FROM person_details").fetchone()[0] <= 1500


def test_the_build_loads_the_person_pull_when_given(tmp_path):
    raw, cpi = tmp_path / "raw.jsonl", tmp_path / "cpi.csv"
    raw.write_text("".join(json.dumps(r) + "\n" for r in RECORDS[:30]), encoding="utf-8")
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in CPI.items()), encoding="utf-8")
    report = build_db.build(raw, cpi, tmp_path / "movies.db", write(tmp_path / "p.jsonl", [rec(2001), rec(999_999)]))
    assert report["people_details"]["people_with_details"] == 1
    with sqlite3.connect(tmp_path / "movies.db") as c:
        assert c.execute("SELECT person_id FROM person_details").fetchall() == [(2001,)]
