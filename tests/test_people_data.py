"""The TMDB person pull (Day 14.6), offline: slimming, cleaning, the bio cut, which ids, resume, refresh, summary."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone

import httpx

from ml.data.people import (PERSON_FIELDS, clean_person, drop_older_than, person_ids, slim_person, summarize,
                            truncate_bio)
from ml.data.pull import run_details
from ml.data.tmdb_client import TMDBClient

T = "2026-11-01T10:00:00+00:00"
TODAY = date(2026, 11, 1)
FULL_RAW = {"id": 31, "name": "Tom Hanks", "profile_path": "/hanks.jpg", "biography": "An actor.",
            "birthday": "1956-07-09", "deathday": None, "place_of_birth": "Concord, California, USA",
            "known_for_department": "Acting", "imdb_id": "nm0000158", "homepage": "https://example.com",
            "popularity": 42.5}


def test_slim_keeps_only_person_fields():
    out = slim_person({**FULL_RAW, "also_known_as": ["x"], "adult": False}, T)
    assert set(out) == set(PERSON_FIELDS) | {"fetched_at"} and out["fetched_at"] == T


def test_clean_maps_id_and_popularity_and_keeps_good_values():
    row = clean_person({**FULL_RAW, "fetched_at": T}, TODAY)
    assert row["person_id"] == 31 and row["tmdb_popularity"] == 42.5 and row["birthday"] == "1956-07-09"
    assert row["imdb_id"] == "nm0000158" and row["homepage"] == "https://example.com" and row["fetched_at"] == T


def test_clean_blank_strings_become_none():
    row = clean_person({**FULL_RAW, "biography": "  ", "homepage": "", "place_of_birth": None, "fetched_at": T}, TODAY)
    assert row["biography"] is None and row["homepage"] is None and row["place_of_birth"] is None


def test_clean_future_and_bad_dates():
    row = clean_person({**FULL_RAW, "birthday": "2030-01-01", "deathday": "not-a-date", "fetched_at": T}, TODAY)
    assert row["birthday"] is None and row["deathday"] is None


def test_clean_death_before_birth_drops_both():
    row = clean_person({**FULL_RAW, "birthday": "1960-05-01", "deathday": "1950-01-01", "fetched_at": T}, TODAY)
    assert row["birthday"] is None and row["deathday"] is None


def test_clean_refuses_links_that_are_not_web_pages_or_imdb_ids():
    row = clean_person({**FULL_RAW, "homepage": "javascript:alert(1)", "imdb_id": "tt123", "fetched_at": T}, TODAY)
    assert row["homepage"] is None and row["imdb_id"] is None


def test_truncate_bio_cuts_at_a_sentence_end():
    out = truncate_bio("One. " * 400, 1500)
    assert len(out) <= 1500 and out.endswith(".")
    assert truncate_bio("Short.", 1500) == "Short." and truncate_bio(None, 1500) is None
    no_stop = truncate_bio("x" * 2000, 1500)
    assert len(no_stop) == 1500 and no_stop.endswith("…")


def test_person_ids_are_cast_members_with_enough_films_most_films_first():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE movie_cast (movie_id INTEGER, person_id INTEGER, character TEXT, ord INTEGER)")
    con.executemany("INSERT INTO movie_cast VALUES (?, ?, NULL, 0)",
                    [(1, 100), (2, 100), (3, 100), (1, 101), (2, 101), (1, 102)])
    assert person_ids(con, 2) == [100, 101] and person_ids(con, 1) == [100, 101, 102]


class FakePeople:
    def __init__(self, missing=frozenset()):
        self.missing, self.calls = missing, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        person_id = int(request.url.path.rsplit("/", 1)[1])
        self.calls.append((request.url.path, dict(request.url.params)))
        if person_id in self.missing:
            return httpx.Response(404)
        return httpx.Response(200, json={**FULL_RAW, "id": person_id, "also_known_as": []})


async def pull(fake, ids, tmp_path):
    out = tmp_path / "people.jsonl"
    async with TMDBClient("t", rate=10_000, backoff_base=0, transport=httpx.MockTransport(fake)) as client:
        return await run_details(client, ids, out, tmp_path / "missing_people.txt", endpoint="/person/{}",
                                 params={"language": "en-US"}, trim=slim_person)


def ids_in(path):
    return sorted(json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines())


async def test_the_pull_asks_person_endpoint_in_english_resumes_and_records_404s(tmp_path):
    fake = FakePeople(missing={102})
    assert await pull(fake, [100, 101, 102], tmp_path) == {"saved": 2, "missing": 1, "failed": 0}
    assert fake.calls[0] == ("/3/person/100", {"language": "en-US"})
    assert ids_in(tmp_path / "people.jsonl") == [100, 101]
    fake.calls.clear()
    assert await pull(fake, [100, 101, 102, 103], tmp_path) == {"saved": 1, "missing": 0, "failed": 0}
    assert [c[0] for c in fake.calls] == ["/3/person/103"]  # saved and 404 ids are not asked again


async def test_refresh_pulls_only_old_records_again_and_leaves_one_line_per_id(tmp_path):
    path = tmp_path / "people.jsonl"
    lines = [{**FULL_RAW, "id": 100, "fetched_at": "2026-01-01T00:00:00+00:00"},
             {**FULL_RAW, "id": 101, "fetched_at": "2026-10-20T00:00:00+00:00"},
             {**FULL_RAW, "id": 101, "fetched_at": "2026-10-01T00:00:00+00:00"}]  # an older duplicate
    path.write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    assert drop_older_than(path, 180, datetime(2026, 10, 25, tzinfo=timezone.utc)) == 1
    assert ids_in(path) == [101]
    fake = FakePeople()
    await pull(fake, [100, 101], tmp_path)
    assert [c[0] for c in fake.calls] == ["/3/person/100"] and ids_in(path) == [100, 101]


def test_summary_counts_each_person_once(tmp_path):
    path = tmp_path / "people.jsonl"
    recs = [{**FULL_RAW, "id": 1}, {**FULL_RAW, "id": 2, "profile_path": None, "biography": "", "birthday": None}]
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    s = summarize(path)
    assert s["people"] == 2 and s["with_photo"] == 1 and s["with_biography"] == 1 and s["with_birthday_pct"] == 50.0
