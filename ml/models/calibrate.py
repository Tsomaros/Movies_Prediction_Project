"""Conformal correction of the 10th-90th ranges (conformalized quantile regression), learned on folds 1-2.

    conformal_q(y, p10, p90, level)    -> how much to widen every range so `level` of films fall inside
    calibrate(target)                  -> q from out-of-fold predictions on folds 1-2, with coverage before
                                          and after on those folds and on 2016-18
    uv run python -m ml.models.calibrate  -> ml/artifacts/{target}_calibration.json for revenue and score

For each calibration film the score is max(p10 - y, y - p90): negative when the real value is inside
the range, positive by how far it falls outside. q is the ceil((n + 1) x level)-th smallest score
(the finite-sample conformal quantile), and the calibrated range is [p10 - q, p90 + q], in log units
for revenue and score points for score. Folds 1-2 train on <=2009 / <=2012 and predict 2010-12 /
2013-15, so the calibration films are never ones the model saw; 2016-18 stays an honest check.
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
from ml.models.train import TARGETS, LgbmQuantile
from ml.models.tune import ARTIFACTS_DIR, TUNE_FOLDS, fold_sets, load_params

LEVEL = 0.80
CALIBRATION_FOLDS = TUNE_FOLDS  # folds 1-2; the <=2018 model on Day 6 uses all three


def conformal_q(y, p10, p90, level: float = LEVEL) -> float:
    scores = np.sort(np.maximum(np.asarray(p10) - np.asarray(y), np.asarray(y) - np.asarray(p90)))
    k = math.ceil((len(scores) + 1) * level)
    return float(scores[k - 1]) if k <= len(scores) else math.inf


def calibration_file(target: str) -> Path:
    return ARTIFACTS_DIR / f"{target}_calibration.json"


def load_q(target: str) -> float:
    return json.loads(calibration_file(target).read_text(encoding="utf-8"))["q"]


def _range_stats(target: str, y, p) -> dict[str, float]:
    width = score_width if target == "score" else money_width
    return {"coverage": coverage(y, p["p10"], p["p90"]), "width": width(p["p10"], p["p90"])}


def calibrate(target: str, level: float = LEVEL) -> dict[str, Any]:
    params, n_trees = load_params(target)
    folds = []
    for fold, (train, test) in zip(CALIBRATION_FOLDS, fold_sets(target)):
        p = LgbmQuantile(target, params, n_trees).fit(train).predict(test)
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
    p = LgbmQuantile(target, params, n_trees).fit(train).predict(validation)
    report["before"]["validation 2016-18"] = _range_stats(target, validation["target"], p)
    report["after"]["validation 2016-18"] = _range_stats(target, validation["target"], widened(p))

    result = {
        "target": target,
        "level": level,
        "q": q,
        "units": "score points" if target == "score" else "log 2025 $",
        "calibration_films": int(len(y)),
        "folds": [f"{f.name}: <={f.train_last} -> {f.test_first}-{f.test_last}" for f in CALIBRATION_FOLDS],
        "report": report,
        "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    calibration_file(target).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for target in TARGETS:
        start = time.perf_counter()
        r = calibrate(target)
        fmt = "{:.2f} pts" if target == "score" else "{:.1f}x"
        print(f"{target}: q = {r['q']:+.3f} {r['units']} from {r['calibration_films']:,} fold films "
              f"({time.perf_counter() - start:.0f} s); wrote {calibration_file(target)}")
        for where in r["report"]["before"]:
            b, a = r["report"]["before"][where], r["report"]["after"][where]
            print(f"  {where:20s} coverage {b['coverage']:.1%} -> {a['coverage']:.1%}   "
                  f"width {fmt.format(b['width'])} -> {fmt.format(a['width'])}")


if __name__ == "__main__":
    main()
