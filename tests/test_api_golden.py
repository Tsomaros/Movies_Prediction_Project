"""The API on the real app: the golden forms over HTTP, plus the public and form-support endpoints on the
real database. Skipped, like tests/test_golden.py, without data/movies.db, the all-data models or the
comparables index.

- POST /predict gives exactly what predict() gives for the three golden forms (plus `cached` and the
  comparables' poster URLs), and its numbers, drivers, comparables and warnings match the golden snapshot;
- a prediction over HTTP takes under 400 ms (median of 10 uncached calls per form);
- real autocomplete, movie pages, options and health answer sensibly.
"""

import json
import statistics
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from ml.predict import Predictor
from tests.test_golden import FORMS, GOLDEN_FILE, NEEDED, snapshot

pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not all(p.exists() for p in NEEDED),
                                 reason="needs data/movies.db, the all-data models and the comparables index")]
MAX_MS = 400


@pytest.fixture(scope="module")
def predictor():
    return Predictor.load()


@pytest.fixture(scope="module")
def api(predictor):
    with TestClient(create_app(Settings(rate_limit=10_000, cache_size=0), predictor=predictor)) as c:
        yield c


COMPARISON_OPTIONAL = ("budget", "position", "ratio", "sentence")  # sent as null over HTTP when no budget is given


def without_api_extras(out):
    films = [{k: v for k, v in f.items() if k != "poster"} for f in out["comparables"]]
    return {**{k: v for k, v in out.items() if k != "cached"}, "comparables": films}


def with_nulls(out):
    """predict() leaves the comparison's optional fields out; the response model writes them as null."""
    comparison = {k: None for k in COMPARISON_OPTIONAL} | out["budget"]["comparison"]
    return {**out, "budget": {**out["budget"], "comparison": comparison}}


@pytest.mark.parametrize("name", FORMS)
def test_golden_forms_over_http_equal_predict(api, predictor, name):
    r = api.post(f"{API_PREFIX}/predict", json=FORMS[name])
    assert r.status_code == 200
    out = r.json()
    assert without_api_extras(out) == with_nulls(predictor.predict(FORMS[name]))
    assert snapshot(out) == json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))[name]


@pytest.mark.parametrize("name", FORMS)
def test_a_prediction_over_http_takes_under_400_ms(api, name):
    url = f"{API_PREFIX}/predict"
    api.post(url, json=FORMS[name])  # warm up (the synopsis model loads lazily)
    times = []
    for i in range(10):  # cache_size=0, so every call is a real prediction
        start = time.perf_counter()
        assert api.post(url, json=FORMS[name]).status_code == 200
        times.append((time.perf_counter() - start) * 1000)
    assert statistics.median(times) < MAX_MS


def test_compare_on_the_real_models(api):
    base = FORMS["small_drama"]
    out = api.post(f"{API_PREFIX}/predict/compare",
                   json={"base": base, "variants": [{"budget": 20_000_000}, {"companies": [33]}]}).json()
    budget, studio = (v["differences"] for v in out["variants"])
    assert budget["changed_fields"] == ["budget"] and budget["mode_changed"] is True
    assert studio["changed_fields"] == ["companies"] and studio["revenue"]["ratio"] > 1  # Universal vs A24


def test_real_autocomplete(api):
    tom = api.get(f"{API_PREFIX}/people", params={"role": "actor", "q": "tom ha"}).json()
    assert tom[0] == {"id": 31, "name": "Tom Hanks", "n_films": tom[0]["n_films"]} and tom[0]["n_films"] > 50
    assert api.get(f"{API_PREFIX}/people", params={"role": "director", "q": "gerwig"}).json()[0]["id"] == 45400
    assert api.get(f"{API_PREFIX}/companies", params={"q": "marvel"}).json()[0]["name"] == "Marvel Studios"
    assert api.get(f"{API_PREFIX}/collections", params={"q": "harry pot"}).json()[0]["name"] == "Harry Potter Collection"


def test_real_movie_pages(api):
    found = api.get(f"{API_PREFIX}/movies", params={"q": "avengers infinity"}).json()["items"]
    assert found[0]["id"] == 299536
    film = api.get(f"{API_PREFIX}/movies/299536").json()
    assert film["title"] == "Avengers: Infinity War" and film["franchise"]["name"] == "The Avengers Collection"
    similar = [s["id"] for s in film["similar"]]
    assert 299536 not in similar and 299534 in similar  # Avengers: Endgame (2019), a later film, is allowed
    assert api.get(f"{API_PREFIX}/movies", params={"q": "spider-man"}).json()["items"][0]["title"].startswith("Spider-Man")


def test_real_options_and_health(api, predictor):
    options = api.get(f"{API_PREFIX}/meta/options").json()
    assert len(options["themes"]) == 27 and options["languages"][0]["code"] == "en"
    health = api.get(f"{API_PREFIX}/health").json()
    assert health["status"] == "ok" and health["model_version"] == predictor.manifest["version"]
    assert health["database"]["films"] == 79_199
