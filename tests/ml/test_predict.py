"""The predict() package: the full output, both revenue modes, warnings and the manifest, on a small database
and small synthetic models (no network, no real models needed)."""

import json
import shutil
import sqlite3

import numpy as np
import pytest

from ml.explain.comparables import Index
from ml.models.chain import Chain
from ml.models.rough import ROUGH_FILE
from ml.models.train import save_model
from ml.predict import InvalidForm, Predictor, budget_position, check_manifest, write_manifest
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db with a features table, 2008-2022)
from tests.features.test_features import context
from tests.ml.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                               score_model, score_rows)

RULE = {"cutoff": {"revenue": 81.0, "budget": 12.0}}
MANIFEST = {"version": "test.0", "models": {t: {"trained_on": "films released 2008-2022"}
                                            for t in ("revenue", "budget", "score")}}


@pytest.fixture(scope="module")
def predictor(db, revenue_model, budget_model, score_model):
    con = sqlite3.connect(db / "movies.db")
    ctx = context(con)
    index = Index.build(con, cache=db / "emb.npz", theme_names=["heist"])
    con.close()
    chain = Chain(revenue_model, budget_model, {"given": 0.3, "estimated": 0.5})
    return Predictor(chain, score_model, ctx, RULE, index, MANIFEST, db / "movies.db")


def form(**overrides):
    base = {"genres": ["Action", "Drama"], "release_year": 2021, "release_month": 6, "runtime": 120,
            "language": "en", "certification": "PG-13", "director": 1003,
            "actors": [2010, 2011, 2012, 2013, 2014], "themes": ["heist"], "companies": ["Some Studio"],
            "countries": ["US"], "budget": 40_000_000}
    return {**base, **overrides}


def test_full_output_with_a_budget(predictor):
    out = predictor.predict(form())
    assert json.loads(json.dumps(out)) == out  # JSON-ready
    assert set(out) == {"model_version", "as_of", "budget", "revenue", "score", "drivers", "comparables", "warnings"}
    assert out["model_version"] == "test.0" and out["as_of"] == "2021-06-01"
    for target in ("budget", "revenue", "score"):
        r = out[target]
        assert r["low"] <= r["middle"] <= r["high"] and isinstance(r["rough"], bool) and r["text"]
        assert set(out["drivers"][target]) == {"up", "down"}
        drivers = out["drivers"][target]["up"] + out["drivers"][target]["down"]
        assert 0 < len(drivers) <= 5 and all("_" not in d["text"] for d in drivers)
    assert out["revenue"]["mode"] == "given" and out["revenue"]["budget_used"] == pytest.approx(40_000_000)
    assert out["score"]["rough"] is False
    comparison = out["budget"]["comparison"]
    assert comparison["text"].startswith("Similar films usually cost") and comparison["budget"] == 40_000_000
    assert comparison["sentence"].startswith("Your budget of $40M is ")


def test_estimated_mode_without_a_budget(predictor):
    out = predictor.predict(form(budget=None))
    assert out["revenue"]["mode"] == "estimated"
    assert out["revenue"]["budget_used"] == pytest.approx(out["budget"]["middle"])  # the budget model's middle
    assert "sentence" not in out["budget"]["comparison"]
    budget_drivers = [d for d in out["drivers"]["revenue"]["up"] + out["drivers"]["revenue"]["down"]
                      if d["group"] == "budget"]
    assert budget_drivers and all(d["estimated"] and "estimated budget" in d["text"] for d in budget_drivers)
    given = predictor.predict(form(budget=out["revenue"]["budget_used"]))
    assert given["revenue"]["middle"] == pytest.approx(out["revenue"]["middle"])  # same budget, same middle
    assert (out["revenue"]["high"] / out["revenue"]["low"]) >= (given["revenue"]["high"] / given["revenue"]["low"])


def test_comparables_are_earlier_films_only(predictor):
    for year in (2012, 2016, 2021):
        out = predictor.predict(form(release_year=year, release_month=1))
        as_of = np.datetime64(out["as_of"]).astype(int)
        days = dict(zip(predictor.index.ids.tolist(), predictor.index.days.tolist()))
        assert out["comparables"] and all(days[f["id"]] < as_of for f in out["comparables"])


def test_invalid_forms_are_refused_with_readable_errors(predictor):
    with pytest.raises(InvalidForm) as e:
        predictor.predict(form(runtime=10, popularity=50, themes=["not a theme"]))
    assert set(e.value.errors) == {"runtime", "popularity", "themes"}
    assert e.value.errors["popularity"] == "unknown field"


def test_warnings(predictor):
    codes = lambda out: {w["code"] for w in out["warnings"]}
    assert codes(predictor.predict(form())) == set()
    out = predictor.predict(form(director="Nobody Known", actors=[2010, 2011, 2012, "New One", "New Two"],
                                 countries=[], companies=[], release_year=2024, budget=200_000_000))
    assert codes(out) == {"new_director", "new_actors", "no_country", "no_studio", "future_release", "big_budget"}
    text = {w["code"]: w["text"] for w in out["warnings"]}
    assert "2 of the 5 actors" in text["new_actors"] and "ends in 2022" in text["future_release"]


def test_names_come_from_the_database(predictor):
    names = predictor.names({"director": {"id": 1003, "name": None}, "actors": [{"id": 2010, "name": None},
                             {"id": None, "name": "Typed Name"}], "companies": [], "franchise": None})
    assert names == {"director": "Director 3", "actors": ["Actor 10", "Typed Name"], "companies": [],
                     "franchise": None}


@pytest.mark.parametrize("budget, position", [
    (10.0, "below"), (19.5, "at the low end"), (20.5, "at the low end"), (50.0, "within"),
    (78.0, "at the high end"), (82.0, "at the high end"), (90.0, "above")])
def test_budget_near_an_edge_is_at_the_low_or_high_end(budget, position):
    assert budget_position(budget, 20.0, 80.0) == position


def test_manifest_records_and_checks_every_file(tmp_path, revenue_model, budget_model, score_model):
    for model, rows in ((revenue_model, revenue_rows), (budget_model, budget_rows), (score_model, score_rows)):
        save_model(model, rows(), out_dir=tmp_path)
    manifest = write_manifest(tmp_path, ROUGH_FILE)
    assert (tmp_path / ROUGH_FILE.name).read_bytes() == ROUGH_FILE.read_bytes()  # the rule is copied alongside
    assert len(manifest["files"]) == 13 and manifest["tag"] == "final-models"
    assert manifest["models"]["revenue"]["trained_on"] == "films released 2000-2009"
    assert check_manifest(tmp_path)["version"] == manifest["version"]
    shutil.copyfile(tmp_path / "budget_p10.joblib", tmp_path / "budget_p50.joblib")  # a model changed behind our back
    with pytest.raises(ValueError, match="budget_p50.joblib"):
        check_manifest(tmp_path)
