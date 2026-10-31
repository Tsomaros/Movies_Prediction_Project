"""The demo account (Day 14): auth, lists, ratings, notes, caps, limits and the nightly reset, over HTTP,
plus the logged-in side of "Surprise me" (Day 14.5).

Needs Postgres at TEST_DATABASE_URL (default: the compose db on :5432, `make test-pg`); skipped without it.
The module gets a throwaway database (created, migrated, dropped at the end) and every test starts from
emptied tables with the demo user and SEED loaded, plus a second user. Films come from the small `db`
fixture (ids 1-300), and the clock is frozen at NOW unless a test moves it.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from backend.app.deps import COOKIE, connect_read_only
from backend.app.main import create_app
from backend.app.services.auth import hash_password
from backend.app.services.ratelimit import RateLimiter
from backend.app.settings import API_PREFIX, Settings
from backend.app.userdb import repo
from backend.app.userdb.migrate import migrate
from backend.app.userdb.seed import check_ids, load_seed, reset_if_due, seed
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)

pytestmark = pytest.mark.pg

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://movies:movies@localhost:5432/movies")
AUTH, ME = f"{API_PREFIX}/auth", f"{API_PREFIX}/me"
SEED = {"username": "demo",
        "watched": [{"movie_id": 1, "watched_on": "2026-01-02", "rating": 8},
                    {"movie_id": 2, "watched_on": None, "rating": None}],
        "plan_to_watch": [3, 4],
        "notes": [{"movie_id": 1, "body": "Newest seed note"}, {"movie_id": 5, "body": "Older seed note"}]}
PASSWORD, OTHER_PASSWORD = "demo-pass", "other-pass"
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)  # Athens is UTC+3 until 25 October 2026
ATHENS_MIDNIGHT = datetime(2026, 10, 24, 21, 0, tzinfo=timezone.utc)  # 25 October 00:00 in Athens


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture(scope="module")
def pg_url():
    try:
        admin = psycopg.connect(TEST_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("no Postgres at TEST_DATABASE_URL (start it with make test-pg)")
    name = f"accounts_test_{os.getpid()}"
    admin.execute(f"DROP DATABASE IF EXISTS {name}")
    admin.execute(f"CREATE DATABASE {name}")
    url = make_conninfo(TEST_URL, dbname=name)
    with psycopg.connect(url, autocommit=True) as conn:
        assert migrate(conn) == ["001_init.sql"] and migrate(conn) == []  # each file once
    yield url
    admin.execute(f"DROP DATABASE {name} WITH (FORCE)")
    admin.close()


@pytest.fixture
def pg(pg_url, db):
    """A connection to the emptied test database, with the demo user (SEED) and a second user."""
    with psycopg.connect(pg_url, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("TRUNCATE users, user_movies, comments, sessions, app_state RESTART IDENTITY CASCADE")
        with closing(connect_read_only(db / "movies.db")) as con:
            conn.demo_id = seed(conn, con, PASSWORD, SEED, date(2026, 10, 24))
        conn.other_id = repo.upsert_user(conn, "other", hash_password(OTHER_PASSWORD), is_demo=False)
        yield conn


def make_client(db, pg_url, base_url="http://testserver"):
    app = create_app(Settings(db_path=db / "movies.db", user_database_url=pg_url), predictor=object())
    client = TestClient(app, base_url=base_url, headers={"Origin": base_url})
    client.clock = Clock(NOW)
    app.state.clock = client.clock
    return client


@pytest.fixture
def acct(db, pg_url, pg):
    with make_client(db, pg_url) as c:
        c.app.state.demo_seed = SEED
        c.pg = pg
        yield c


def demo(c):
    r = c.post(f"{AUTH}/demo")
    assert r.status_code == 200, r.text
    return r.json()["user"]


def put(c, movie_id, **body):
    return c.put(f"{ME}/movies/{movie_id}", json=body)


def entries(pg, user_id):
    return {r["movie_id"]: (r["status"], r["watched_on"], r["rating"]) for r in repo.entries(pg, user_id)}


# ---------------------------------------------------------------- auth


ME_ROUTES = [("GET", "/movies"), ("GET", "/movies/status?ids=1"), ("PUT", "/movies/1"), ("DELETE", "/movies/1"),
             ("GET", "/movies/1/notes"), ("POST", "/movies/1/notes"), ("GET", "/notes"), ("PATCH", "/notes/1"),
             ("DELETE", "/notes/1")]


@pytest.mark.parametrize("method,path", ME_ROUTES)
def test_every_me_route_is_a_401_when_logged_out(acct, method, path):
    body = {"PUT": {"status": "watched"}, "POST": {"body": "x"}, "PATCH": {"body": "x"}}.get(method)
    r = acct.request(method, f"{ME}{path}", json=body)
    assert r.status_code == 401 and r.json() == {"detail": "Please log in first"}


def test_me_is_quiet_when_logged_out_and_names_the_user_after_a_demo_login(acct):
    r = acct.get(f"{AUTH}/me")
    assert r.status_code == 200 and r.json() == {"user": None}
    assert r.headers["cache-control"] == "private, no-store"
    user = demo(acct)
    assert user == {"id": acct.pg.demo_id, "username": "demo", "is_demo": True}
    assert acct.get(f"{AUTH}/me").json()["user"] == user


def test_password_login_works_and_any_wrong_detail_gets_the_same_answer(acct):
    for username, password in [("other", "wrong"), ("nobody", OTHER_PASSWORD), ("demo", OTHER_PASSWORD)]:
        r = acct.post(f"{AUTH}/login", json={"username": username, "password": password})
        assert r.status_code == 401 and r.json() == {"detail": "Wrong username or password"}
        assert COOKIE not in r.cookies
    r = acct.post(f"{AUTH}/login", json={"username": " Other ", "password": OTHER_PASSWORD})  # trimmed, any case
    assert r.status_code == 200 and r.json()["user"]["username"] == "other"
    assert acct.post(f"{AUTH}/login", json={"username": "demo", "password": PASSWORD}).json()["user"]["is_demo"]


def test_the_6th_password_login_in_a_minute_is_a_429(acct):
    for _ in range(5):
        assert acct.post(f"{AUTH}/login", json={"username": "other", "password": "wrong"}).status_code == 401
    r = acct.post(f"{AUTH}/login", json={"username": "other", "password": OTHER_PASSWORD})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "login attempts" in r.json()["detail"]
    assert acct.post(f"{AUTH}/demo").status_code == 200  # the demo button has its own limit (10 a minute)


def test_the_11th_demo_login_in_a_minute_is_a_429(acct):
    for _ in range(10):
        demo(acct)
    assert acct.post(f"{AUTH}/demo").status_code == 429


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_the_cookie_is_httponly_lax_site_wide_for_7_days_and_secure_on_https(db, pg_url, pg, scheme):
    with make_client(db, pg_url, base_url=f"{scheme}://testserver") as c:
        cookie = c.post(f"{AUTH}/demo").headers["set-cookie"]
    parts = {p.strip().split("=")[0].lower(): p.strip() for p in cookie.split(";")}
    assert parts[COOKIE].startswith(f"{COOKIE}=") and len(parts[COOKIE]) > len(COOKIE) + 40
    assert "httponly" in parts and parts["samesite"].lower() == "samesite=lax" and parts["path"] == "Path=/"
    assert parts["max-age"] == f"Max-Age={7 * 24 * 3600}"
    assert ("secure" in parts) == (scheme == "https")


def test_only_the_tokens_hash_is_stored(acct):
    demo(acct)
    token = acct.cookies[COOKIE]
    stored = acct.pg.execute("SELECT token_hash FROM sessions").fetchone()["token_hash"]
    assert len(stored) == 32 and token.encode() not in bytes(stored)


def test_an_old_cookie_gets_a_401_after_logout(acct):
    demo(acct)
    token = acct.cookies[COOKIE]
    r = acct.post(f"{AUTH}/logout")
    assert r.status_code == 204 and COOKIE not in acct.cookies
    acct.cookies.set(COOKIE, token)
    assert acct.get(f"{ME}/movies").status_code == 401 and acct.get(f"{AUTH}/me").json() == {"user": None}


def test_an_expired_session_is_refused(acct):
    demo(acct)
    acct.clock.now = NOW + timedelta(days=7, seconds=-1)
    assert acct.get(f"{ME}/movies").status_code == 200
    acct.clock.now = NOW + timedelta(days=7)
    assert acct.get(f"{ME}/movies").status_code == 401


def test_a_write_from_another_site_or_without_json_is_refused(acct):
    demo(acct)
    for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}):
        r = acct.put(f"{ME}/movies/7", json={"status": "watched"}, headers=headers)
        assert r.status_code == 403
    r = acct.put(f"{ME}/movies/7", content='{"status": "watched"}', headers={"Content-Type": "text/plain"})
    assert r.status_code == 415
    no_origin = TestClient(acct.app, cookies=acct.cookies)  # same session, no Origin header at all
    assert no_origin.post(f"{AUTH}/logout").status_code == 403
    assert repo.entry(acct.pg, acct.pg.demo_id, 7) is None
    assert acct.get(f"{ME}/movies", headers={"Origin": "https://evil.example"}).status_code == 200  # reads are fine
    allowed = acct.put(f"{ME}/movies/7", json={"status": "watched"}, headers={"Origin": "http://localhost:5173"})
    assert allowed.status_code == 200  # a CORS_ORIGINS origin (the Vite dev server)


def test_accounts_off_answer_503_and_the_rest_still_works(db):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object())) as c:
        assert c.get(f"{AUTH}/me").status_code == 503 and c.post(f"{AUTH}/demo", headers={"Origin": "http://testserver"}).status_code == 503
        assert c.get(f"{API_PREFIX}/movies").status_code == 200


# ---------------------------------------------------------------- lists


def test_create_switch_and_remove_a_film(acct):
    demo(acct)
    r = put(acct, 7, status="watched")
    assert r.status_code == 200 and r.json()["watched_on"] == "2026-10-24" and r.json()["rating"] is None
    assert r.headers["cache-control"] == "private, no-store"
    r = put(acct, 7, status="watched", watched_on="2026-05-01", rating=8)
    assert (r.json()["watched_on"], r.json()["rating"]) == ("2026-05-01", 8)
    r = put(acct, 7, status="plan_to_watch", watched_on="2026-05-01", rating=8)  # the watchlist drops both
    assert r.json()["status"] == "plan_to_watch" and r.json()["watched_on"] is None and r.json()["rating"] is None
    acct.post(f"{ME}/movies/7/notes", json={"body": "keep me"})
    assert acct.delete(f"{ME}/movies/7").status_code == 204
    assert repo.entry(acct.pg, acct.pg.demo_id, 7) is None
    assert [n["body"] for n in acct.get(f"{ME}/movies/7/notes").json()["items"]] == ["keep me"]  # notes stay
    assert acct.delete(f"{ME}/movies/7").status_code == 204  # removing twice is fine


def test_a_field_left_out_keeps_its_value_and_a_null_rating_clears_it(acct):
    demo(acct)
    put(acct, 7, status="watched", watched_on="2026-05-01")
    assert put(acct, 7, status="watched", rating=9).json()["watched_on"] == "2026-05-01"
    assert put(acct, 7, status="watched").json()["rating"] == 9  # "Watched" clicked again: the rating stays
    assert put(acct, 7, status="watched", rating=None).json()["rating"] is None


@pytest.mark.parametrize("body,field", [({"status": "watched", "rating": 11}, "rating"),
                                        ({"status": "watched", "rating": 0}, "rating"),
                                        ({"status": "seen"}, "status"),
                                        ({"status": "watched", "watched_on": "2026-12-01"}, "watched_on"),
                                        ({"status": "watched", "extra": 1}, "extra")])
def test_bad_list_bodies_are_422s_by_field(acct, body, field):
    demo(acct)
    r = put(acct, 7, **body)
    assert r.status_code == 422 and field in r.json()["errors"], r.json()


def test_the_database_rejects_a_rating_or_date_on_a_watchlist_film(acct):
    for column, value in [("rating", 7), ("watched_on", date(2026, 1, 1))]:
        with pytest.raises(psycopg.errors.CheckViolation):
            acct.pg.execute(f"INSERT INTO user_movies (user_id, movie_id, status, {column}) "
                            "VALUES (%s, 9, 'plan_to_watch', %s)", (acct.pg.demo_id, value))
    with pytest.raises(psycopg.errors.CheckViolation):
        acct.pg.execute("INSERT INTO user_movies (user_id, movie_id, status, rating) VALUES (%s, 9, 'watched', 11)",
                        (acct.pg.demo_id,))
    with pytest.raises(psycopg.errors.UniqueViolation):  # one list per film
        acct.pg.execute("INSERT INTO user_movies (user_id, movie_id, status) VALUES (%s, 1, 'plan_to_watch')",
                        (acct.pg.demo_id,))


def test_an_unknown_film_is_a_404(acct):
    demo(acct)
    assert put(acct, 999_999, status="watched").status_code == 404
    assert acct.delete(f"{ME}/movies/999999").status_code == 404
    assert acct.get(f"{ME}/movies/999999/notes").status_code == 404
    assert acct.post(f"{ME}/movies/999999/notes", json={"body": "x"}).status_code == 404


def test_status_answers_for_up_to_48_films_and_refuses_more(acct):
    demo(acct)
    r = acct.get(f"{ME}/movies/status", params={"ids": ",".join(map(str, range(1, 49)))})
    assert r.status_code == 200
    assert [(e["movie_id"], e["status"], e["rating"]) for e in r.json()["items"]] == [
        (1, "watched", 8), (2, "watched", None), (3, "plan_to_watch", None), (4, "plan_to_watch", None)]
    too_many = acct.get(f"{ME}/movies/status", params={"ids": ",".join(map(str, range(1, 50)))})
    assert too_many.status_code == 422 and "48" in too_many.json()["errors"]["ids"]
    assert acct.get(f"{ME}/movies/status", params={"ids": "1,x"}).status_code == 422


def test_my_movies_has_one_tab_a_page_at_a_time_with_every_count(acct):
    demo(acct)
    for movie_id, rating in [(10, 3), (11, 9), (12, None)]:
        put(acct, movie_id, status="watched", rating=rating, watched_on=f"2026-0{movie_id - 9}-01")
    r = acct.get(f"{ME}/movies")
    body = r.json()
    assert r.headers["cache-control"] == "private, no-store"
    assert body["counts"] == {"watched": 5, "plan_to_watch": 2, "notes": 2} and body["total"] == 5
    assert [i["movie"]["id"] for i in body["items"]] == [12, 11, 10, 1, 2]  # newest added first
    assert set(body["items"][0]["movie"]) >= {"title", "year", "poster", "score", "genres"}  # the /movies card
    by = lambda sort: [i["movie"]["id"] for i in acct.get(f"{ME}/movies", params={"sort": sort}).json()["items"]]
    assert by("rating") == [11, 1, 10, 12, 2]
    assert by("watched") == [12, 11, 1, 10, 2]  # 1 March, 1 February, 2 January, 1 January, no date
    titles = [i["movie"]["title"] for i in acct.get(f"{ME}/movies", params={"sort": "title"}).json()["items"]]
    assert titles == sorted(titles, key=str.casefold)
    plan = acct.get(f"{ME}/movies", params={"status": "plan_to_watch"}).json()
    assert [i["movie"]["id"] for i in plan["items"]] == [3, 4] and plan["items"][0]["entry"]["status"] == "plan_to_watch"
    for movie_id in range(20, 45):
        repo.set_entry(acct.pg, acct.pg.demo_id, movie_id, "plan_to_watch", None, None)
    page2 = acct.get(f"{ME}/movies", params={"status": "plan_to_watch", "page": 2}).json()
    assert page2["total"] == 27 and page2["pages"] == 2 and len(page2["items"]) == 3
    assert acct.get(f"{ME}/movies", params={"sort": "popularity"}).status_code == 422


def test_lists_and_notes_are_private(acct):
    acct.post(f"{AUTH}/login", json={"username": "other", "password": OTHER_PASSWORD})
    body = acct.get(f"{ME}/movies").json()
    assert body["items"] == [] and body["counts"] == {"watched": 0, "plan_to_watch": 0, "notes": 0}
    assert acct.get(f"{ME}/movies/status", params={"ids": "1,2,3"}).json()["items"] == []
    assert acct.get(f"{ME}/notes").json()["items"] == []


# ---------------------------------------------------------------- notes


def test_notes_add_edit_delete_newest_first(acct):
    demo(acct)
    first = acct.post(f"{ME}/movies/1/notes", json={"body": "  second thoughts  "})
    assert first.status_code == 201 and first.json()["body"] == "second thoughts"  # trimmed
    newest = acct.post(f"{ME}/movies/1/notes", json={"body": "third"}).json()
    assert [n["body"] for n in acct.get(f"{ME}/movies/1/notes").json()["items"]] == ["third", "second thoughts",
                                                                                      "Newest seed note"]
    edited = acct.patch(f"{ME}/notes/{newest['id']}", json={"body": "third, edited"})
    assert edited.status_code == 200 and edited.json()["body"] == "third, edited"
    assert edited.json()["updated_at"] >= edited.json()["created_at"]
    assert acct.delete(f"{ME}/notes/{newest['id']}").status_code == 204
    assert acct.delete(f"{ME}/notes/{newest['id']}").status_code == 404
    assert acct.get(f"{ME}/movies/9/notes").json() == {"items": []}  # a film in no list can have notes
    assert acct.post(f"{ME}/movies/9/notes", json={"body": "unlisted"}).status_code == 201


def test_someone_elses_note_is_a_404(acct):
    demo(acct)
    mine = acct.post(f"{ME}/movies/1/notes", json={"body": "the demo's"}).json()
    acct.post(f"{AUTH}/logout")
    acct.post(f"{AUTH}/login", json={"username": "other", "password": OTHER_PASSWORD})
    for r in (acct.patch(f"{ME}/notes/{mine['id']}", json={"body": "mine now"}), acct.delete(f"{ME}/notes/{mine['id']}")):
        assert r.status_code == 404 and r.json() == {"detail": "No such note"}
    assert acct.patch(f"{ME}/notes/987654", json={"body": "x"}).json() == {"detail": "No such note"}  # same answer
    assert repo.notes_for(acct.pg, acct.pg.demo_id, 1)[0]["body"] == "the demo's"


def test_a_note_is_1_to_2000_characters(acct):
    demo(acct)
    assert acct.post(f"{ME}/movies/1/notes", json={"body": "x" * 2000}).status_code == 201
    for body in ("x" * 2001, "   ", ""):
        r = acct.post(f"{ME}/movies/1/notes", json={"body": body})
        assert r.status_code == 422 and list(r.json()["errors"]) == ["body"]
    with pytest.raises(psycopg.errors.CheckViolation):  # the database checks it too
        repo.add_note(acct.pg, acct.pg.demo_id, 1, "x" * 2001)


def test_the_notes_tab_pages_every_note_with_its_film(acct):
    demo(acct)
    for i in range(25):
        repo.add_note(acct.pg, acct.pg.demo_id, 6 + i % 3, f"note {i}")
    first = acct.get(f"{ME}/notes").json()
    assert first["total"] == 27 and first["pages"] == 2 and len(first["items"]) == 24
    assert first["counts"]["notes"] == 27 and first["items"][0]["movie"]["id"] in (6, 7, 8)
    last = acct.get(f"{ME}/notes", params={"page": 2}).json()["items"]
    assert [n["body"] for n in last] == ["note 0", "Newest seed note", "Older seed note"]
    assert last[1]["movie"]["id"] == 1


# ---------------------------------------------------------------- "Surprise me" (Day 14.5)


def spins(c, **params):
    """Every film GET /random gives with Spin again until nothing is left, and the final reason."""
    c.app.state.limiters["random"] = c.app.state.limiters["read"] = RateLimiter(10_000)
    shown = []
    while True:
        r = c.get(f"{API_PREFIX}/random", params={**params, "exclude": ",".join(map(str, shown))})
        assert r.status_code == 200, r.text
        if r.json()["movie"] is None:
            return set(shown), r.json()["reason"]
        shown.append(r.json()["movie"]["id"])


def test_surprise_me_never_picks_a_watched_film(acct):
    everything, _ = spins(acct, decade=2020)  # logged out: nothing is left out
    demo(acct)
    for movie_id in (12, 13, 27):  # 2020-22 films above the floor
        assert put(acct, movie_id, status="watched").status_code == 200
    unseen, reason = spins(acct, decade=2020)
    assert unseen == everything - {12, 13, 27} and reason == "all_seen"
    assert spins(acct, decade=2020, source="all")[0] == unseen


def test_surprise_me_from_the_watchlist_has_no_floor_and_keeps_the_filters(acct):
    assert acct.get(f"{API_PREFIX}/random", params={"source": "watchlist"}).status_code == 401
    demo(acct)
    assert put(acct, 5, status="plan_to_watch").status_code == 200  # film 5 scores 5.0: under the floor
    assert spins(acct, source="watchlist") == ({3, 4, 5}, "all_seen")  # the seed's watchlist plus film 5
    assert spins(acct, source="watchlist", genre="Drama") == ({4}, "all_seen")
    assert spins(acct, source="watchlist", decade=2020) == (set(), "no_match")


def test_an_empty_watchlist_says_so(acct):
    demo(acct)
    for movie_id in (3, 4):
        assert put(acct, movie_id, status="watched").status_code == 200
    assert spins(acct, source="watchlist") == (set(), "watchlist_empty")


# ---------------------------------------------------------------- caps and limits


def test_the_501st_list_entry_is_a_409(acct):
    demo(acct)
    acct.pg.execute("INSERT INTO user_movies (user_id, movie_id, status) "
                    "SELECT %s, 100000 + g, 'plan_to_watch' FROM generate_series(1, 496) g", (acct.pg.demo_id,))
    assert repo.count_entries(acct.pg, acct.pg.demo_id) == 500
    r = put(acct, 7, status="watched")
    assert r.status_code == 409 and "500" in r.json()["detail"]
    assert put(acct, 1, status="watched", rating=10).status_code == 200  # changing a listed film still works


def test_the_201st_note_is_a_409(acct):
    demo(acct)
    acct.pg.execute("INSERT INTO comments (user_id, movie_id, body) SELECT %s, 1, 'n' || g FROM generate_series(1, 198) g",
                    (acct.pg.demo_id,))
    r = acct.post(f"{ME}/movies/1/notes", json={"body": "one too many"})
    assert r.status_code == 409 and "200" in r.json()["detail"]


def test_the_31st_write_in_a_minute_is_a_429(acct):
    demo(acct)
    for i in range(30):
        assert put(acct, 10 + i, status="plan_to_watch").status_code == 200
    r = acct.post(f"{ME}/movies/1/notes", json={"body": "x"})  # notes share the write limit
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert acct.get(f"{ME}/movies").status_code == 200  # reads don't count


# ---------------------------------------------------------------- the nightly reset


def test_the_demo_seed_film_ids_all_exist_in_the_movie_database():
    from backend.app.settings import Settings
    path = Settings.from_env().db_path
    if not path.exists():
        pytest.skip("no data/movies.db")
    with closing(connect_read_only(path)) as con:
        check_ids(con, load_seed())


def test_the_seed_refuses_films_missing_from_the_movie_database(db):
    with closing(connect_read_only(db / "movies.db")) as con, pytest.raises(ValueError, match="999999"):
        check_ids(con, {**SEED, "plan_to_watch": [3, 999_999]})


def test_the_reset_runs_once_at_midnight_athens_time_and_restores_the_seed_exactly(acct):
    seeded = entries(acct.pg, acct.pg.demo_id)
    assert seeded == {1: ("watched", date(2026, 1, 2), 8), 2: ("watched", None, None), 3: ("plan_to_watch", None, None),
                      4: ("plan_to_watch", None, None)}
    demo(acct)
    put(acct, 1, status="plan_to_watch")
    put(acct, 9, status="watched", rating=5)
    acct.post(f"{ME}/movies/9/notes", json={"body": "a visitor's note"})
    changed = entries(acct.pg, acct.pg.demo_id)
    acct.pg.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ('\\x01', %s, %s)",
                    (acct.pg.demo_id, NOW - timedelta(days=1)))  # an expired session, deleted by the reset

    acct.clock.now = ATHENS_MIDNIGHT - timedelta(seconds=1)  # 23:59:59 in Athens: same day, no reset
    demo(acct)
    assert entries(acct.pg, acct.pg.demo_id) == changed
    acct.clock.now = ATHENS_MIDNIGHT + timedelta(seconds=1)  # 00:00:01: the first demo login resets
    demo(acct)
    assert entries(acct.pg, acct.pg.demo_id) == seeded
    notes = [(n["movie_id"], n["body"]) for n in repo.notes_page(acct.pg, acct.pg.demo_id, 50, 0)[0]]
    assert notes == [(n["movie_id"], n["body"]) for n in SEED["notes"]]  # same order, newest first
    assert repo.get_state(acct.pg, "last_reset") == "2026-10-25"
    assert acct.pg.execute("SELECT count(*) AS n FROM sessions WHERE token_hash = '\\x01'").fetchone()["n"] == 0
    put(acct, 2, status="plan_to_watch")
    demo(acct)  # later the same day: the visitor's change stays
    assert entries(acct.pg, acct.pg.demo_id)[2] == ("plan_to_watch", None, None)
    assert acct.get(f"{AUTH}/me").json()["user"]["is_demo"]  # the session made at the reset works


def test_two_demo_logins_at_once_reset_only_once(pg_url, pg):
    repo.set_state(pg, "last_reset", "2026-10-23")

    def login(_):
        with psycopg.connect(pg_url, autocommit=True, row_factory=dict_row) as conn:
            return reset_if_due(conn, pg.demo_id, SEED, date(2026, 10, 24), NOW)

    with ThreadPoolExecutor(4) as pool:
        assert sorted(pool.map(login, range(4))) == [False, False, False, True]
    assert repo.get_state(pg, "last_reset") == "2026-10-24"


def test_listed_movie_ids_come_from_every_users_lists_and_notes(pg):
    base = repo.listed_movie_ids(pg)  # the demo seed's films
    repo.set_entry(pg, pg.other_id, 900_001, "plan_to_watch", None, None)
    repo.add_note(pg, pg.demo_id, 900_002, "a note on a film not in a list")
    assert repo.listed_movie_ids(pg) == base | {900_001, 900_002}


def test_a_watchlisted_new_film_is_in_my_movies_and_hidden_without_it(db, pg_url, pg, tmp_path):
    import shutil

    from backend.app.services.fresh import merge_into, open_for_writing
    from tests.factories import TEST_CPI, film

    merged = tmp_path / "movies.db"
    shutil.copyfile(db / "movies.db", merged)
    with closing(open_for_writing(merged)) as con:
        merge_into(con, [film(900_001, title="Just Out", release_date="2026-10-25")], TEST_CPI, "2026-10-30T10:00:00+00:00")

    def client(path):
        app = create_app(Settings(db_path=path, user_database_url=pg_url), predictor=object())
        c = TestClient(app, base_url="http://testserver", headers={"Origin": "http://testserver"})
        c.clock = Clock(NOW)
        app.state.clock = c.clock
        app.state.demo_seed = SEED
        return c

    with client(merged) as c:
        demo(c)
        assert put(c, 900_001, status="plan_to_watch").status_code == 200
        titles = [m["movie"]["title"] for m in c.get(f"{ME}/movies?status=plan_to_watch").json()["items"]]
        assert "Just Out" in titles
    with client(db / "movies.db") as c:  # the build without it (a restart): the entry stays, the film is hidden
        demo(c)
        titles = [m["movie"]["title"] for m in c.get(f"{ME}/movies?status=plan_to_watch").json()["items"]]
        assert "Just Out" not in titles and repo.entry(pg, pg.demo_id, 900_001) is not None
