"""End to end: a raw TMDB pull all the way to an API answer, with every step's real code (marked slow).

    tests/fixtures/mini_raw.jsonl (213 records: 200 normal films 2005-2020 and 13 messy ones)
      -> clean (every messy case trips its rule) -> build_db -> FeatureContext.load + the features table
      -> tiny LightGBM models trained on the train split -> conformal q from backtest fold 2
      -> Chain + score model -> comparables index -> Predictor -> create_app -> HTTP

Only the text model is faked (tests.test_features.FakeEmbedder), so the test stays offline. The feature
context uses the committed vocab, themes and PCA, exactly as the app does, so the columns match
ml/features/feature_list.json. It catches bugs that live between days: a column renamed in one step and
not the next, a cleaning flag a view forgets, a model that can't be loaded into the predictor.
"""

import json
import shutil
import sqlite3

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from ml.data import build_db
from ml.eval.metrics import spearman
from ml.eval.splits import FOLDS, fold_data, load
from ml.explain.comparables import Index
from ml.features.build import FeatureContext, build_table, write_table
from ml.features.history import day_number
from ml.models.calibrate import conformal_q
from ml.models.chain import Chain
from ml.models.rough import load_rule
from ml.models.train import LgbmQuantile
from ml.predict import Predictor
from tests.fixtures import mini_raw
from tests.test_features import FakeEmbedder

pytestmark = pytest.mark.slow
PARAMS = {"num_leaves": 7, "min_data_in_leaf": 5, "learning_rate": 0.1}  # sized for about 150 training films
TREES = 40
CPI = {y: 100.0 + 2 * (y - 2000) for y in range(2000, 2027)}
CALIBRATION_FOLD = FOLDS[1]  # trains on <=2012, scores 2013-15: never 2016-18


def test_the_committed_fixture_is_what_the_generator_makes():
    lines = mini_raw.FILE.read_text(encoding="utf-8").splitlines()
    assert lines == [json.dumps(r, sort_keys=True) for r in mini_raw.records()]


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    raw, cpi, db = tmp / "raw.jsonl", tmp / "cpi.csv", tmp / "movies.db"
    shutil.copyfile(mini_raw.FILE, raw)
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in CPI.items()), encoding="utf-8")
    report = build_db.build(raw, cpi, db)

    con = sqlite3.connect(db)
    ctx = FeatureContext.load(con, embedder=FakeEmbedder())
    write_table(con, build_table(con, ctx, cache=tmp / "emb.npz"))

    models, q = {}, {}
    for target in ("revenue", "budget", "score"):
        f_train, f_test = fold_data(target, CALIBRATION_FOLD, db_path=db)
        p = LgbmQuantile(target, PARAMS, TREES).fit(f_train).predict(f_test)
        q[target] = conformal_q(f_test["target"], p["p10"], p["p90"])
        models[target] = LgbmQuantile(target, PARAMS, TREES, q=q[target]).fit(load(target, "train", db_path=db))
    index = Index.build(con, cache=tmp / "emb.npz")
    con.close()

    chain = Chain(models["revenue"], models["budget"], {"given": q["revenue"], "estimated": 1.25 * q["revenue"]})
    manifest = {"version": "e2e.0", "models": {t: {"trained_on": "films released 2005-2015"} for t in models}}
    predictor = Predictor(chain, models["score"], ctx, load_rule(), index, manifest, db)
    client = TestClient(create_app(Settings(db_path=db), predictor=predictor))
    with client:
        yield {"report": report, "db": db, "models": models, "q": q, "predictor": predictor, "api": client}


# ---------------------------------------------------------------- the data steps


def test_every_messy_film_trips_its_cleaning_rule(pipeline):
    r = pipeline["report"]
    assert (r["raw_records"], r["films"]) == (213, 211)  # the unreleased film and the older pull are dropped
    assert r["not_released_dropped"] == 1 and r["duplicate_ids_dropped"] == 1
    assert r["budget_zero_or_missing"] == 1 and r["budget_placeholder_nulled"] == 1
    assert r["money_suspect_low_ratio"] == 1 and r["money_suspect_currency"] == 1
    assert r["runtime_nulled"] == 2 and r["title_from_original_title"] == 1
    assert r["score_nulled_no_votes"] == 1 and r["revenue_incomplete"] == 1


def test_the_training_views_keep_the_messy_films_out(pipeline):
    con = sqlite3.connect(pipeline["db"])
    in_view = lambda view: {i for (i,) in con.execute(f"SELECT id FROM {view} WHERE id > 9000")}
    assert in_view("v_train_revenue") == {9005, 9006, 9008, 9009, 9010, 9011}  # money fine, the rest is NULLed
    assert in_view("v_train_budget") == {9005, 9006, 9008, 9009, 9010, 9011, 9012}  # a young film's budget is fine
    assert 9010 not in in_view("v_train_score")
    row = con.execute("SELECT title, runtime, budget FROM movies WHERE id = 9008").fetchone()
    assert row[0] == "Messy New Pull"
    assert con.execute("SELECT COUNT(*) FROM features").fetchone()[0] == 211
    con.close()


def test_the_feature_table_follows_the_committed_feature_list(pipeline):
    con = sqlite3.connect(pipeline["db"])
    columns = [r[1] for r in con.execute("PRAGMA table_info(features)")][2:]
    con.close()
    listed = [e["name"] for e in json.loads(open("ml/features/feature_list.json", encoding="utf-8").read())]
    assert columns == listed


# ---------------------------------------------------------------- the models


def test_the_tiny_models_learn_something(pipeline):
    """Budgets grow with the director's level in the fixture, so the budget model must rank 2016-18 films."""
    validation = load("budget", "validation", db_path=pipeline["db"])
    p = pipeline["models"]["budget"].predict(validation)
    assert spearman(validation["target"], p["p50"]) > 0.3
    assert all(q > 0 for q in pipeline["q"].values())


def test_the_revenue_model_rises_with_the_budget(pipeline):
    rows = load("revenue", "validation", db_path=pipeline["db"]).iloc[:10]
    model = pipeline["models"]["revenue"]
    middles = [model.predict(rows.assign(log_budget=np.log(b)))["p50"].to_numpy() for b in (1e6, 1e7, 1e8)]
    assert (np.diff(np.vstack(middles), axis=0) >= 0).all()


# ---------------------------------------------------------------- through the API


FORM = {"genres": ["Action"], "release_year": 2021, "release_month": 6, "runtime": 110, "language": "en",
        "certification": "PG-13", "director": 1003, "actors": [2000, 2013, 2026, 2039, 2052], "themes": ["heist"],
        "companies": [1], "countries": ["US"], "budget": 30_000_000,
        "synopsis": "A crew of thieves plans one last job."}


@pytest.mark.parametrize("budget", [30_000_000, None])
def test_a_creator_form_gets_a_full_prediction_over_http(pipeline, budget):
    form = {**FORM, "budget": budget} if budget else {k: v for k, v in FORM.items() if k != "budget"}
    r = pipeline["api"].post(f"{API_PREFIX}/predict", json=form)
    assert r.status_code == 200
    out = r.json()
    for t in ("budget", "revenue", "score"):
        assert 0 < out[t]["low"] <= out[t]["middle"] <= out[t]["high"]
        assert out["drivers"][t]["up"] or out["drivers"][t]["down"]
    assert out["revenue"]["mode"] == ("given" if budget else "estimated")
    assert out["model_version"] == "e2e.0" and "future_release" in {w["code"] for w in out["warnings"]}
    days = dict(zip(pipeline["predictor"].index.ids.tolist(), pipeline["predictor"].index.days.tolist()))
    assert out["comparables"] and all(days[f["id"]] < day_number("2021-06-01") for f in out["comparables"])


def test_a_bad_form_is_a_readable_422(pipeline):
    r = pipeline["api"].post(f"{API_PREFIX}/predict", json={**FORM, "runtime": 5, "themes": ["no such theme"]})
    assert r.status_code == 422
    assert set(r.json()["errors"]) == {"runtime", "themes"}


def test_the_public_pages_show_the_cleaned_data(pipeline):
    api = pipeline["api"]
    token = api.get(f"{API_PREFIX}/movies/9003").json()
    assert token["money"]["suspect"] is True and token["money"]["suspect_reason"] == "low_ratio"
    assert api.get(f"{API_PREFIX}/movies/9008").json()["title"] == "Messy New Pull"
    assert api.get(f"{API_PREFIX}/movies/9007").status_code == 404  # never released: not in the database
    assert api.get(f"{API_PREFIX}/movies", params={"q": "messy"}).json()["total"] == 10
    sequel = api.get(f"{API_PREFIX}/movies/29").json()  # i = 28 is a "Mini Saga" film
    assert sequel["franchise"] == {"id": 77, "name": "Mini Saga"}
    assert sequel["id"] not in [s["id"] for s in sequel["similar"]]


def test_autocomplete_and_health_on_the_built_database(pipeline):
    api = pipeline["api"]
    directors = api.get(f"{API_PREFIX}/people", params={"role": "director", "q": "director 1"}).json()
    names = [d["name"] for d in directors]  # "Director 1" and "Director 10".."Director 19": 11 match
    assert len(names) == 10 and all(n.startswith("Director 1") for n in names)
    assert [d["n_films"] for d in directors] == sorted((d["n_films"] for d in directors), reverse=True)
    assert api.get(f"{API_PREFIX}/companies", params={"q": "paris"}).json()[0]["name"] == "Paris Pictures"
    health = api.get(f"{API_PREFIX}/health").json()
    assert health["status"] == "ok" and health["database"]["films"] == 211
