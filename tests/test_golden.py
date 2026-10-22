"""Golden examples: predict() on the app's real all-data models for three fixed creator forms.

Skipped when the gitignored files are missing (data/movies.db, the .joblib models, the comparables
index). Each form is checked twice:
- by rules that must hold whatever the numbers (ordered ranges, mode, warnings, earlier comparables,
  speed under 400 ms);
- against tests/golden/predictions.json, a snapshot of the numbers, drivers and comparables, so any
  change to the models, features or wording shows up. The models are frozen (Day 6), so the snapshot
  should only change on purpose: rewrite it with  UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
"""

import json
import os
import time
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from ml.data.build_db import DB_FILE
from ml.explain.comparables import INDEX_FILE
from ml.features.history import day_number
from ml.models.train import QUANTILE_KEYS, TARGETS
from ml.predict import FINAL_DIR, Predictor, check_manifest

GOLDEN_FILE = Path("tests/golden/predictions.json")
NEEDED = [DB_FILE, INDEX_FILE] + [FINAL_DIR / f"{t}_{k}.joblib" for t in TARGETS for k in QUANTILE_KEYS]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDED),
                                reason="needs data/movies.db, the all-data models and the comparables index")
MAX_MS = 400

FORMS = {
    "franchise_blockbuster": {  # the Russo brothers, the Avengers cast, Marvel, the Avengers Collection
        "genres": ["Action", "Adventure", "Science Fiction"], "release_year": 2027, "release_month": 5,
        "runtime": 150, "language": "en", "certification": "PG-13", "director": 19271,
        "actors": [3223, 16828, 1245, 74568, 103], "themes": ["superhero", "science fiction"],
        "companies": [420], "countries": ["US"], "franchise": 86311, "budget": 300_000_000,
        "synopsis": "The surviving heroes reunite to stop a cosmic threat that could erase every world they know.",
    },
    "small_drama": {  # Greta Gerwig, Saoirse Ronan, Florence Pugh, Timothee Chalamet and two newcomers, A24
        "genres": ["Drama"], "release_year": 2026, "release_month": 10, "runtime": 105, "language": "en",
        "certification": "R", "director": 45400, "actors": [36592, 1373737, 1190668, "Ann Newcomer", "Bo Unknown"],
        "themes": ["family", "coming of age and school"], "companies": [41077], "countries": ["US"],
        "synopsis": "Two sisters return to their small hometown to care for their ailing mother.",
    },
    "unknown_cast": {  # nobody we know, no studio or country, a small budget
        "genres": ["Horror", "Thriller"], "release_year": 2026, "release_month": 10, "runtime": 92, "language": "en",
        "certification": "R", "director": "Totally New Director",
        "actors": ["New Actor One", "New Actor Two", "New Actor Three", "New Actor Four", "New Actor Five"],
        "themes": ["supernatural"], "budget": 2_000_000,
    },
}


@pytest.fixture(scope="module")
def predictor():
    return Predictor.load()


@pytest.fixture(scope="module")
def outputs(predictor):
    return {name: predictor.predict(form) for name, form in FORMS.items()}


def drivers(out, target):
    return out["drivers"][target]["up"] + out["drivers"][target]["down"]


def snapshot(out):
    """What the golden file keeps: numbers to 6 significant figures, drivers, comparables, warnings."""
    rounded = lambda x: None if x is None else float(f"{x:.6g}")
    ranges = {t: {k: rounded(out[t][k]) for k in ("low", "middle", "high")} | {"rough": out[t]["rough"]}
              for t in TARGETS}
    ranges["revenue"]["mode"] = out["revenue"]["mode"]
    return {
        "model_version": out["model_version"],
        "ranges": ranges,
        "comparison": out["budget"]["comparison"].get("position"),
        "drivers": {t: [d["text"] for d in drivers(out, t)] for t in TARGETS},
        "comparables": [f["id"] for f in out["comparables"]],
        "warnings": [w["code"] for w in out["warnings"]],
    }


# ---------------------------------------------------------------- rules that hold whatever the numbers


def test_the_app_models_match_their_manifest(predictor):
    assert check_manifest(FINAL_DIR)["version"] == predictor.manifest["version"]


@pytest.mark.parametrize("name", FORMS)
def test_every_output_is_complete_and_ordered(outputs, name):
    out = outputs[name]
    assert json.loads(json.dumps(out)) == out
    for t in TARGETS:
        assert out[t]["low"] <= out[t]["middle"] <= out[t]["high"]
        assert 0 < len(drivers(out, t)) <= 5 and all("_" not in d["text"] for d in drivers(out, t))
    assert out["score"]["rough"] is False and 0 <= out["score"]["low"] and out["score"]["high"] <= 10
    assert 0 < len(out["comparables"]) <= 5


@pytest.mark.parametrize("name", FORMS)
def test_comparables_are_released_before_the_planned_date(predictor, outputs, name):
    as_of = day_number(date.fromisoformat(outputs[name]["as_of"]))
    days = dict(zip(predictor.index.ids.tolist(), predictor.index.days.tolist()))
    assert all(days[f["id"]] < as_of for f in outputs[name]["comparables"])


def test_franchise_blockbuster(outputs):
    out = outputs["franchise_blockbuster"]
    assert out["revenue"]["mode"] == "given" and out["revenue"]["budget_used"] == 300_000_000
    assert out["revenue"]["middle"] > 500_000_000 and out["budget"]["comparison"]["position"] == "within"
    assert {"big_budget", "future_release"} == {w["code"] for w in out["warnings"]}
    up = {d["group"] for d in out["drivers"]["revenue"]["up"]}
    assert {"budget", "franchise", "studio"} <= up
    assert 299536 in [f["id"] for f in out["comparables"]]  # Avengers: Infinity War


def test_small_drama(outputs):
    out = outputs["small_drama"]
    assert out["revenue"]["mode"] == "estimated" and out["revenue"]["rough"] and out["budget"]["rough"]
    assert out["revenue"]["budget_used"] == pytest.approx(out["budget"]["middle"])
    assert {w["code"] for w in out["warnings"]} == {"new_actors", "future_release"}
    assert "2 of the 5 actors" in next(w["text"] for w in out["warnings"] if w["code"] == "new_actors")
    assert all(d["estimated"] for d in drivers(out, "revenue") if d["group"] == "budget")
    assert out["budget"]["middle"] < 100_000_000


def test_unknown_cast(outputs):
    out = outputs["unknown_cast"]
    assert out["revenue"]["mode"] == "given" and out["revenue"]["middle"] < 10_000_000
    assert {w["code"] for w in out["warnings"]} == {"new_director", "new_actors", "no_country", "no_studio",
                                                    "future_release"}
    assert all(d["direction"] == "down" for d in drivers(out, "budget"))
    assert any("no earlier films" in d["text"] for d in drivers(out, "budget"))


def test_the_same_form_gives_the_same_output(predictor, outputs):
    assert predictor.predict(FORMS["small_drama"]) == outputs["small_drama"]


@pytest.mark.parametrize("name", FORMS)
def test_each_prediction_takes_under_400_ms(predictor, name):
    predictor.predict(FORMS[name])  # the first call warms caches (the synopsis model loads lazily)
    times = []
    for _ in range(10):
        start = time.perf_counter()
        predictor.predict(FORMS[name])
        times.append((time.perf_counter() - start) * 1000)
    assert np.median(times) < MAX_MS and max(times) < 2 * MAX_MS


# ---------------------------------------------------------------- the snapshot


def test_outputs_match_the_golden_snapshot(outputs):
    got = {name: snapshot(out) for name, out in outputs.items()}
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_text(json.dumps(got, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    assert got == golden
