"""LightGBM models, conformal calibration and saved artifacts, on small synthetic data (no database needed)."""

import csv
import math

import numpy as np
import pandas as pd
import pytest

from ml.models.calibrate import conformal_q
from ml.models.train import MONOTONE, LgbmQuantile, load_model, model_features, save_model
from ml.models.tune import log_experiment

SMALL = {"num_leaves": 7, "min_data_in_leaf": 5, "learning_rate": 0.1}
REVENUE_FEATURES = ["log_budget", "director_revenue", "franchise_revenue", "runtime", "genre_action"]
SCORE_FEATURES = ["director_score", "runtime", "genre_drama"]


def revenue_rows(n=400, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "log_budget": rng.uniform(13, 19, n),
        "director_revenue": rng.uniform(14, 19, n),
        "franchise_revenue": np.where(rng.random(n) < 0.2, rng.uniform(17, 21, n), np.nan),
        "runtime": rng.uniform(80, 160, n),
        "genre_action": rng.integers(0, 2, n),
        "year": rng.integers(2000, 2010, n),
    })
    df["target"] = 0.9 * df["log_budget"] + 0.2 * (df["director_revenue"] - 16) + rng.normal(0, 1.0, n)
    return df


def score_rows(n=400, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "director_score": rng.uniform(4, 8.5, n),
        "runtime": rng.uniform(80, 160, n),
        "genre_drama": rng.integers(0, 2, n),
        "year": rng.integers(2000, 2010, n),
        "score_weight": np.log1p(rng.integers(50, 5000, n)),
    })
    df["target"] = np.clip(0.8 * df["director_score"] + 0.5 * df["genre_drama"] + 1 + rng.normal(0, 0.5, n), 0, 10)
    return df


@pytest.fixture(scope="module")
def revenue_model():
    return LgbmQuantile("revenue", SMALL, 60, features=REVENUE_FEATURES).fit(revenue_rows())


@pytest.fixture(scope="module")
def score_model():
    return LgbmQuantile("score", SMALL, 60, features=SCORE_FEATURES).fit(score_rows())


# ---------------------------------------------------------------- predictions


@pytest.mark.parametrize("model_name, rows", [("revenue_model", revenue_rows), ("score_model", score_rows)])
def test_low_middle_high_are_ordered(request, model_name, rows):
    p = request.getfixturevalue(model_name).predict(rows(300, seed=1))
    assert list(p.columns) == ["p10", "p50", "p90"]
    assert (p["p10"] <= p["p50"]).all() and (p["p50"] <= p["p90"]).all()


def test_score_stays_within_0_to_10(score_model):
    rows = score_rows(300, seed=1)
    rows["director_score"] = np.linspace(-5, 20, len(rows))  # far outside the training range
    p = score_model.predict(rows)
    assert p.min().min() >= 0 and p.max().max() <= 10
    wide = LgbmQuantile.apply_q(p, 50.0, "score")  # a huge correction still clips
    assert (wide["p10"] == 0).all() and (wide["p90"] == 10).all()


@pytest.mark.parametrize("column", MONOTONE)
def test_higher_monotone_input_never_lowers_revenue(revenue_model, column):
    base = revenue_rows(50, seed=2)
    base["franchise_revenue"] = base["franchise_revenue"].fillna(18.0)
    previous = None
    for value in np.linspace(10, 22, 25):  # sweep the column for every film, other inputs fixed
        rows = base.copy()
        rows[column] = value
        p = revenue_model.predict(rows)
        if previous is not None:
            assert (p.to_numpy() >= previous - 1e-9).all(), f"raising {column} lowered a prediction"
        previous = p.to_numpy()


def test_range_models_never_see_monotone_columns(revenue_model):
    assert not set(MONOTONE) & set(revenue_model.residual_features)
    for key in ("p10", "p90"):
        assert not set(MONOTONE) & set(revenue_model.models[key].feature_name())
    assert revenue_model.models["p50"].feature_name() == REVENUE_FEATURES


def test_unknown_target_is_refused():
    with pytest.raises(ValueError):
        LgbmQuantile("budget")


# ---------------------------------------------------------------- features per model


def test_score_model_never_gets_budget():
    assert "log_budget" not in model_features("score")
    assert "log_budget" not in model_features("score", ())
    assert "log_budget" in model_features("revenue", ())


def test_default_model_leaves_out_synopsis():
    for target in ("revenue", "score"):
        features = LgbmQuantile(target).features
        assert not any(c.startswith("synopsis_") or c == "has_synopsis" for c in features)
        assert any(c.startswith("synopsis_") for c in LgbmQuantile(target, drop=()).features)


@pytest.mark.parametrize("group, prefix", [("track_record", "director_"), ("themes", "theme_"),
                                           ("budget", "log_budget"), ("synopsis", "synopsis_")])
def test_dropped_groups_are_absent(group, prefix):
    full, dropped = model_features("revenue", ()), model_features("revenue", (group,))
    assert any(c.startswith(prefix) for c in full)
    assert not any(c.startswith(prefix) for c in dropped)
    assert set(dropped) < set(full)


def test_more_synopsis_numbers_add_columns():
    m = LgbmQuantile("score", drop=(), synopsis_components=32)
    assert [c for c in m.features if c.startswith("synopsis_")] == [f"synopsis_{i:02d}" for i in range(32)]
    assert m.uses_synopsis and not LgbmQuantile("score").uses_synopsis


# ---------------------------------------------------------------- conformal calibration


def test_conformal_q_hand_computed():
    y = [0.5, 1.5, -1.0, 3.0]  # range [0, 1] for every film -> scores -0.5, 0.5, 1.0, 2.0
    low, high = [0.0] * 4, [1.0] * 4
    assert conformal_q(y, low, high, 0.8) == 2.0  # ceil(5 x 0.8) = 4th smallest
    assert conformal_q(y, low, high, 0.5) == 1.0  # ceil(5 x 0.5) = 3rd smallest
    assert conformal_q([0.5], [0.0], [1.0], 0.8) == math.inf  # too few films to promise 80%


def test_conformal_q_can_narrow_too_wide_ranges():
    assert conformal_q([0.0] * 9, [-5.0] * 9, [5.0] * 9, 0.8) == -5.0


def test_calibrated_ranges_reach_the_level_on_new_data():
    rng = np.random.default_rng(0)
    calib, fresh = rng.normal(0, 1, 2000), rng.normal(0, 1, 20000)
    q = conformal_q(calib, np.full(2000, -0.5), np.full(2000, 0.5), 0.8)  # the raw range covers only ~38%
    covered = np.mean((fresh >= -0.5 - q) & (fresh <= 0.5 + q))
    assert 0.78 <= covered <= 0.83


def test_negative_q_never_crosses_the_middle():
    p = pd.DataFrame({"p10": [1.0], "p50": [2.0], "p90": [3.0]})
    out = LgbmQuantile.apply_q(p, -5.0, "revenue")
    assert out.iloc[0].tolist() == [2.0, 2.0, 2.0]


def test_q_widens_predictions(revenue_model):
    rows = revenue_rows(50, seed=3)
    plain = revenue_model.predict(rows)
    revenue_model.q = 0.4
    try:
        wide = revenue_model.predict(rows)
    finally:
        revenue_model.q = 0.0
    assert np.allclose(wide["p10"], plain["p10"] - 0.4) and np.allclose(wide["p90"], plain["p90"] + 0.4)
    assert np.allclose(wide["p50"], plain["p50"])


# ---------------------------------------------------------------- artifacts and logs


@pytest.mark.parametrize("model_name, rows", [("revenue_model", revenue_rows), ("score_model", score_rows)])
def test_saved_models_reload_with_identical_predictions(request, tmp_path, model_name, rows):
    model = request.getfixturevalue(model_name)
    train = rows()
    meta = save_model(model, train, {"mae": 1.0}, out_dir=tmp_path)
    assert meta["train_films"] == len(train) and meta["trained_on"].endswith("2000-2009")
    reloaded = load_model(model.target, out_dir=tmp_path)
    test = rows(100, seed=4)
    pd.testing.assert_frame_equal(reloaded.predict(test), model.predict(test))
    assert reloaded.features == model.features and reloaded.q == model.q


def test_experiment_log_writes_header_once(tmp_path):
    path = tmp_path / "experiments.csv"
    for trial in range(2):
        log_experiment({"target": "score", "run": "tune", "trial": trial, "settings": "{}", "n_trees": 10,
                        "fold_1": 0.5, "fold_2": 0.6, "mean": 0.55}, path)
    rows = list(csv.reader(path.open(encoding="utf-8")))
    assert rows[0][0] == "time" and len(rows) == 3 and rows[2][3] == "1"
