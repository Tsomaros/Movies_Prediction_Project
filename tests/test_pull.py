"""Offline tests for the pull script, using a fake TMDB (httpx.MockTransport)."""

import csv
import json

import httpx

from ml.data.pull import (
    load_discover_ids,
    repair_jsonl,
    run_details,
    run_discover,
    trim_movie,
    us_certification,
)
from ml.data.tmdb_client import TMDBClient


def raw_movie(movie_id: int) -> dict:
    """A /movie/{id} response with credits, keywords and release_dates appended."""
    return {
        "id": movie_id,
        "imdb_id": "tt0000001",
        "title": f"Film {movie_id}",
        "original_title": f"Film {movie_id}",
        "original_language": "en",
        "release_date": "2019-07-12",
        "status": "Released",
        "runtime": 118,
        "genres": [{"id": 28, "name": "Action"}],
        "overview": "A heist goes wrong.",
        "tagline": "",
        "budget": 50_000_000,
        "revenue": 180_000_000,
        "poster_path": "/abc.jpg",
        "backdrop_path": "/backdrop.jpg",
        "popularity": 12.3,
        "vote_count": 2500,
        "vote_average": 6.8,
        "belongs_to_collection": {"id": 10, "name": "Film Collection", "poster_path": "/c.jpg"},
        "production_companies": [{"id": 1, "name": "Studio", "origin_country": "US", "logo_path": "/l.png"}],
        "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
        "spoken_languages": [{"iso_639_1": "en", "english_name": "English", "name": "English"}],
        "keywords": {"keywords": [{"id": 5, "name": "heist"}]},
        "release_dates": {
            "results": [
                {"iso_3166_1": "GB", "release_dates": [{"certification": "15", "type": 3}]},
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"certification": "", "type": 1},
                        {"certification": "NR", "type": 4},
                        {"certification": "PG-13", "type": 3},
                    ],
                },
            ]
        },
        "credits": {
            # 20 cast members, deliberately out of order
            "cast": [
                {"id": 100 + i, "name": f"Actor {i}", "character": f"Role {i}", "order": i, "profile_path": "/p.jpg"}
                for i in reversed(range(20))
            ],
            "crew": [
                {"id": 1, "name": "Dir", "job": "Director", "department": "Directing"},
                {"id": 2, "name": "Wri", "job": "Screenplay", "department": "Writing"},
                {"id": 3, "name": "Pro", "job": "Producer", "department": "Production"},
                {"id": 4, "name": "Com", "job": "Original Music Composer", "department": "Sound"},
                {"id": 5, "name": "Cin", "job": "Director of Photography", "department": "Camera"},
                {"id": 6, "name": "Edi", "job": "Editor", "department": "Editing"},
                {"id": 7, "name": "Grip", "job": "Key Grip", "department": "Camera"},
                {"id": 8, "name": "Cat", "job": "Caterer", "department": "Crew"},
            ],
        },
    }


class FakeTMDB:
    """Routes discover and details requests; counts calls per route."""

    def __init__(self, films_per_year: dict[int, list[int]], missing: set[int] = frozenset(), per_page: int = 20):
        self.films_per_year = films_per_year
        self.missing = missing
        self.per_page = per_page
        self.discover_calls = 0
        self.details_calls: list[int] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/3/discover/movie":
            self.discover_calls += 1
            year = int(request.url.params["primary_release_year"])
            page = int(request.url.params["page"])
            films = self.films_per_year.get(year, [])
            total_pages = max(1, -(-len(films) // self.per_page))
            chunk = films[(page - 1) * self.per_page : page * self.per_page]
            return httpx.Response(200, json={"page": page, "total_pages": total_pages, "results": [{"id": i} for i in chunk]})
        if path.startswith("/3/movie/"):
            movie_id = int(path.rsplit("/", 1)[1])
            self.details_calls.append(movie_id)
            if movie_id in self.missing:
                return httpx.Response(404)
            return httpx.Response(200, json=raw_movie(movie_id))
        return httpx.Response(400)


def client_for(fake: FakeTMDB) -> TMDBClient:
    return TMDBClient("test-token", rate=10_000, backoff_base=0, transport=httpx.MockTransport(fake))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------- trimming


def test_trim_keeps_the_right_fields():
    movie = trim_movie(raw_movie(42), pulled_at="2026-10-21T00:00:00+00:00")

    assert movie["id"] == 42
    assert movie["budget"] == 50_000_000 and movie["revenue"] == 180_000_000
    assert movie["poster_path"] == "/abc.jpg"
    assert movie["collection"] == {"id": 10, "name": "Film Collection"}
    assert movie["production_countries"] == ["US"]
    assert movie["spoken_languages"] == ["en"]
    assert movie["keywords"] == [{"id": 5, "name": "heist"}]
    assert movie["us_certification"] == "PG-13"
    assert movie["pulled_at"] == "2026-10-21T00:00:00+00:00"
    # Left out: UI-only images, IMDb id, raw appended blocks
    for dropped in ("imdb_id", "backdrop_path", "credits", "release_dates"):
        assert dropped not in movie
    assert "logo_path" not in movie["production_companies"][0]


def test_trim_keeps_top_15_cast_in_billing_order():
    cast = trim_movie(raw_movie(1))["cast"]
    assert [c["order"] for c in cast] == list(range(15))
    assert set(cast[0]) == {"id", "name", "character", "order"}


def test_trim_keeps_only_key_crew():
    jobs = [c["job"] for c in trim_movie(raw_movie(1))["crew"]]
    assert jobs == ["Director", "Screenplay", "Producer", "Original Music Composer", "Director of Photography", "Editor"]


def test_trim_handles_missing_optional_blocks():
    movie = trim_movie({"id": 7, "belongs_to_collection": None})
    assert movie["collection"] is None
    assert movie["cast"] == [] and movie["crew"] == [] and movie["keywords"] == []
    assert movie["us_certification"] is None


def test_us_certification_falls_back_to_any_release():
    dates = {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "R", "type": 4}]}]}
    assert us_certification(dates) == "R"
    assert us_certification({"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "", "type": 3}]}]}) is None
    assert us_certification({"results": [{"iso_3166_1": "FR", "release_dates": [{"certification": "U", "type": 3}]}]}) is None


# ---------------------------------------------------------------- discover


async def test_discover_stops_at_total_pages_and_dedupes(tmp_path):
    ids_path = tmp_path / "discover_ids.csv"
    # 2019 has 45 films (3 pages of 20) with one duplicate; 2020 has 5 films
    fake = FakeTMDB({2019: list(range(1, 45)) + [3], 2020: [101, 102, 103, 104, 105]})
    async with client_for(fake) as client:
        added = await run_discover(client, range(2019, 2021), pages=35, ids_path=ids_path)

    assert added == 44 + 5
    assert fake.discover_calls == 3 + 1  # never asks past total_pages
    with ids_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert set(rows[0]) == {"year", "page", "id"}
    assert load_discover_ids(ids_path, range(2020, 2021)) == [101, 102, 103, 104, 105]


async def test_discover_respects_page_cap(tmp_path):
    fake = FakeTMDB({2019: list(range(1, 101))})  # 5 pages available
    async with client_for(fake) as client:
        added = await run_discover(client, range(2019, 2020), pages=2, ids_path=tmp_path / "ids.csv")
    assert added == 40
    assert fake.discover_calls == 2


async def test_discover_resume_skips_finished_years(tmp_path):
    ids_path = tmp_path / "discover_ids.csv"
    fake = FakeTMDB({2019: [1, 2], 2020: [3, 4]})
    async with client_for(fake) as client:
        await run_discover(client, range(2019, 2020), pages=35, ids_path=ids_path)
        fake.discover_calls = 0
        await run_discover(client, range(2019, 2021), pages=35, ids_path=ids_path)

    assert fake.discover_calls == 1  # only 2020
    assert load_discover_ids(ids_path, range(2019, 2021)) == [1, 2, 3, 4]


# ---------------------------------------------------------------- details


async def test_details_writes_one_line_per_film(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"
    fake = FakeTMDB({})
    async with client_for(fake) as client:
        stats = await run_details(client, [1, 2, 3], movies, missing)

    assert stats == {"saved": 3, "missing": 0, "failed": 0}
    assert sorted(m["id"] for m in read_jsonl(movies)) == [1, 2, 3]
    assert "credits" not in read_jsonl(movies)[0]


async def test_details_resume_skips_saved_ids(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"
    fake = FakeTMDB({})
    async with client_for(fake) as client:
        await run_details(client, [1, 2, 3], movies, missing)
        fake.details_calls.clear()
        stats = await run_details(client, [1, 2, 3, 4], movies, missing)

    assert fake.details_calls == [4]
    assert stats["saved"] == 1
    assert len(read_jsonl(movies)) == 4


async def test_details_skips_and_records_404s(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"
    fake = FakeTMDB({}, missing={2})
    async with client_for(fake) as client:
        stats = await run_details(client, [1, 2, 3], movies, missing)
        fake.details_calls.clear()
        rerun = await run_details(client, [1, 2, 3], movies, missing)

    assert stats == {"saved": 2, "missing": 1, "failed": 0}
    assert sorted(m["id"] for m in read_jsonl(movies)) == [1, 3]
    assert missing.read_text().split() == ["2"]
    assert fake.details_calls == []  # nothing left to do on the rerun
    assert rerun == {"saved": 0, "missing": 0, "failed": 0}


async def test_details_limit(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"
    fake = FakeTMDB({})
    async with client_for(fake) as client:
        stats = await run_details(client, list(range(1, 51)), movies, missing, limit=20)
    assert stats["saved"] == 20
    assert len(fake.details_calls) == 20


async def test_details_failure_is_left_for_next_run(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"

    def always_500(request):
        return httpx.Response(500)

    client = TMDBClient("t", rate=10_000, backoff_base=0, max_retries=2, transport=httpx.MockTransport(always_500))
    async with client:
        stats = await run_details(client, [1], movies, missing)

    assert stats == {"saved": 0, "missing": 0, "failed": 1}
    assert movies.read_text() == "" and missing.read_text() == ""


def test_repair_drops_half_written_last_line(tmp_path):
    path = tmp_path / "movies.jsonl"
    path.write_bytes(b'{"id": 1}\n{"id": 2}\n{"id": 3, "tit')
    repair_jsonl(path)
    assert path.read_bytes() == b'{"id": 1}\n{"id": 2}\n'


async def test_resume_after_interrupted_write(tmp_path):
    movies, missing = tmp_path / "movies.jsonl", tmp_path / "missing.txt"
    movies.write_text(json.dumps({"id": 1}) + "\n" + '{"id": 2, "ti', encoding="utf-8")
    fake = FakeTMDB({})
    async with client_for(fake) as client:
        await run_details(client, [1, 2], movies, missing)

    assert fake.details_calls == [2]
    assert [m["id"] for m in read_jsonl(movies)] == [1, 2]
