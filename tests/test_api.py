"""The FastAPI backend (backend/app), through TestClient. Offline: the app gets an injected Predictor, so the
real models are never loaded."""

import sqlite3

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app.deps import connect_read_only, get_db
from backend.app.main import ROUTERS, create_app
from backend.app.services.lookups import NameIndex
from backend.app.services.prediction import PredictionService, merge
from backend.app.services.ratelimit import RateLimiter
from backend.app.settings import API_PREFIX, Settings
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db with a features table, 2008-2022)
from tests.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                               score_model, score_rows)
from tests.test_predict import form as film_form
from tests.test_predict import predictor  # noqa: F401 (fixture: a small Predictor on the db fixture)

ORIGIN = "http://localhost:5173"


@pytest.fixture
def client(db):
    sentinel = object()  # stands in for a Predictor until the endpoints need a real one
    settings = Settings(db_path=db / "movies.db", cors_origins=(ORIGIN,))
    with TestClient(create_app(settings, predictor=sentinel)) as c:
        c.sentinel = sentinel
        yield c


# ---------------------------------------------------------------- structure


def test_the_injected_predictor_is_used_and_nothing_is_loaded(client):
    assert client.app.state.predictor is client.sentinel


def test_docs_and_the_openapi_schema_are_served(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Movie Prediction API" and "TMDB" in schema["info"]["description"]


def test_every_router_is_mounted_under_the_version_prefix(client):
    paths = [route.path for module in ROUTERS for route in module.router.routes]
    mounted = client.get("/openapi.json").json()["paths"]
    assert all(f"{API_PREFIX}{p}" in mounted for p in paths)
    assert all(p.startswith(f"{API_PREFIX}/") for p in mounted)


def test_cors_allows_the_frontend_origin_only(client):
    ok = client.options(f"{API_PREFIX}/health", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    other = client.options(f"{API_PREFIX}/health",
                           headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in other.headers


def test_settings_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("MOVIES_DB", "x/movies.db")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("RATE_LIMIT", "5")
    s = Settings.from_env()
    assert str(s.db_path).replace("\\", "/") == "x/movies.db"
    assert s.cors_origins == ("http://a.test", "http://b.test") and s.rate_limit == 5 and s.cache_size == 1000


# ---------------------------------------------------------------- startup and database


def test_startup_builds_the_lookups_from_the_settings_database(client):
    lookups = client.app.state.lookups
    assert len(lookups.indexes["director"]) == 7 and len(lookups.indexes["actor"]) == 300  # the fixture's people
    assert lookups.search("director", "director 3")[0]["name"] == "Director 3"
    assert client.app.state.load_seconds >= 0 and client.app.state.started > 0


def test_each_request_gets_a_read_only_connection_that_is_closed_after(client):
    seen = []

    @client.app.get("/_probe")
    def probe(con: sqlite3.Connection = Depends(get_db)):
        seen.append(con)
        films = con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        try:
            con.execute("DELETE FROM movies")
            wrote = True
        except sqlite3.OperationalError as e:
            wrote = str(e)
        return {"films": films, "wrote": wrote}

    first, second = client.get("/_probe").json(), client.get("/_probe").json()
    assert first["films"] == 300 and "readonly" in first["wrote"] and second["films"] == 300
    assert seen[0] is not seen[1]
    with pytest.raises(sqlite3.ProgrammingError):  # closed after its request
        seen[0].execute("SELECT 1")


def test_a_missing_database_is_an_error_not_a_new_empty_file(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        connect_read_only(tmp_path / "nope.db").execute("SELECT 1")
    assert not (tmp_path / "nope.db").exists()


# ---------------------------------------------------------------- the autocomplete index


NAMES = NameIndex.build([(1, "Tom Hanks", 85), (2, "Colin Hanks", 24), (3, "Tom Hardy", 37), (4, "Tomás Milián", 90),
                         (5, "Hank Azaria", 60), (6, "Élodie Bouchez", 20), (7, "tom hanks", 1)])


def ids(found):
    return [f["id"] for f in found]


def test_any_word_can_start_the_match_and_the_query_can_run_on():
    assert ids(NAMES.search("hanks")) == [1, 2, 7]
    assert ids(NAMES.search("tom ha")) == [1, 3, 7]
    assert ids(NAMES.search("tom hanks")) == [1, 7]
    assert ids(NAMES.search("hank")) == [1, 5, 2, 7]  # "Hank Azaria" and every "Hanks"


def test_matching_ignores_case_and_extra_spaces_but_not_accents():
    assert ids(NAMES.search("  TOM   HA ")) == [1, 3, 7]
    assert ids(NAMES.search("élodie")) == [6] and ids(NAMES.search("ÉLO")) == [6]
    assert NAMES.search("elodie") == []  # accents are kept, as TMDB spells the name


def test_most_films_first_and_at_most_the_limit():
    assert ids(NAMES.search("t")) == [4, 1, 3, 7]
    assert ids(NAMES.search("t", limit=2)) == [4, 1]
    assert NAMES.search("t")[0] == {"id": 4, "name": "Tomás Milián", "n_films": 90}


def test_empty_or_unknown_queries_find_nothing():
    assert NAMES.search("") == [] and NAMES.search("   ") == [] and NAMES.search("zzz") == []
    assert NameIndex.build([]).search("a") == []


# ---------------------------------------------------------------- prediction endpoints


PREDICT, COMPARE = f"{API_PREFIX}/predict", f"{API_PREFIX}/predict/compare"


@pytest.fixture
def api(db, predictor):
    """The app with the small Predictor on the fixture database; a fresh cache and rate limit per test."""
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=predictor)) as c:
        yield c


def errors_of(response):
    assert response.status_code == 422 and response.json()["detail"] == "Some fields need fixing"
    return response.json()["errors"]


def test_predict_returns_the_full_output_in_both_revenue_modes(api, predictor):
    given = api.post(PREDICT, json=film_form()).json()
    estimated = api.post(PREDICT, json=film_form(budget=None)).json()
    assert given["revenue"]["mode"] == "given" and estimated["revenue"]["mode"] == "estimated"
    expected = predictor.predict(film_form())
    for key in ("model_version", "as_of", "budget", "revenue", "score", "drivers", "warnings"):
        assert given[key] == expected[key]
    assert [f["id"] for f in given["comparables"]] == [f["id"] for f in expected["comparables"]]
    assert given["cached"] is False and given["score"]["note"]


def test_comparables_get_full_poster_urls(api):
    films = api.post(PREDICT, json=film_form()).json()["comparables"]
    assert films and all(f["poster"] is None or f["poster"]["small"].startswith("https://image.tmdb.org/t/p/w342/")
                         for f in films)


def test_the_same_film_written_two_ways_is_served_from_the_cache(api):
    first = api.post(PREDICT, json=film_form(budget=40_000_000)).json()
    again = api.post(PREDICT, json=film_form(budget=40_000_000.0, companies=["  Some Studio "])).json()
    assert first["cached"] is False and again["cached"] is True
    assert {k: v for k, v in again.items() if k != "cached"} == {k: v for k, v in first.items() if k != "cached"}
    service = api.app.state.predictions
    assert (service.hits, service.misses, len(service)) == (1, 1, 1)


def test_the_cache_drops_the_least_recently_used_form(predictor):
    service = PredictionService(predictor, size=2)
    a, b, c = film_form(runtime=100), film_form(runtime=110), film_form(runtime=120)
    service.predict(a), service.predict(b), service.predict(a), service.predict(c)  # b is the oldest now
    assert service.predict(a)[1] is True and service.predict(b)[1] is False and len(service) == 2


def test_rule_errors_name_every_field_in_one_response(api):
    form = film_form(release_year=2040, genres=["Drama", "Cartoon"], runtime=5)
    del form["themes"]
    assert errors_of(api.post(PREDICT, json=form)) == {
        "genres": "unknown value(s): 'Cartoon'", "release_year": "must be between 1960 and 2035",
        "runtime": "must be between 40 and 300", "themes": "required"}


def test_shape_errors_read_like_rule_errors_and_list_the_rest_too(api):
    form = film_form(runtime="long", director=True, release_year=2040, extra=1)
    assert errors_of(api.post(PREDICT, json=form)) == {
        "runtime": "must be a number", "director": "must be an id or a name",
        "release_year": "must be between 1960 and 2035", "extra": "unknown field"}
    assert errors_of(api.post(PREDICT, json=film_form(release_year="2021")))["release_year"] == "must be a number"
    assert errors_of(api.post(PREDICT, json=film_form(themes=["no such theme"])))["themes"].startswith("unknown value")
    assert "body" in errors_of(api.post(PREDICT, json=[1, 2]))


def test_compare_differences_agree_with_separate_predictions(api):
    base = film_form()
    variants = [{"budget": 80_000_000}, {"budget": None}, {"runtime": 150, "release_month": 12}]
    out = api.post(COMPARE, json={"base": base, "variants": variants}).json()
    single = [api.post(PREDICT, json=merge(base, v)).json() for v in variants]
    base_out = out["base"]
    for variant, alone, changes in zip(out["variants"], single, variants):
        d, p = variant["differences"], variant["prediction"]
        assert p["revenue"] == alone["revenue"] and p["score"] == alone["score"]
        assert sorted(d["changed_fields"]) == sorted(changes)
        assert d["revenue"]["ratio"] == pytest.approx(p["revenue"]["middle"] / base_out["revenue"]["middle"], rel=1e-3)
        assert d["score"]["points"] == pytest.approx(p["score"]["middle"] - base_out["score"]["middle"], abs=1e-3)
        assert d["revenue"]["points"] is None and d["score"]["ratio"] is None
    assert [v["differences"]["mode_changed"] for v in out["variants"]] == [False, True, False]
    assert not any(v["prediction"]["cached"] for v in out["variants"])
    assert all(alone["cached"] for alone in single)  # compare filled the cache for the singles that followed


def test_compare_names_the_variant_and_field_and_needs_1_to_3_variants(api):
    bad = api.post(COMPARE, json={"base": film_form(), "variants": [{"runtime": 5}, {"budget": -1}, {"runtime": "x"}]})
    assert errors_of(bad) == {"variants.0.runtime": "must be between 40 and 300",
                              "variants.1.budget": "must be between 1000 and 1,000,000,000",
                              "variants.2.runtime": "must be a number"}
    assert errors_of(api.post(COMPARE, json={"base": film_form(runtime=1), "variants": [{}]})) == {
        "base.runtime": "must be between 40 and 300", "variants.0.runtime": "must be between 40 and 300"}
    for variants in ([], [{}] * 4):
        assert errors_of(api.post(COMPARE, json={"base": film_form(), "variants": variants})) == {
            "variants": "needs 1 to 3 variants"}
    assert errors_of(api.post(COMPARE, json={"base": film_form(), "variants": [{"nope": 1}]})) == {
        "variants.0.nope": "unknown field"}


def test_the_31st_prediction_in_a_minute_is_refused_politely(api):
    assert api.post(COMPARE, json={"base": film_form(), "variants": [{"runtime": 100}]}).status_code == 200
    assert all(api.post(PREDICT, json=film_form()).status_code == 200 for _ in range(29))
    refused = api.post(PREDICT, json=film_form())
    assert refused.status_code == 429 and "try again in a minute" in refused.json()["detail"]
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    assert api.get("/openapi.json").status_code == 200  # other endpoints are not limited


def test_the_rate_limit_window_slides_and_forgets_idle_clients():
    now = [0.0]
    limiter = RateLimiter(limit=2, window=60, clock=lambda: now[0])
    assert limiter.hit("a") is None and limiter.hit("a") is None and limiter.hit("a") == 60
    assert limiter.hit("b") is None  # each client has its own window
    now[0] = 30.0
    assert limiter.hit("a") == 30
    now[0] = 60.5
    assert limiter.hit("a") is None and limiter.hit("a") is None and limiter.hit("a") is not None
    now[0] = 200.0
    limiter.hit("c")
    assert len(limiter) == 1  # a and b were idle for a whole window


def test_merge_applies_changes_and_null_clears_a_field():
    base = {"runtime": 100, "budget": 5, "genres": ["Drama"]}
    assert merge(base, {"budget": None, "runtime": 120}) == {"runtime": 120, "genres": ["Drama"]}
    assert base == {"runtime": 100, "budget": 5, "genres": ["Drama"]}


def test_the_openapi_schema_documents_the_form_and_the_output(api):
    schema = api.get("/openapi.json").json()
    form = schema["components"]["schemas"]["PredictForm"]
    assert set(form["required"]) == {"genres", "release_year", "release_month", "runtime", "language",
                                     "certification", "director", "actors", "themes"}
    runtime, actors = form["properties"]["runtime"], form["properties"]["actors"]
    assert (runtime["minimum"], runtime["maximum"], actors["minItems"], actors["maxItems"]) == (40, 300, 5, 10)
    assert {"Prediction", "CompareResponse", "Driver", "Comparable"} <= set(schema["components"]["schemas"])
    assert {"422", "429"} <= set(schema["paths"][PREDICT]["post"]["responses"])


def test_the_openapi_schema_shows_the_real_error_bodies_and_field_specs(api):
    """The frontend's types are generated from this schema: every 422 must be our {detail, errors} shape (not
    FastAPI's default, which errors.py never sends), and the options' fields must be typed."""
    schema = api.get("/openapi.json").json()
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    for path, ops in schema["paths"].items():
        for op in ops.values():
            if "422" in op["responses"]:
                ref = op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
                assert ref.endswith("/FieldErrors"), path
    assert schema["components"]["schemas"]["Options"]["properties"]["fields"]["items"]["$ref"].endswith("/FieldSpec")
    assert api.get(f"{API_PREFIX}/meta/options").json()["fields"][1] == {
        "name": "release_year", "kind": "int", "required": True, "help": "Planned release year", "min": 1960, "max": 2035}


def test_the_frontend_test_options_match_the_contract():
    """frontend/src/test/options.json (the /meta/options answer the Vitest form tests run on) must keep the
    contract's fields, genres, certifications and themes; refresh it from the running API when they change."""
    import json
    from pathlib import Path

    from backend.app.routers.meta import build_options
    from ml.features.themes import load_themes

    saved = json.loads(Path("frontend/src/test/options.json").read_text(encoding="utf-8"))
    with sqlite3.connect(":memory:") as con:  # empty tables: the language and country lists aren't compared
        con.execute("CREATE TABLE movies (original_language TEXT)")
        con.execute("CREATE TABLE movie_countries (country TEXT)")
        current = build_options(con, sorted(load_themes()))
    for key in ("fields", "genres", "certifications", "themes", "months"):
        assert saved[key] == json.loads(json.dumps(current[key])), key


# ---------------------------------------------------------------- public movie endpoints
# The fixture has 300 films "Film 1".."Film 300": year 2008 + id % 15, genre Action / Drama / Comedy by id % 3,
# all English with money and 2,500 votes, all with the same popularity (so ties fall back to the id).


MOVIES = f"{API_PREFIX}/movies"


def titles(response):
    assert response.status_code == 200
    return [m["title"] for m in response.json()["items"]]


def test_browse_pages_through_every_film_and_is_cacheable(api):
    first = api.get(MOVIES)
    body = first.json()
    assert (body["total"], body["page"], body["page_size"], body["pages"]) == (300, 1, 24, 13)
    assert titles(first)[:3] == ["Film 1", "Film 2", "Film 3"]  # equal popularity: by id
    assert first.headers["cache-control"] == "public, max-age=3600"
    last = api.get(MOVIES, params={"page": 13}).json()
    assert len(last["items"]) == 300 - 12 * 24 and api.get(MOVIES, params={"page": 14}).json()["items"] == []
    item = body["items"][0]
    assert item["poster"]["large"].startswith("https://image.tmdb.org/t/p/w780/") and item["genres"] == ["Drama"]


def test_search_finds_words_by_prefix_in_titles_and_overviews(api):
    assert sorted(titles(api.get(MOVIES, params={"q": "film 12", "page_size": 48}))) == sorted(
        ["Film 12", *[f"Film {i}" for i in range(120, 130)]])
    assert api.get(MOVIES, params={"q": "story numb"}).json()["total"] == 300  # overview words, prefix of "number"
    assert api.get(MOVIES, params={"q": "FILM 300"}).json()["total"] == 1


@pytest.mark.parametrize("q", ['"', "'", "AND", "film AND", "NEAR(", "*", "-film", "film OR 7", "(", "^", ":"])
def test_search_text_is_never_fts_syntax(api, q):
    assert api.get(MOVIES, params={"q": q}).status_code == 200


def test_search_with_only_punctuation_finds_nothing(api):
    assert api.get(MOVIES, params={"q": "!?."}).json()["total"] == 0


def test_filters_combine(api):
    count = lambda **p: api.get(MOVIES, params=p).json()["total"]
    assert count(genre="Action") == 100 and count(year_from=2010, year_to=2012) == 60
    assert count(genre="Action", year_from=2010, year_to=2012) == 20
    assert count(language="en") == 300 and count(language="fr") == 0 and count(has_money=True) == 300


def test_sorting(api):
    newest = api.get(MOVIES, params={"sort": "newest", "page_size": 48}).json()["items"]
    assert all(a["release_date"] >= b["release_date"] for a, b in zip(newest, newest[1:]))
    assert titles(api.get(MOVIES, params={"sort": "title"}))[:3] == ["Film 1", "Film 10", "Film 100"]
    best = api.get(MOVIES, params={"sort": "score", "page_size": 48}).json()["items"]
    assert all(a["score"] >= b["score"] for a, b in zip(best, best[1:]))


def test_bad_browse_parameters_are_named(api):
    assert errors_of(api.get(MOVIES, params={"page_size": 49})) == {
        "page_size": "input should be less than or equal to 48"}
    assert errors_of(api.get(MOVIES, params={"year_from": 2012, "year_to": 2010})) == {
        "year_to": "must be the same as or after year_from"}
    assert set(errors_of(api.get(MOVIES, params={"genre": "Cartoon", "page": 0, "sort": "random"}))) == {
        "genre", "page", "sort"}


def test_a_movie_page_has_facts_people_money_score_and_similar_films(api):
    r = api.get(f"{MOVIES}/7")
    m = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    assert (m["title"], m["year"], m["genres"], m["certification"]) == ("Film 7", 2015, ["Drama"], "PG-13")
    assert m["themes"] == ["heist"] and m["countries"] == ["US"] and m["companies"][0]["name"] == "Studio"
    assert m["cast"] and m["cast"][0]["order"] == min(c["order"] for c in m["cast"])
    assert m["crew"][0]["job"] == "Director"
    assert m["money"]["budget"] == 30_000_000 and m["money"]["budget_2025"] > m["money"]["budget"]
    assert m["money"]["suspect"] is False and m["rating"] == {"average": m["score"], "votes": 2500, "usable": True}
    assert len(m["similar"]) == 6 and all(s["poster"] for s in m["similar"])


def test_similar_films_come_from_any_year_but_never_the_film_itself(api):
    for movie_id in (15, 16, 150, 299):  # 15 is from 2008, the first year
        similar = api.get(f"{MOVIES}/{movie_id}").json()["similar"]
        assert movie_id not in [s["id"] for s in similar]
    first_year = api.get(f"{MOVIES}/15").json()  # 2008: no film is earlier, so a date rule would leave none
    assert first_year["year"] == 2008 and len(first_year["similar"]) == 6


def test_a_film_outside_the_comparables_pool_still_gets_similar_films(api, monkeypatch):
    monkeypatch.setattr(api.app.state.predictor.index, "row", lambda movie_id: None)
    similar = api.get(f"{MOVIES}/7").json()["similar"]
    assert len(similar) == 6 and 7 not in [s["id"] for s in similar]


def test_an_unknown_film_is_a_404(api):
    r = api.get(f"{MOVIES}/999999")
    assert r.status_code == 404 and r.json()["detail"] == "No film with id 999999"
    assert api.get(f"{MOVIES}/abc").status_code == 422


# ---------------------------------------------------------------- form support endpoints
# The fixture's directors are "Director 0".."Director 6" (ids 1000-1006), its actors "Actor 1".."Actor 300", and
# every film is made by the one company "Studio".


def test_people_autocomplete_by_role_most_films_first(api):
    r = api.get(f"{API_PREFIX}/people", params={"role": "director", "q": "director"})
    found = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    assert len(found) == 7 and all(set(m) == {"id", "name", "n_films"} for m in found)
    assert [m["n_films"] for m in found] == sorted((m["n_films"] for m in found), reverse=True)
    assert sum(m["n_films"] for m in found) == 300
    actors = api.get(f"{API_PREFIX}/people", params={"role": "actor", "q": "actor 1", "limit": 3}).json()
    assert len(actors) == 3 and all(m["name"].startswith("Actor 1") for m in actors)
    assert api.get(f"{API_PREFIX}/people", params={"role": "actor", "q": "director"}).json() == []  # roles apart


def test_company_and_franchise_autocomplete(api):
    assert api.get(f"{API_PREFIX}/companies", params={"q": "stu"}).json() == [{"id": 1, "name": "Studio", "n_films": 300}]
    assert api.get(f"{API_PREFIX}/collections", params={"q": "film"}).json() == []  # the fixture has no franchises


def test_autocomplete_parameters_are_checked(api):
    assert errors_of(api.get(f"{API_PREFIX}/people", params={"role": "writer", "q": "x"})) == {
        "role": "input should be 'director' or 'actor'"}
    assert errors_of(api.get(f"{API_PREFIX}/people", params={"role": "actor"})) == {"q": "required"}
    assert set(errors_of(api.get(f"{API_PREFIX}/companies", params={"q": "", "limit": 11}))) == {"q", "limit"}


def test_meta_options_match_the_contract_with_themes_filled_in(api, predictor):
    from ml.features.contract import CERTIFICATIONS, FIELDS, GENRES
    r = api.get(f"{API_PREFIX}/meta/options")
    options = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"
    assert [f["name"] for f in options["fields"]] == [f.name for f in FIELDS]
    themes = next(f for f in options["fields"] if f["name"] == "themes")
    assert themes["choices"] == options["themes"] == sorted(predictor.ctx.themes) == ["heist"]
    runtime = next(f for f in options["fields"] if f["name"] == "runtime")
    assert (runtime["min"], runtime["max"], runtime["required"]) == (40, 300, True)
    assert options["genres"] == list(GENRES) and options["certifications"] == list(CERTIFICATIONS)
    assert options["languages"] == [{"code": "en", "films": 300}] and options["countries"] == [{"code": "US", "films": 300}]
    assert options["months"] == list(range(1, 13)) and len(options["release_years"]) == 5


def test_suggested_release_years_never_pass_the_contracts_last_year(db):
    from datetime import date

    from backend.app.routers.meta import build_options
    con = connect_read_only(db / "movies.db")
    assert build_options(con, ["heist"], today=date(2026, 10, 22))["release_years"] == [2026, 2027, 2028, 2029, 2030]
    assert build_options(con, ["heist"], today=date(2033, 1, 1))["release_years"] == [2033, 2034, 2035]
    con.close()


def test_health_reports_the_models_the_database_and_the_cache(api):
    api.post(PREDICT, json=film_form())
    api.post(PREDICT, json=film_form())
    r = api.get(f"{API_PREFIX}/health")
    h = r.json()
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert (h["status"], h["api_version"], h["model_version"]) == ("ok", "1.0.0", "test.0")
    assert h["models"]["revenue"] == "films released 2008-2022"
    assert h["database"]["films"] == 300 and h["database"]["built_at"]
    assert h["prediction_cache"] == {"size": 1, "max_size": 1000, "hits": 1, "misses": 1}
    assert h["uptime_seconds"] >= 0 and h["load_seconds"] >= 0


# ---------------------------------------------------------------- the API as a whole


ENDPOINTS = {  # every endpoint and the test above that covers it; a new endpoint must be added here
    ("POST", "/predict"): test_predict_returns_the_full_output_in_both_revenue_modes,
    ("POST", "/predict/compare"): test_compare_differences_agree_with_separate_predictions,
    ("GET", "/movies"): test_browse_pages_through_every_film_and_is_cacheable,
    ("GET", "/movies/{movie_id}"): test_a_movie_page_has_facts_people_money_score_and_similar_films,
    ("GET", "/people"): test_people_autocomplete_by_role_most_films_first,
    ("GET", "/companies"): test_company_and_franchise_autocomplete,
    ("GET", "/collections"): test_company_and_franchise_autocomplete,
    ("GET", "/meta/options"): test_meta_options_match_the_contract_with_themes_filled_in,
    ("GET", "/health"): test_health_reports_the_models_the_database_and_the_cache,
}


def test_every_endpoint_is_listed_and_tested(api):
    paths = api.get("/openapi.json").json()["paths"]
    served = {(method.upper(), path.removeprefix(API_PREFIX)) for path, ops in paths.items() for method in ops}
    assert served == set(ENDPOINTS)


def test_the_wrong_method_is_a_405_not_a_crash(api):
    assert api.get(PREDICT).status_code == 405 and api.post(MOVIES).status_code == 405


def test_parallel_requests_give_the_same_answers_as_one_at_a_time(api):
    from concurrent.futures import ThreadPoolExecutor
    forms = [film_form(runtime=90 + 10 * i, budget=None if i % 2 else 30_000_000) for i in range(8)]
    one_by_one = [api.post(PREDICT, json=f).json() for f in forms]
    api.app.state.predictions = PredictionService(api.app.state.predictor)  # empty cache: really predict again
    with ThreadPoolExecutor(8) as pool:
        parallel = list(pool.map(lambda f: api.post(PREDICT, json=f).json(), forms))
    strip = lambda out: {k: v for k, v in out.items() if k != "cached"}
    assert [strip(a) for a in parallel] == [strip(b) for b in one_by_one]
    assert not any(a["cached"] for a in parallel)


def test_the_api_refuses_to_start_on_models_that_do_not_match_their_manifest(db, tmp_path, revenue_model,
                                                                           budget_model, score_model):
    """No injected predictor: the lifespan loads from MODELS_DIR and must stop at the manifest check."""
    from ml.models.rough import ROUGH_FILE
    from ml.models.train import save_model
    from ml.predict import write_manifest
    for model, rows in ((revenue_model, revenue_rows), (budget_model, budget_rows), (score_model, score_rows)):
        save_model(model, rows(), out_dir=tmp_path)
    write_manifest(tmp_path, ROUGH_FILE)
    meta = tmp_path / "score_meta.json"
    meta.write_text(meta.read_text(encoding="utf-8").replace('"q"', '"q" ', 1), encoding="utf-8")  # one byte changed
    app = create_app(Settings(db_path=db / "movies.db", models_dir=tmp_path))
    with pytest.raises(ValueError, match="score_meta.json changed"):
        with TestClient(app):
            pass
    assert not hasattr(app.state, "predictor")  # nothing was served
