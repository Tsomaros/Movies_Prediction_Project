"""The header's people search (V1.1): services/people_search.py and GET /people/search on a small database.

A copy of test_people_api's database (HANKS, named "Actor 1", acts in films 1-4 and 8, directs film 9 and writes
films 9 and 10; WRITER writes films 1 and 8 and acts in film 9; CRUZ is "Penélope Cruz") with a few more people:
three Smiths (Screenplay, Writer, Producer), five Toms for the ranking, and DUAL, who acts in and directs the same
two films, against SOLO, who acts in three.
"""

from __future__ import annotations

import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.lookups import Lookups
from backend.app.services.people_search import search_people, usable
from backend.app.settings import API_PREFIX, Settings
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)
from tests.test_people_api import CRUZ, HANKS, person_db  # noqa: F401 (fixture: the person pages' database)

ANN, BOB, CY = 8001, 8002, 8003
TOM_MANY, TOM_POPULAR, TOM_ALPHA, TOM_BETA, TOM_OBSCURE = 8101, 8102, 8103, 8104, 8105
DUAL, SOLO = 8201, 8202
SEARCH = f"{API_PREFIX}/people/search"


@pytest.fixture(scope="module")
def search_db(person_db, tmp_path_factory):
    path = tmp_path_factory.mktemp("search") / "movies.db"
    shutil.copyfile(person_db, path)
    with sqlite3.connect(path) as c:
        c.executemany("INSERT INTO people (id, name) VALUES (?, ?)", [
            (ANN, "Ann Smith"), (BOB, "Bob Smith"), (CY, "Cy Smith"), (TOM_MANY, "Tom Many Films"),
            (TOM_POPULAR, "Tom Popular"), (TOM_ALPHA, "Tom Alpha"), (TOM_BETA, "Tom Beta"),
            (TOM_OBSCURE, "Tom Obscure"), (DUAL, "Dual Person"), (SOLO, "Solo Person")])
        c.executemany("INSERT INTO movie_crew (movie_id, person_id, job) VALUES (?, ?, ?)", [
            (11, ANN, "Screenplay"), (12, BOB, "Writer"), (13, CY, "Producer"), (20, DUAL, "Director"),
            (21, DUAL, "Director")])
        c.executemany("INSERT INTO movie_cast (movie_id, person_id, character, ord) VALUES (?, ?, 'X', 9)", [
            (30, TOM_MANY), (31, TOM_MANY), (32, TOM_MANY), (33, TOM_POPULAR), (34, TOM_ALPHA), (35, TOM_BETA),
            (36, TOM_OBSCURE), (20, DUAL), (21, DUAL), (21, SOLO), (22, SOLO), (23, SOLO)])
        c.executemany("INSERT INTO person_details (person_id, tmdb_popularity, fetched_at) VALUES (?, ?, '2026-10-25')",
                      [(TOM_POPULAR, 90.0), (TOM_OBSCURE, None)])
    c.close()
    return path


@pytest.fixture(scope="module")
def con(search_db):
    out = sqlite3.connect(f"file:{search_db}?mode=ro", uri=True)
    out.row_factory = sqlite3.Row
    yield out
    out.close()


@pytest.fixture(scope="module")
def lookups(con):
    return Lookups.from_db(con)


def names(lookups, con, q, role="all", **kw):
    return [p["name"] for p in search_people(lookups, con, q, role, **kw)["results"]]


def test_writers_come_from_both_jobs_and_other_crew_jobs_are_left_out(lookups, con):
    assert names(lookups, con, "smith", "writer") == ["Ann Smith", "Bob Smith"]
    out = search_people(lookups, con, "smith")
    assert out["total"] == 2 and out["role_counts"] == {"all": 2, "actor": 0, "director": 0, "writer": 2}


def test_all_counts_distinct_films_so_acting_and_directing_one_film_counts_once(lookups, con):
    assert names(lookups, con, "person") == ["Solo Person", "Dual Person"]  # 3 films against 2 (not 4)
    assert names(lookups, con, "person", "director") == ["Dual Person"]


def test_ranking_is_films_then_popularity_then_name(lookups, con):
    assert names(lookups, con, "tom", "actor") == ["Tom Many Films", "Tom Popular", "Tom Alpha", "Tom Beta",
                                                   "Tom Obscure"]


def test_a_result_has_its_roles_most_films_first_photo_and_known_for(lookups, con):
    hit = search_people(lookups, con, "actor 1")["results"][0]
    assert hit["id"] == HANKS and hit["profile_path"] == "/hanks.jpg"
    assert hit["roles"] == [{"role": "actor", "n_films": 5}, {"role": "writer", "n_films": 2},
                            {"role": "director", "n_films": 1}]
    film8 = con.execute("SELECT title, year FROM movies WHERE id = 8").fetchone()
    assert hit["known_for"] == {"movie_id": 8, "title": film8["title"], "year": film8["year"]}  # the most-voted


def test_counts_per_role_and_paging(lookups, con):
    out = search_people(lookups, con, "tom", "actor", page=1, page_size=2)
    assert out["total"] == 5 and len(out["results"]) == 2
    assert out["role_counts"] == {"all": 5, "actor": 5, "director": 0, "writer": 0}
    assert names(lookups, con, "tom", "actor", page=3, page_size=2) == ["Tom Obscure"]
    assert search_people(lookups, con, "tom", "actor", page=9, page_size=2)["results"] == []


def test_every_page_together_is_the_whole_ranking_once(lookups, con):
    whole = search_people(lookups, con, "actor", page_size=48)
    pages = [p["id"] for page in range(1, 10) for p in search_people(lookups, con, "actor", page=page,
                                                                       page_size=7)["results"]]
    assert len(pages) == len(set(pages)) == min(whole["total"], 63)
    assert pages[:48] == [p["id"] for p in whole["results"]]


@pytest.mark.parametrize("q", ['"', "*", "-", "(", "NEAR(", "a", "   ", "'; DROP", "é"])
def test_an_unsearchable_query_finds_nobody(lookups, con, q):
    out = search_people(lookups, con, q)
    assert out["total"] == 0 and out["results"] == [] and set(out["role_counts"].values()) == {0}


def test_accents_are_folded_and_the_query_runs_on_into_later_words(lookups, con):
    assert [p["id"] for p in search_people(lookups, con, "penelope")["results"]] == [CRUZ]
    assert [p["id"] for p in search_people(lookups, con, "PENÉLOPE c")["results"]] == [CRUZ]
    assert names(lookups, con, "tom ma") == ["Tom Many Films"]


def test_a_usable_query_needs_two_letters_or_digits():
    assert usable(" Tom  HA ") == "tom ha" and usable("a") is None and usable("**") is None and usable("7a") == "7a"


# ---------------------------------------------------------------- over HTTP


@pytest.fixture(scope="module")
def client(search_db):
    with TestClient(create_app(Settings(db_path=search_db), predictor=object())) as c:
        yield c


def test_the_search_answers_one_page_with_counts_photos_and_known_for(client):
    r = client.get(SEARCH, params={"q": "actor 1", "page_size": 3})
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    body = r.json()
    assert {k: body[k] for k in ("q", "role", "page", "page_size")} == {"q": "actor 1", "role": "all", "page": 1,
                                                                         "page_size": 3}
    assert body["total"] == body["role_counts"]["all"] > 3 and len(body["results"]) == 3
    hit = body["results"][0]
    assert set(hit) == {"id", "name", "thumb", "roles", "known_for"} and hit["id"] == HANKS
    assert hit["thumb"] == "https://image.tmdb.org/t/p/w185/hanks.jpg" and hit["known_for"]["movie_id"] == 8
    assert body["results"][1]["thumb"] is None
    assert client.get(SEARCH, params={"q": "smith", "role": "writer"}).json()["total"] == 2


def test_search_is_not_taken_for_a_person_id_and_the_other_people_endpoints_still_work(client):
    assert client.get(SEARCH, params={"q": "tom"}).status_code == 200
    assert client.get(f"{API_PREFIX}/people/{HANKS}").json()["id"] == HANKS
    assert client.get(f"{API_PREFIX}/people", params={"role": "actor", "q": "tom"}).status_code == 200


@pytest.mark.parametrize("params,field", [({}, "q"), ({"q": "tom", "role": "producer"}, "role"),
                                          ({"q": "tom", "page": 0}, "page"), ({"q": "tom", "page_size": 49}, "page_size"),
                                          ({"q": "x" * 101}, "q")])
def test_bad_parameters_are_a_422_in_the_usual_shape(client, params, field):
    r = client.get(SEARCH, params=params)
    assert r.status_code == 422 and set(r.json()["errors"]) == {field}


def test_a_short_or_syntax_only_query_is_an_empty_200(client):
    for q in ("a", '"*', "NEAR("):
        body = client.get(SEARCH, params={"q": q}).json()
        assert body["total"] == 0 and body["results"] == [] and set(body["role_counts"].values()) == {0}
