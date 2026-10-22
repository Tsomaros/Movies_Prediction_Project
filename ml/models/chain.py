"""The chain: revenue with the budget given, or with the budget estimated by the budget model.

    EstimatedBudgetRevenue(...).fit(train_df)  -> a revenue model plus a budget model trained on the same years
    model.predict(df)                          -> p10 / p50 / p90 revenue with log_budget replaced by the
                                                  budget model's middle prediction
    with_budget(features, log_budget)          -> a copy of the feature rows with log_budget set
    Chain.load() / chain.predict_revenue(features, budget=None)
                                               -> the saved models; "given" mode when budget (2025 $) is
                                                  passed, "estimated" mode when it is None
    predict_revenue(features, budget=None)     -> the same with the saved models, loaded once
    chain.compare_budget(features, budget)     -> "Similar films usually cost $X-Y" next to the creator's budget
    compare_budget(budget_p, budget)           -> the same from budget predictions (log 2025 $)
    format_money(dollars)                      -> "$12M", "$1.2B": two significant figures

One revenue model serves both modes; only the range correction differs. "Given" uses the Day 5
correction (ml/artifacts/revenue_calibration.json). "Estimated" uses one learned the same way on
folds 1-2, but with each fold's revenue predictions fed budgets from a budget model trained on that
fold's train years (ml/artifacts/revenue_estimated_calibration.json). The revenue range models
never see log_budget, so both modes give the same raw width and the estimated range is wider only by
its larger correction; it is never allowed to be narrower (max of the two corrections).

The budget comparison is shown even when the creator gives a budget: "similar films" are the budget
model's calibrated 10th-90th range for the same form, and the creator's budget is placed below, within
or above it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.eval.splits import through
from ml.models.train import ARTIFACTS_DIR, LgbmQuantile, load_model, meta_file

MODES = ("given", "estimated")
POSITIONS = ("below", "within", "above")  # the creator's budget against the similar-films range


def format_money(dollars: float) -> str:
    """Two significant figures with K / M / B: 12_345_678 -> "$12M", 1_234_567_890 -> "$1.2B"."""
    value = float(f"{dollars:.2g}")
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= size:
            return f"${value / size:g}{suffix}"
    return f"${value:g}"


def compare_budget(budget_p: pd.DataFrame, budget=None) -> pd.DataFrame:
    """budget_p: the budget model's p10 / p50 / p90 (log 2025 $); budget: 2025 dollars, one value or one per row.

    Columns: low, middle, high (2025 $), text ("Similar films usually cost $X-Y"), and when a budget is
    given: budget, position (below / within / above) and ratio (budget / middle)."""
    out = pd.DataFrame({"low": np.exp(budget_p["p10"]), "middle": np.exp(budget_p["p50"]),
                        "high": np.exp(budget_p["p90"])}, index=budget_p.index)
    out["text"] = [f"Similar films usually cost {format_money(lo)}–{format_money(hi)}"
                   for lo, hi in zip(out["low"], out["high"])]
    if budget is not None:
        b = np.broadcast_to(np.asarray(budget, dtype=float), len(out))
        out["budget"] = b
        out["position"] = np.select([b < out["low"], b > out["high"]], ["below", "above"], "within")
        out["ratio"] = b / out["middle"]
    return out


def with_budget(features: pd.DataFrame, log_budget) -> pd.DataFrame:
    out = features.copy()
    out["log_budget"] = np.broadcast_to(np.asarray(log_budget, dtype=float), len(out)).copy()
    return out


class EstimatedBudgetRevenue:
    """Revenue as the app sees it without a budget: the revenue model fed the budget model's estimate.

    fit(train) trains the revenue model on train's real budgets and the budget model on every
    v_train_budget film released up to the last year in train, so in each backtest fold both models
    see the same years and nothing from the fold's test years."""

    def __init__(self, revenue_params: dict[str, Any], revenue_trees: int, budget_params: dict[str, Any],
                 budget_trees: int, q: float = 0.0, name: str = "LightGBM, budget estimated"):
        self.revenue = LgbmQuantile("revenue", revenue_params, revenue_trees, q=q)
        self.budget = LgbmQuantile("budget", budget_params, budget_trees)
        self.q = q
        self.name = name
        if q:
            self.backtest_note = ("Range correction learned on folds 1-2 with estimated budgets, so coverage there is "
                                  "fitted, not tested; fold 3 (2016-18) is the honest check.")

    def fit(self, train: pd.DataFrame) -> EstimatedBudgetRevenue:
        self.revenue.fit(train)
        self.budget.fit(through("budget", int(train["year"].max())))
        return self

    def estimate(self, df: pd.DataFrame) -> np.ndarray:
        """The budget model's middle prediction (log 2025 $) for each row."""
        return self.budget.predict(df)["p50"].to_numpy()

    def predict(self, df: pd.DataFrame, q: float | None = None) -> pd.DataFrame:
        return self.revenue.predict(with_budget(df, self.estimate(df)), q=self.q if q is None else q)


@dataclass
class Chain:
    revenue: LgbmQuantile
    budget: LgbmQuantile
    q: dict[str, float]  # mode -> range correction (log units)

    @classmethod
    def load(cls, out_dir: Path = ARTIFACTS_DIR) -> Chain:
        """The saved models in out_dir: ml/artifacts (<=2015, `make train`) or ml/artifacts/final (all data).

        The all-data revenue model carries its estimated-mode correction in its metadata (q_estimated)."""
        from ml.models.calibrate import load_q  # calibrate imports this module

        revenue, budget = load_model("revenue", out_dir), load_model("budget", out_dir)
        meta = json.loads(meta_file("revenue", out_dir).read_text(encoding="utf-8"))
        given = revenue.q
        estimated = meta["q_estimated"] if "q_estimated" in meta else load_q("revenue", estimated=True)
        return cls(revenue, budget, {"given": given, "estimated": max(estimated, given)})

    def predict_revenue(self, features: pd.DataFrame, budget=None) -> pd.DataFrame:
        """Revenue p10 / p50 / p90 (log 2025 $). budget: 2025 dollars, one value or one per row; None estimates it.

        The result's attrs say which mode was used and the log budget fed to the revenue model."""
        if budget is None:
            mode, log_budget = "estimated", self.budget.predict(features)["p50"].to_numpy()
        else:
            mode, log_budget = "given", np.log(np.broadcast_to(np.asarray(budget, dtype=float), len(features)))
        out = self.revenue.predict(with_budget(features, log_budget), q=self.q[mode])
        out.attrs.update(mode=mode, log_budget=np.asarray(log_budget, dtype=float))
        return out

    def compare_budget(self, features: pd.DataFrame, budget=None) -> pd.DataFrame:
        return compare_budget(self.budget.predict(features), budget)


_CHAIN: Chain | None = None


def predict_revenue(features: pd.DataFrame, budget=None) -> pd.DataFrame:
    global _CHAIN
    if _CHAIN is None:
        _CHAIN = Chain.load()
    return _CHAIN.predict_revenue(features, budget)
