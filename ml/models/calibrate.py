"""Conformal correction of the 10th-90th ranges (conformalized quantile regression), learned on folds 1-2.

    conformal_q(y, p10, p90, level)    -> how much to widen every range so `level` of films fall inside
    calibrate(target)                  -> q from out-of-fold predictions on folds 1-2, with coverage before
                                          and after on those folds and on 2016-18
    calibrate("revenue", estimated=True) -> the same for revenue fed estimated budgets (ml.models.chain)
    uv run python -m ml.models.calibrate  -> ml/artifacts/{target}_calibration.json for revenue, budget and score,
                                          plus revenue_estimated_calibration.json

For each calibration film the score is max(p10 - y, y - p90): negative when the real value is inside
the range, positive by how far it falls outside. q is the ceil((n + 1) x level)-th smallest score
(the finite-sample conformal quantile), and the calibrated range is [p10 - q, p90 + q], in log units
for revenue and score points for score. Folds 1-2 train on <=2009 / <=2012 and predict 2010-12 /
2013-15, so the calibration films are never ones the model saw; 2016-18 stays an honest check.
In estimated mode each fold also trains a budget model on its own train years and the revenue model
predicts from that model's budget instead of the real one, which is what the app does without a budget.
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ml.eval.metrics import coverage, money_width, score_width
from ml.eval.splits import load
from ml.models.chain import EstimatedBudgetRevenue
from ml.models.train import TARGETS, LgbmQuantile
from ml.models.tune import ARTIFACTS_DIR, TUNE_FOLDS, fold_sets, load_params

LEVEL = 0.80
CALIBRATION_FOLDS = TUNE_FOLDS  # folds 1-2; the <=2018 model on Day 6 uses all three


def conformal_q(y, p10, p90, level: float = LEVEL) -> float:
    scores = np.sort(np.maximum(np.asarray(p10) - np.asarray(y), np.asarray(y) - np.asarray(p90)))
    k = math.ceil((len(scores) + 1) * level)
    return float(scores[k - 1]) if k <= len(scores) else math.inf


def calibration_file(target: str, estimated: bool = False) -> Path:
    return ARTIFACTS_DIR / f"{target}{'_estimated' if estimated else ''}_calibration.json"


def load_q(target: str, estimated: bool = False) -> float:
    return json.loads(calibration_file(target, estimated).read_text(encoding="utf-8"))["q"]


def uncalibrated(target: str, estimated: bool = False):
    """The tuned model with no range correction; estimated=True is the revenue chain."""
    params, n_trees = load_params(target)
    if estimated:
        return EstimatedBudgetRevenue(params, n_trees, *load_params("budget"))
    return LgbmQuantile(target, params, n_trees)


def _range_stats(target: str, y, p) -> dict[str, float]:
    width = score_width if target == "score" else money_width
    return {"coverage": coverage(y, p["p10"], p["p90"]), "width": width(p["p10"], p["p90"])}


def calibrate(target: str, level: float = LEVEL, estimated: bool = False) -> dict[str, Any]:
    if estimated and target != "revenue":
        raise ValueError("only revenue has an estimated-budget mode")
    folds = []
    for fold, (train, test) in zip(CALIBRATION_FOLDS, fold_sets(target)):
        p = uncalibrated(target, estimated).fit(train).predict(test)
        folds.append({"fold": fold.name, "test_years": f"{fold.test_first}-{fold.test_last}",
                      "y": test["target"].to_numpy(), "p": p})
    y = np.concatenate([f["y"] for f in folds])
    q = conformal_q(y, np.concatenate([f["p"]["p10"] for f in folds]),
                    np.concatenate([f["p"]["p90"] for f in folds]), level)

    def widened(p):
        return LgbmQuantile.apply_q(p, q, target)

    report = {"before": {}, "after": {}}
    for f in folds:
        report["before"][f["fold"]] = _range_stats(target, f["y"], f["p"])
        report["after"][f["fold"]] = _range_stats(target, f["y"], widened(f["p"]))

    train, validation = load(target, "train"), load(target, "validation")
    p = uncalibrated(target, estimated).fit(train).predict(validation)
    report["before"]["validation 2016-18"] = _range_stats(target, validation["target"], p)
    report["after"]["validation 2016-18"] = _range_stats(target, validation["target"], widened(p))

    result = {
        "target": target,
        "mode": "budget estimated" if estimated else ("budget given" if target == "revenue" else None),
        "level": level,
        "q": q,
        "units": "score points" if target == "score" else "log 2025 $",
        "calibration_films": int(len(y)),
        "folds": [f"{f.name}: <={f.train_last} -> {f.test_first}-{f.test_last}" for f in CALIBRATION_FOLDS],
        "report": report,
        "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    calibration_file(target, estimated).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for target, estimated in [(t, False) for t in TARGETS] + [("revenue", True)]:
        start = time.perf_counter()
        r = calibrate(target, estimated=estimated)
        fmt = "{:.2f} pts" if target == "score" else "{:.1f}x"
        label = f"{target} ({r['mode']})" if r["mode"] else target
        print(f"{label}: q = {r['q']:+.3f} {r['units']} from {r['calibration_films']:,} fold films "
              f"({time.perf_counter() - start:.0f} s); wrote {calibration_file(target, estimated)}")
        for where in r["report"]["before"]:
            b, a = r["report"]["before"][where], r["report"]["after"][where]
            print(f"  {where:20s} coverage {b['coverage']:.1%} -> {a['coverage']:.1%}   "
                  f"width {fmt.format(b['width'])} -> {fmt.format(a['width'])}")


if __name__ == "__main__":
    main()
