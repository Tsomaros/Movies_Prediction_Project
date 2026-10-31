"""Fuzzing the prediction endpoints with hypothesis: whatever a client sends, the API answers 200 or a readable 422.

About 300 forms go to POST /predict, 100 requests to POST /predict/compare and 60 to POST /predict/sweep,
on the small app (the db fixture and small models). Each form starts from a valid one and has some fields replaced by:
- valid alternatives, including the edges of every limit (40 and 300 minutes, $1,000 and $1B, 5 and 10 actors);
- values just past the limits, or of the wrong type (strings for numbers, true for an id, lists for text);
- junk: huge or unicode strings, NaN and infinity, nested objects, unknown fields, nothing at all.
Sometimes the whole body is not even an object.

Every answer must be either 200 with ordered, finite ranges, or 422 with {"detail", "errors": {field: text}}
naming at least one field. A 500 fails the test: TestClient re-raises server errors. The examples are
derandomized, so a failure reproduces exactly.
"""

import json
import math

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from ml.features.contract import CERTIFICATIONS, GENRES
from tests.ml.test_eval import db  # noqa: F401 (fixture)
from tests.ml.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                               score_model, score_rows)
from tests.ml.test_predict import form as film_form
from tests.ml.test_predict import predictor  # noqa: F401 (fixture: a small Predictor on the db fixture)

PREDICT, COMPARE, SWEEP = f"{API_PREFIX}/predict", f"{API_PREFIX}/predict/compare", f"{API_PREFIX}/predict/sweep"
FUZZ = settings(max_examples=300, deadline=None, derandomize=True,
                suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


@pytest.fixture(scope="module")
def api(db, predictor):
    with TestClient(create_app(Settings(db_path=db / "movies.db", rate_limit=1_000_000, cache_size=50),
                               predictor=predictor)) as c:
        yield c


# ---------------------------------------------------------------- strategies

junk_text = st.one_of(st.text(max_size=30), st.text(min_size=2_000, max_size=2_200),
                      st.just("💥 ¿Qué? 映画"), st.just("   "), st.just(""))
non_finite = st.sampled_from([float("nan"), float("inf"), float("-inf")])
json_leaf = st.one_of(st.none(), st.booleans(), st.integers(-10**12, 10**12),
                      st.floats(allow_nan=True, allow_infinity=True), junk_text)
junk = st.recursive(json_leaf, lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner,
                                                                                         max_size=3), max_leaves=8)
ref = st.one_of(st.integers(-5, 3000), junk_text, st.fixed_dictionaries({"id": st.integers(-1, 2000)}),
                st.fixed_dictionaries({"name": junk_text}), st.just({"id": None, "name": None}), st.just(True))

FIELDS = {
    "genres": st.one_of(st.lists(st.sampled_from(GENRES), min_size=0, max_size=7), st.lists(junk_text, max_size=3)),
    "release_year": st.one_of(st.integers(1955, 2040), st.sampled_from([1960, 2035, "2021", 2021.5]), non_finite),
    "release_month": st.one_of(st.integers(-1, 14), st.just(6.0), non_finite),
    "runtime": st.one_of(st.integers(30, 320), st.sampled_from([40, 300, 39, 301, 100.5, "long"]), non_finite),
    "language": st.one_of(st.sampled_from(["en", "fr", "xx", "EN", "eng", ""]), junk_text),
    "certification": st.one_of(st.sampled_from(CERTIFICATIONS), junk_text),
    "director": ref,
    "actors": st.one_of(st.lists(ref, min_size=3, max_size=12), ref),
    "themes": st.one_of(st.just(["heist"]), st.lists(junk_text, max_size=6), st.just([])),
    "companies": st.one_of(st.lists(ref, max_size=6), ref),
    "countries": st.one_of(st.lists(st.sampled_from(["US", "GB", "us", "USA", ""]), max_size=6), junk_text),
    "franchise": st.one_of(st.none(), ref),
    "synopsis": st.one_of(st.none(), junk_text),
    "budget": st.one_of(st.none(), st.floats(allow_nan=True, allow_infinity=True),
                        st.sampled_from([999, 1_000, 1e9, 1e9 + 1, -5, 0, "5M"]), non_finite),
}


known_ref = st.one_of(st.integers(1000, 1006), st.integers(2001, 2300), st.sampled_from(["Director 3", "Someone New"]),
                      st.fixed_dictionaries({"id": st.integers(1000, 1006)}))
VALID = {  # only allowed values, edges included: these forms must get a 200
    "genres": st.lists(st.sampled_from(GENRES), min_size=1, max_size=5, unique=True),
    "release_year": st.integers(1960, 2035),
    "release_month": st.integers(1, 12),
    "runtime": st.integers(40, 300),
    "language": st.sampled_from(["en", "fr", "ja", "xx"]),
    "certification": st.sampled_from(CERTIFICATIONS),
    "director": known_ref,
    "actors": st.lists(known_ref, min_size=5, max_size=10),
    "themes": st.just(["heist"]),
    "companies": st.lists(st.one_of(st.integers(1, 5), st.just("Some Studio")), max_size=5),
    "countries": st.lists(st.sampled_from(["US", "GB", "FR", "JP"]), max_size=5),
    "franchise": st.one_of(st.none(), st.integers(1, 50), st.just("A New Saga")),
    "synopsis": st.one_of(st.none(), st.text(min_size=1, max_size=300).filter(str.strip)),
    "budget": st.one_of(st.none(), st.floats(1_000, 1e9), st.sampled_from([1_000, 1e9])),
}


@st.composite
def valid_forms(draw):
    form = film_form()
    for name in draw(st.lists(st.sampled_from(list(VALID)), max_size=8, unique=True)):
        form[name] = draw(VALID[name])
    return form


@st.composite
def forms(draw):
    form = film_form()
    for name in draw(st.lists(st.sampled_from(list(FIELDS)), max_size=6, unique=True)):
        choice = draw(st.sampled_from(["field", "field", "junk", "drop"]))
        if choice == "drop":
            form.pop(name, None)
        else:
            form[name] = draw(FIELDS[name] if choice == "field" else junk)
    if draw(st.integers(0, 9)) == 0:
        form[draw(st.text(min_size=1, max_size=10))] = draw(junk)  # an unknown (or duplicate) field
    return form


bodies = st.one_of(valid_forms(), forms(), forms(), junk)  # about a third valid; now and then not even an object


@st.composite
def compares(draw):
    if draw(st.booleans()):  # a valid compare: valid base, 1-3 valid changes (null clears an optional field)
        optional = st.sampled_from(["companies", "countries", "franchise", "synopsis", "budget"])
        change = st.one_of(st.sampled_from(list(VALID)).flatmap(lambda f: VALID[f].map(lambda v: {f: v})),
                           optional.map(lambda f: {f: None}))
        return {"base": draw(valid_forms()), "variants": draw(st.lists(change, min_size=1, max_size=3))}
    base = draw(forms())
    variants = draw(st.lists(st.dictionaries(st.sampled_from(list(FIELDS)), junk | st.none(), max_size=3)
                             | st.just({"budget": 50_000_000}), min_size=0, max_size=5))
    return draw(st.one_of(st.just({"base": base, "variants": variants}), junk))


@st.composite
def sweeps(draw):
    if draw(st.booleans()):  # a valid sweep: a valid form, 2-12 values of a sweepable field
        field = draw(st.sampled_from(["release_month", "runtime", "budget"]))
        values = draw(st.lists(VALID[field], min_size=2, max_size=12))
        return {"form": draw(valid_forms()), "field": field, "values": values}
    body = {"form": draw(forms()), "field": draw(st.sampled_from(["release_month", "runtime", "budget", "genres"]) | junk),
            "values": draw(st.lists(junk, max_size=14) | junk)}
    return draw(st.one_of(st.just(body), junk))


# ---------------------------------------------------------------- checks


def post(api, url, body, record=True):
    """Send the JSON text ourselves: httpx refuses NaN and Infinity, which a client can still send (Python's
    json and the server's parser accept them)."""
    response = api.post(url, content=json.dumps(body, allow_nan=True), headers={"Content-Type": "application/json"})
    if record:
        event(f"status {response.status_code}")
    return response


def check(response):
    assert response.status_code in (200, 422), (response.status_code, response.text[:300])
    body = response.json()
    if response.status_code == 422:
        assert body["detail"] == "Some fields need fixing"
        assert body["errors"] and all(isinstance(k, str) and isinstance(v, str) and v for k, v in body["errors"].items())
        return None
    return body


def check_prediction(out):
    for t in ("budget", "revenue", "score"):
        low, middle, high = out[t]["low"], out[t]["middle"], out[t]["high"]
        assert all(math.isfinite(v) for v in (low, middle, high)) and low <= middle <= high


@pytest.mark.slow
@FUZZ
@given(body=bodies)
def test_predict_answers_200_or_a_readable_422(api, body):
    out = check(post(api, PREDICT, body))
    if out is not None:
        check_prediction(out)


@pytest.mark.slow
@settings(FUZZ, max_examples=100)
@given(body=compares())
def test_compare_answers_200_or_a_readable_422(api, body):
    out = check(post(api, COMPARE, body))
    if out is not None:
        check_prediction(out["base"])
        for variant in out["variants"]:
            check_prediction(variant["prediction"])
            assert all(f in body["base"] or f in variant["differences"]["changed_fields"]
                       for f in variant["differences"]["changed_fields"])


@pytest.mark.slow
@settings(FUZZ, max_examples=60)
@given(body=sweeps())
def test_sweep_answers_200_or_a_readable_422(api, body):
    out = check(post(api, SWEEP, body))
    if out is not None:
        assert len(out["points"]) == len(body["values"])
        for point in out["points"]:
            check_prediction(point)


def test_the_fuzzing_reaches_both_outcomes(api):
    """The fuzz tests mean something only if valid forms get through as well as bad ones get refused."""
    assert api.post(PREDICT, json=film_form()).status_code == 200
    assert post(api, PREDICT, {**film_form(), "budget": float("nan")}, record=False).status_code == 422
    assert post(api, PREDICT, {**film_form(), "runtime": float("inf")}, record=False).status_code == 422
    assert api.post(PREDICT, json=[1, 2]).status_code == 422
