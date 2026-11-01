"""The batched predict path (V1.5): sweep and compare run each LightGBM booster once for all their forms, the
answers equal one prediction per form, the synopsis embedding is cached and /predict says X-Cache: hit or miss.

Offline: the small Predictor on the fixture database (tests/ml/test_predict.py)."""

from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.prediction import PredictionService, merge
from backend.app.settings import API_PREFIX, Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db with a features table, 2008-2022)
from tests.ml.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                                  score_model, score_rows)
from tests.ml.test_predict import form as film_form
from tests.ml.test_predict import predictor  # noqa: F401 (fixture: a small Predictor on the db fixture)

PREDICT, COMPARE, SWEEP = f"{API_PREFIX}/predict", f"{API_PREFIX}/predict/compare", f"{API_PREFIX}/predict/sweep"
VARIANTS = [{"budget": 80_000_000}, {"budget": None}, {"runtime": 150, "release_month": 12}]  # mixed revenue modes


@pytest.fixture
def api(db, predictor):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=predictor)) as c:
        yield c


@pytest.fixture
def calls(predictor, monkeypatch):
    """(target, key) -> one (pred_contrib, rows) pair per call of that booster's predict."""
    seen = defaultdict(list)
    models = {"budget": predictor.chain.budget, "revenue": predictor.chain.revenue, "score": predictor.score}
    for target, model in models.items():
        for key, booster in model.models.items():
            def spy(data, *args, _real=booster.predict, _name=(target, key), **kwargs):
                seen[_name].append((bool(kwargs.get("pred_contrib")), len(data)))
                return _real(data, *args, **kwargs)
            monkeypatch.setattr(booster, "predict", spy)
    return seen


BOOSTERS = [(t, k) for t in ("budget", "revenue", "score") for k in ("p10", "p50", "p90")]


def test_a_sweep_runs_each_booster_once_for_all_12_months_and_explains_nothing(api, calls):
    r = api.post(SWEEP, json={"form": film_form(runtime=97), "field": "release_month", "values": list(range(1, 13))})
    assert r.status_code == 200
    assert {b: calls[b] for b in BOOSTERS} == {b: [(False, 12)] for b in BOOSTERS}


def test_a_compare_runs_each_booster_once_and_each_middle_model_explains_once(api, calls):
    r = api.post(COMPARE, json={"base": film_form(runtime=98), "variants": VARIANTS})
    assert r.status_code == 200
    want = {b: [(False, 4)] + ([(True, 4)] if b[1] == "p50" else []) for b in BOOSTERS}
    assert {b: calls[b] for b in BOOSTERS} == want


def test_one_prediction_explains_only_the_middle_models_and_runs_no_booster_twice(api, calls):
    assert api.post(PREDICT, json=film_form(runtime=99, budget=None)).status_code == 200
    want = {b: [(False, 1)] + ([(True, 1)] if b[1] == "p50" else []) for b in BOOSTERS}
    assert {b: calls[b] for b in BOOSTERS} == want


def without_cached(out):
    return {k: v for k, v in out.items() if k != "cached"}


def test_batched_compare_and_sweep_equal_one_prediction_per_form(predictor):
    base = film_form(runtime=101)
    batched = PredictionService(predictor).compare(base, VARIANTS)
    alone = PredictionService(predictor, size=0)
    assert without_cached(batched["base"]) == alone.predict(base)[0]
    for variant, changes in zip(batched["variants"], VARIANTS):
        assert without_cached(variant["prediction"]) == alone.predict(merge(base, changes))[0]

    for field, values in (("release_month", list(range(1, 13))), ("budget", [1e6, 5e7, 3e8])):
        for form in (base, film_form(runtime=101, budget=None)):
            points = PredictionService(predictor).sweep(form, field, values)[0]["points"]
            for point, value in zip(points, values):
                single = alone.predict(merge(form, {field: value}))[0]
                assert {t: point[t] for t in ("budget", "revenue", "score")} == {
                    t: single[t] for t in ("budget", "revenue", "score")}
                assert point["revenue_mode"] == single["revenue"]["mode"]


def test_a_compare_variant_equal_to_the_base_is_still_reported_as_cached(predictor):
    out = PredictionService(predictor).compare(film_form(runtime=102), [{"runtime": 102}])
    assert out["base"]["cached"] is False and out["variants"][0]["prediction"]["cached"] is True


def test_the_synopsis_is_embedded_once_for_the_same_text(predictor, monkeypatch):
    texts = []
    real = predictor.ctx.embed
    monkeypatch.setattr(predictor.ctx, "embed", lambda text: texts.append(text) or real(text))
    service = PredictionService(predictor)
    story = "A crew of thieves plans one last job."
    service.predict(film_form(runtime=103, synopsis=story))
    service.predict(film_form(runtime=104, synopsis=story))
    service.sweep(film_form(runtime=105, synopsis=story), "release_month", [1, 2, 3])
    service.predict(film_form(runtime=106, synopsis="Something else entirely."))
    service.predict(film_form(runtime=107))  # no synopsis: nothing to embed
    assert texts == [story, "Something else entirely."]


def test_predict_compare_and_sweep_say_whether_the_cache_answered(api):
    first, again = (api.post(PREDICT, json=film_form(runtime=111)) for _ in range(2))
    assert (first.headers["x-cache"], again.headers["x-cache"]) == ("miss", "hit")
    assert without_cached(again.json()) == without_cached(first.json())

    body = {"base": film_form(runtime=112), "variants": VARIANTS}
    first, again = (api.post(COMPARE, json=body) for _ in range(2))
    assert (first.headers["x-cache"], again.headers["x-cache"]) == ("miss", "hit")

    body = {"form": film_form(runtime=113), "field": "release_month", "values": [1, 2, 3]}
    first, again = (api.post(SWEEP, json=body) for _ in range(2))
    assert (first.headers["x-cache"], again.headers["x-cache"]) == ("miss", "hit")
    assert again.json() == first.json()
