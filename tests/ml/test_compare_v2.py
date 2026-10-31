"""V1.5's v1-vs-v2 comparison: the keep rule and the like-for-like join, on tiny frames (no database)."""

import numpy as np
import pandas as pd
import pytest

from ml.eval.compare_v2 import keep_rule, like_for_like, summarise
from ml.eval.learning_curve import sample_train


def _m(validation, backtest_mean, backtest_std=0.02, coverage=0.80):
    return {"validation": validation, "backtest_mean": backtest_mean, "backtest_std": backtest_std,
            "coverage": coverage}


V1 = {"revenue": _m(1.09, 1.12), "budget": _m(0.61, 0.66, 0.03), "score": _m(0.50, 0.51, 0.02)}


def test_keep_when_revenue_better_on_both_and_coverage_ok():
    v2 = {**V1, "revenue": _m(1.05, 1.10, coverage=0.80)}
    keep, reasons = keep_rule(V1, v2)
    assert keep and reasons == []


def test_reject_when_revenue_backtest_worse():
    v2 = {**V1, "revenue": _m(1.05, 1.15, coverage=0.80)}
    keep, reasons = keep_rule(V1, v2)
    assert not keep
    assert any("revenue" in r and "backtest" in r for r in reasons)
    assert not any("validation" in r and "revenue" in r and "coverage" not in r for r in reasons)


def test_reject_when_revenue_coverage_out_of_range():
    v2 = {**V1, "revenue": _m(1.05, 1.10, coverage=0.76)}
    keep, reasons = keep_rule(V1, v2)
    assert not keep
    assert any("coverage" in r for r in reasons)


def test_coverage_bounds_are_inclusive():
    for c in (0.77, 0.83):
        assert keep_rule(V1, {**V1, "revenue": _m(1.05, 1.10, coverage=c)})[0]


def test_reject_when_score_worse_by_more_than_its_backtest_std():
    v2 = {**V1, "revenue": _m(1.05, 1.10), "score": _m(0.50 + 0.03, 0.51)}
    keep, reasons = keep_rule(V1, v2)
    assert not keep
    assert any(r.startswith("score") for r in reasons)


def test_keep_when_score_worse_by_less_than_its_backtest_std():
    v2 = {**V1, "revenue": _m(1.05, 1.10), "score": _m(0.50 + 0.01, 0.51 + 0.01)}
    keep, reasons = keep_rule(V1, v2)
    assert keep, reasons


def test_revenue_estimated_is_not_part_of_the_verdict():
    v2 = {**V1, "revenue": _m(1.05, 1.10), "revenue_estimated": _m(9.0, 9.0, coverage=0.1)}
    assert keep_rule({**V1, "revenue_estimated": _m(1.1, 1.2)}, v2)[0]


def _frame(target_name, ids, targets, p50, part="validation"):
    n = len(ids)
    return pd.DataFrame({"target_name": target_name, "movie_id": ids, "part": part, "target": targets,
                         "score_weight": np.ones(n), "p10": np.asarray(p50) - 1, "p50": p50,
                         "p90": np.asarray(p50) + 1})


def test_like_for_like_uses_shared_ids():
    # id 1 only in v1 (newly flagged in v2), id 4 only in v2 (newly kept); id 3's target changed in v2
    v1 = _frame("budget", [1, 2, 3], [10.0, 11.0, 12.0], [10.5, 11.0, 12.0])
    v2 = _frame("budget", [2, 3, 4], [11.0, 13.0, 9.0], [11.5, 13.0, 9.0])
    shared, counts = like_for_like(v1, v2)
    assert sorted(shared["movie_id"]) == [2, 3]
    assert counts["missing_from_v2"] == {"budget": {"validation": 1}}
    assert counts["new_in_v2"] == {"budget": {"validation": 1}}
    assert counts["target_changed"] == {"budget": {"validation": 1}}
    # both versions are scored against v2's target on the shared ids
    row3 = shared.set_index("movie_id").loc[3]
    assert row3["target"] == 13.0
    assert row3["v1_p50"] == 12.0 and row3["v2_p50"] == 13.0
    v1_metrics = summarise("budget", shared, "v1")
    v2_metrics = summarise("budget", shared, "v2")
    assert v1_metrics["n"] == 2
    assert v1_metrics["validation"] == pytest.approx((0.0 + 1.0) / 2)  # |11-11|, |12-13|
    assert v2_metrics["validation"] == pytest.approx((0.5 + 0.0) / 2)


def test_summarise_backtest_mean_and_std_over_folds():
    parts = [_frame("score", [i], [5.0], [5.0 + e], part=p)
             for i, (p, e) in enumerate([("validation", 0.3), ("fold 1", 0.1), ("fold 2", 0.2), ("fold 3", 0.3)])]
    df = pd.concat(parts).rename(columns={c: f"v1_{c}" for c in ("p10", "p50", "p90")})
    m = summarise("score", df, "v1")
    assert m["validation"] == pytest.approx(0.3)
    assert m["backtest_mean"] == pytest.approx(0.2)
    assert m["backtest_std"] == pytest.approx(np.std([0.1, 0.2, 0.3]))


def test_sample_train_is_seeded_and_sized():
    df = pd.DataFrame({"movie_id": range(100)})
    a, b = sample_train(df, 0.25, 1), sample_train(df, 0.25, 1)
    assert len(a) == 25 and a["movie_id"].tolist() == b["movie_id"].tolist()
    assert len(sample_train(df, 1.0, 2)) == 100
