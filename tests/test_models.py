"""LightGBM models, conformal calibration and saved artifacts, on small synthetic data (no database needed)."""

import csv
import math

import numpy as np
import pandas as pd
import pytest

from ml.features.history import BUDGET_FEATURES
from ml.models.calibrate import conformal_q
from ml.models.chain import Chain, compare_budget, format_money, with_budget
from ml.models.rough import fit_rule, is_rough
from ml.models.train import MONOTONE, LgbmQuantile, load_model, model_features, save_model
from ml.models.tune import log_experiment

SMALL = {"num_leaves": 7, "min_data_in_leaf": 5, "learning_rate": 0.1}
REVENUE_FEATURES = ["log_budget", "director_revenue", "franchise_revenue", "runtime", "genre_action"]
SCORE_FEATURES = ["director_score", "runtime", "genre_drama"]
BUDGET_MODEL_FEATURES = ["director_budget", "company_budget", "runtime", "genre_action"]


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


def budget_rows(n=400, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "director_budget": rng.uniform(14, 19, n),
        "company_budget": rng.uniform(14, 19, n),
        "runtime": rng.uniform(80, 160, n),
        "genre_action": rng.integers(0, 2, n),
        "year": rng.integers(2000, 2010, n),
    })
    df["target"] = 0.5 * df["director_budget"] + 0.4 * df["company_budget"] + 0.5 * df["genre_action"] \
        + rng.normal(0, 0.8, n)
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
def budget_model():
    return LgbmQuantile("budget", SMALL, 60, features=BUDGET_MODEL_FEATURES).fit(budget_rows())


@pytest.fixture(scope="module")
def score_model():
    return LgbmQuantile("score", SMALL, 60, features=SCORE_FEATURES).fit(score_rows())


# ---------------------------------------------------------------- predictions


MODELS = [("revenue_model", revenue_rows), ("budget_model", budget_rows), ("score_model", score_rows)]


@pytest.mark.parametrize("model_name, rows", MODELS)
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


def test_budget_model_is_three_plain_quantile_models(budget_model):
    assert set(budget_model.models) == {"p10", "p50", "p90"} and not budget_model.monotone
    for key in ("p10", "p50", "p90"):
        assert budget_model.models[key].feature_name() == BUDGET_MODEL_FEATURES
    p = budget_model.predict(budget_rows(300, seed=1))
    assert (p["p90"] - p["p10"]).std() > 0  # each film gets its own range width


def test_unknown_target_is_refused():
    with pytest.raises(ValueError):
        LgbmQuantile("popularity")


# ---------------------------------------------------------------- features per model


def test_score_model_never_gets_budget():
    assert "log_budget" not in model_features("score")
    assert "log_budget" not in model_features("score", ())
    assert "log_budget" in model_features("revenue", ())


def test_budget_model_never_gets_its_own_target():
    assert "log_budget" not in model_features("budget", ()) and "log_budget" not in LgbmQuantile("budget").features
    assert set(BUDGET_FEATURES) <= set(LgbmQuantile("budget").features)  # but every earlier budget


def test_default_model_leaves_out_synopsis():
    for target in ("revenue", "budget", "score"):
        features = LgbmQuantile(target).features
        assert not any(c.startswith("synopsis_") or c == "has_synopsis" for c in features)
        assert any(c.startswith("synopsis_") for c in LgbmQuantile(target, drop=()).features)


def test_budget_track_record_is_in_revenue_but_not_score():
    assert "company_budget" in LgbmQuantile("revenue").features
    assert not any(c in LgbmQuantile("score").features for c in BUDGET_FEATURES)


@pytest.mark.parametrize("group, prefix", [("track_record", "director_n_films"), ("themes", "theme_"),
                                           ("budget", "log_budget"), ("synopsis", "synopsis_"),
                                           ("budget_history", "company_budget")])
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


# ---------------------------------------------------------------- the chain (budget given / estimated)


@pytest.fixture
def chain(revenue_model, budget_model):
    return Chain(revenue_model, budget_model, {"given": 0.2, "estimated": 0.5})


def chain_rows(n=100, seed=5):
    """Feature rows both small models can read; log_budget is the creator's own (or missing)."""
    rows = revenue_rows(n, seed)
    b = budget_rows(n, seed)
    rows[["director_budget", "company_budget"]] = b[["director_budget", "company_budget"]]
    return rows


def test_given_mode_uses_the_creators_budget(chain, revenue_model):
    rows = chain_rows()
    p = chain.predict_revenue(rows, budget=50_000_000)
    expected = revenue_model.predict(with_budget(rows, math.log(50_000_000)), q=0.2)
    pd.testing.assert_frame_equal(p, expected)
    assert p.attrs["mode"] == "given"
    per_row = chain.predict_revenue(rows, budget=np.exp(rows["log_budget"]))  # one budget per film
    pd.testing.assert_frame_equal(per_row, revenue_model.predict(rows, q=0.2))


def test_estimated_mode_feeds_the_budget_models_middle(chain, revenue_model, budget_model):
    rows = chain_rows()
    p = chain.predict_revenue(rows)
    estimate = budget_model.predict(rows)["p50"].to_numpy()
    pd.testing.assert_frame_equal(p, revenue_model.predict(with_budget(rows, estimate), q=0.5))
    assert p.attrs["mode"] == "estimated" and np.allclose(p.attrs["log_budget"], estimate)
    # A missing or stray log_budget in the features never leaks into estimated mode.
    pd.testing.assert_frame_equal(chain.predict_revenue(rows.assign(log_budget=np.nan)), p)


def test_estimated_mode_is_never_narrower_than_given(chain):
    rows = chain_rows()
    given = chain.predict_revenue(rows, budget=np.exp(chain.predict_revenue(rows).attrs["log_budget"]))
    estimated = chain.predict_revenue(rows)
    assert np.allclose(given["p50"], estimated["p50"])  # same budget in, same middle out
    assert ((estimated["p90"] - estimated["p10"]) >= (given["p90"] - given["p10"]) - 1e-9).all()


@pytest.mark.parametrize("dollars, text", [(12_345_678, "$12M"), (1_234_567_890, "$1.2B"), (999_999, "$1M"),
                                           (45_600, "$46K"), (150_000_000, "$150M"), (800, "$800")])
def test_format_money_uses_two_significant_figures(dollars, text):
    assert format_money(dollars) == text


def test_budget_comparison_places_the_creators_budget():
    p = pd.DataFrame({"p10": np.log([10e6] * 3), "p50": np.log([20e6] * 3), "p90": np.log([40e6] * 3)})
    out = compare_budget(p, [5e6, 25e6, 90e6])
    assert out["text"].iloc[0] == "Similar films usually cost $10M–$40M"
    assert out["position"].tolist() == ["below", "within", "above"]
    assert out["ratio"].tolist() == pytest.approx([0.25, 1.25, 4.5])
    assert out[["low", "middle", "high"]].iloc[0].tolist() == pytest.approx([10e6, 20e6, 40e6])
    shown = compare_budget(p)  # no budget given: the range is still shown
    assert "position" not in shown and shown["text"].iloc[0] == out["text"].iloc[0]


def test_chain_budget_comparison_uses_the_budget_models_range(chain, budget_model):
    rows = chain_rows()
    out = chain.compare_budget(rows, budget=30e6)
    assert np.allclose(np.log(out["middle"]), budget_model.predict(rows)["p50"])
    assert (out["low"] <= out["middle"]).all() and (out["middle"] <= out["high"]).all()


# ---------------------------------------------------------------- rough-estimate label


def test_rough_label_uses_high_over_low_and_skips_score():
    rule = {"cutoff": {"revenue": 81.0, "budget": 12.0}}
    p10, p90 = np.log([1e6, 1e6, 1e6]), np.log([80e6, 82e6, 11e6])  # 80x, 82x, 11x
    assert is_rough("revenue", p10, p90, rule).tolist() == [False, True, False]
    assert is_rough("budget", p10, p90, rule).tolist() == [True, True, False]
    assert not is_rough("score", [3.0, 1.0], [9.0, 9.5], rule).any()


def test_rough_rule_labels_the_widest_quarter_with_a_rounded_cutoff():
    rng = np.random.default_rng(0)
    n = 1000
    widths = rng.uniform(np.log(2), np.log(200), n)
    df = pd.DataFrame({"target": rng.normal(0, 1, n) * widths / 4})  # wider ranges, bigger errors
    p = pd.DataFrame({"p10": -widths / 2, "p50": 0.0, "p90": widths / 2})
    rule = fit_rule({"revenue given": (df, p), "revenue estimated": (df, p), "budget": (df, p)})
    raw = float(np.exp(np.quantile(widths, 0.75)))
    assert rule["cutoff"]["revenue"] == pytest.approx(float(f"{raw:.2g}"))
    v = rule["validation"]["budget"]
    assert v["labelled_share"] == pytest.approx(0.25, abs=0.02) and v["mae_ratio"] > 1


# ---------------------------------------------------------------- artifacts and logs


@pytest.mark.parametrize("model_name, rows", MODELS)
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
