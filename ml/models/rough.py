"""The rough-estimate label: a per-prediction flag for money ranges that are unusually wide.

    is_rough(target, p10, p90, rule)   -> boolean per prediction (always False for score)
    fit_rule(predictions)              -> the cut-offs and what they flag, from 2016-18 predictions
    load_rule() / save_rule(rule)      -> ml/artifacts/rough_estimate.json (committed)
    uv run python -m ml.models.rough   -> measures the rule with the saved models on 2016-18 and saves it

A revenue or budget prediction is "rough" when its high end is more than CUTOFF x its low end. Each
target's cut-off is the 75th percentile of its 2016-18 range widths (revenue: budget given), rounded to
two significant figures, so about a quarter of predictions are labelled; revenue with an estimated
budget has wider ranges and is labelled more often under the same cut-off. Score gets no label: its
ranges barely vary (1.3-2.0 points) and their width hardly predicts the error (Spearman 0.09).
The rule is fitted once, before the test run, and then frozen.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROUGH_FILE = Path("ml/artifacts/rough_estimate.json")
LABELLED_TARGETS = ("revenue", "budget")
QUANTILE = 0.75  # the widest quarter of 2016-18 ranges is labelled


def _two_figures(x: float) -> float:
    digits = 1 - int(math.floor(math.log10(abs(x))))
    return round(x, digits)


def is_rough(target: str, p10, p90, rule: dict[str, Any]) -> np.ndarray:
    """True where high / low exceeds the target's cut-off (p10 and p90 in log units)."""
    width = np.asarray(p90, dtype=float) - np.asarray(p10, dtype=float)
    if target not in LABELLED_TARGETS:
        return np.zeros(len(width), dtype=bool)
    return width > math.log(rule["cutoff"][target])


def _effect(df: pd.DataFrame, p: pd.DataFrame, flag: np.ndarray) -> dict[str, float]:
    err = np.abs(df["target"].to_numpy() - p["p50"].to_numpy())
    within = err <= math.log(2)
    return {
        "films": int(len(flag)),
        "labelled_share": float(flag.mean()),
        "mae_labelled": float(err[flag].mean()),
        "mae_rest": float(err[~flag].mean()),
        "mae_ratio": float(err[flag].mean() / err[~flag].mean()),
        "within_2x_labelled": float(within[flag].mean()),
        "within_2x_rest": float(within[~flag].mean()),
    }


def fit_rule(predictions: dict[str, tuple[pd.DataFrame, pd.DataFrame]]) -> dict[str, Any]:
    """predictions: {"revenue given" | "revenue estimated" | "budget": (rows, p10/p50/p90)} on 2016-18."""
    cutoff = {}
    for target, key in (("revenue", "revenue given"), ("budget", "budget")):
        _, p = predictions[key]
        cutoff[target] = _two_figures(float(np.exp(np.quantile(p["p90"] - p["p10"], QUANTILE))))
    rule = {"cutoff": cutoff, "quantile": QUANTILE}
    rule["validation"] = {key: _effect(df, p, is_rough(key.split()[0], p["p10"], p["p90"], rule))
                          for key, (df, p) in predictions.items()}
    return rule


def save_rule(rule: dict[str, Any], path: Path = ROUGH_FILE) -> None:
    out = {**rule, "about": "high / low above cutoff -> rough estimate; fitted on 2016-18 with the <=2015 models",
           "fitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


def load_rule(path: Path = ROUGH_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    from ml.eval.splits import load
    from ml.models.chain import Chain

    sys.stdout.reconfigure(encoding="utf-8")
    chain = Chain.load()
    revenue, budget = load("revenue", "validation"), load("budget", "validation")
    rule = fit_rule({
        "revenue given": (revenue, chain.predict_revenue(revenue, budget=revenue["budget_2025"])),
        "revenue estimated": (revenue, chain.predict_revenue(revenue)),
        "budget": (budget, chain.budget.predict(budget)),
    })
    save_rule(rule)
    print(f"cut-offs: revenue {rule['cutoff']['revenue']:g}x, budget {rule['cutoff']['budget']:g}x; wrote {ROUGH_FILE}")
    for key, e in rule["validation"].items():
        print(f"  {key:18s} {e['labelled_share']:.0%} labelled; MAE log {e['mae_labelled']:.3f} vs {e['mae_rest']:.3f} "
              f"({e['mae_ratio']:.2f}x); within 2x {e['within_2x_labelled']:.0%} vs {e['within_2x_rest']:.0%}")


if __name__ == "__main__":
    main()
