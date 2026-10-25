"""The person pages (Day 14.6) over HTTP: GET /people/{id} and the extras on GET /people, on a small database.

A copy of the `db` fixture (films 1-300, actor 2000+i in film i, director 1000 + i % 7) with a few changes:
actor HANKS is also in films 2, 3, 4 and 8 (as "Forrest" in film 8, the most-voted); COSTAR shares films 1 and 2
with him; film 8's director (1001) also directed film 1, so 1001 is his top director; film 4 has too few votes
for the average; film 2's revenue is unknown and film 3's doubted. PLAIN has no TMDB details; CRUZ has an accent.
"""

from __future__ import annotations

import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from ml.data.people import TABLE
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)

HANKS, COSTAR, PLAIN, CRUZ, DIRECTOR = 2001, 2005, 2002, 5000, 1001
PEOPLE = f"{API_PREFIX}/people"


@pytest.fixture(scope="module")
def person_db(db, tmp_path_factory):
    path = tmp_path_factory.mktemp("people") / "movies.db"
    shutil.copyfile(db / "movies.db", path)
    with sqlite3.connect(path) as con:
        con.execute(TABLE)
        con.executemany("INSERT INTO movie_cast (movie_id, person_id, character, ord) VALUES (?, ?, ?, 1)",
                        [(2, HANKS, "Two"), (3, HANKS, "Three"), (4, HANKS, "Four"), (8, HANKS, "Forrest"),
                         (1, COSTAR, "Pal"), (2, COSTAR, "Pal")])
        con.execute("UPDATE movies SET vote_count = 9000 WHERE id = 8")
        con.execute("UPDATE movies SET vote_count = 10, score_ok = 0 WHERE id = 4")
        con.execute("UPDATE movies SET revenue_2025 = NULL WHERE id = 2")
        con.execute("UPDATE movies SET money_suspect = 1 WHERE id = 3")
        con.execute("INSERT INTO people (id, name) VALUES (?, 'Penélope Cruz')", (CRUZ,))
        con.execute("INSERT INTO movie_cast (movie_id, person_id, character, ord) VALUES (6, ?, 'Raimunda', 1)", (CRUZ,))
        con.execute("""INSERT INTO person_details (person_id, profile_path, biography, birthday, place_of_birth,
                       known_for_department, imdb_id, homepage, tmdb_popularity, fetched_at)
                       VALUES (?, '/hanks.jpg', 'Line one.', '1956-07-09', 'Concord', 'Acting', 'nm0000158',
                       'https://example.com', 50, '2026-10-25')""", (HANKS,))
    return path


@pytest.fixture(scope="module")
def client(person_db):
    with TestClient(create_app(Settings(db_path=person_db), predictor=object())) as c:
        yield c


def films(path):
    with sqlite3.connect(path) as con:
        return {r[0]: r[1:] for r in con.execute("SELECT id, year, vote_average, revenue_2025 FROM movies")}


def test_a_person_page_has_details_stats_and_films(client, person_db):
    r = client.get(f"{PEOPLE}/{HANKS}")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    body = r.json()
    assert body["name"] == "Actor 1" and body["photo"]["small"] == "https://image.tmdb.org/t/p/w185/hanks.jpg"
    assert body["photo"]["large"].endswith("/h632/hanks.jpg") and body["biography"] == "Line one."
    assert body["imdb_url"] == "https://www.imdb.com/name/nm0000158/"
    assert body["tmdb_url"] == f"https://www.themoviedb.org/person/{HANKS}"
    years = [f["year"] for f in body["cast_credits"]]
    assert years == sorted(years, reverse=True) and len(years) == 5
    assert next(f for f in body["cast_credits"] if f["id"] == 8)["character"] == "Forrest"
    assert body["crew_credits"] == {}
    f = films(person_db)
    s = body["stats"]
    assert s["film_count"] == 5 and (s["first_year"], s["last_year"]) == (min(years), max(years))
    scored = [f[i][1] for i in (1, 2, 3, 8)]  # film 4 has too few votes
    assert s["avg_score"] == {"value": round(sum(scored) / 4, 1), "films": 4}
    assert s["box_office_2025"] == {"total": f[1][2] + f[4][2] + f[8][2], "films": 3, "of": 5}  # 2 unknown, 3 doubted
    assert s["top_costar"] == {"id": COSTAR, "name": "Actor 5", "shared_films": 2}
    assert s["top_director"] == {"id": DIRECTOR, "name": "Director 1", "shared_films": 2}
    assert [g["name"] for g in s["top_genres"]] and sum(g["films"] for g in s["top_genres"]) == 5


def test_a_person_without_tmdb_details_or_shared_films(client):
    body = client.get(f"{PEOPLE}/{PLAIN}").json()
    assert body["photo"] is None and body["biography"] is None and body["imdb_url"] is None
    assert body["stats"]["top_costar"] is None and body["stats"]["top_director"] is None
    assert body["stats"]["film_count"] == 1


def test_a_director_page_lists_what_they_directed(client):
    body = client.get(f"{PEOPLE}/{DIRECTOR}").json()
    assert body["cast_credits"] == [] and body["stats"]["film_count"] == 0
    assert body["stats"]["avg_score"] is None and body["stats"]["box_office_2025"] is None
    assert body["stats"]["first_year"] is None and len(body["crew_credits"]["Director"]) > 1


@pytest.mark.parametrize("path,status", [("/424242", 404), ("/abc", 422), ("/99999999999999999999", 404),
                                         ("/-1", 404), ("/0", 404)])
def test_bad_person_ids_are_404s_or_422s(client, path, status):
    r = client.get(f"{PEOPLE}{path}")
    assert r.status_code == status
    if status == 404:
        assert r.json() == {"detail": "Person not found"}


def test_search_hits_have_a_thumbnail_and_the_film_they_are_known_for(client, person_db):
    with sqlite3.connect(person_db) as con:
        most_voted = con.execute("SELECT title FROM movies WHERE id = 8").fetchone()[0]
    hits = client.get(PEOPLE, params={"role": "actor", "q": "actor 1"}).json()
    hit = next(h for h in hits if h["id"] == HANKS)
    assert set(hit) == {"id", "name", "n_films", "thumb", "known_for"}
    assert hit["thumb"] == "https://image.tmdb.org/t/p/w185/hanks.jpg" and hit["n_films"] == 5
    assert hit["known_for"] == most_voted
    assert next(h for h in hits if h["id"] != HANKS)["thumb"] is None
    director = client.get(PEOPLE, params={"role": "director", "q": "director 1"}).json()[0]
    assert director["id"] == DIRECTOR and director["known_for"] is not None


def test_search_folds_accents_both_ways(client):
    for q in ("penelope", "penélope", "PENÉ"):
        assert [h["id"] for h in client.get(PEOPLE, params={"role": "actor", "q": q}).json()] == [CRUZ]


@pytest.mark.parametrize("q", ['"', "*", "-", "(", "AND", "NEAR(", "'; DROP TABLE people; --", "%", "_"])
def test_search_text_with_syntax_is_just_text(client, q):
    r = client.get(PEOPLE, params={"role": "actor", "q": q})
    assert r.status_code == 200 and isinstance(r.json(), list)
