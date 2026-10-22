"""Optuna tuning of the middle (p50) model on backtest folds 1-2, which both stay inside train (<=2015).

    uv run python -m ml.models.tune [--minutes 15] [--target revenue|budget|score]
        -> ml/artifacts/{target}_params.json (best settings + tree count), every trial in reports/experiments.csv

Each trial trains the middle model on a fold's train years and stops adding trees when MAE on the
fold's test years stops improving (100 rounds of patience). The trial's value is the mean MAE over
the two folds (log MAE for revenue and budget, plain MAE for score, the Day 4 selection metrics) and its tree
count is the mean of the two stopping points. The final model trains on all of train with that fixed
count, and the 10th / 90th models reuse the same settings, so 2016-18 never helps fit or stop anything.
It tunes the model's default features (DEFAULT_DROP). The saved Day 5 settings were tuned before the
ablation dropped the synopsis numbers, with them included, and before revenue gained the Day 6 budget
track record; they are reused as they are. The budget model was tuned on Day 6 with its own default features.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd

from ml.eval.backtest import refit_synopsis
from ml.eval.splits import FOLDS, fold_data
from ml.models.train import (ARTIFACTS_DIR, DEFAULT_DROP, DEFAULT_PARAMS, MONOTONE, TARGETS, _lgb_params,
                             model_features)

TUNE_FOLDS = FOLDS[:2]  # fold 3 tests on 2016-18 = validation, so it stays out
MAX_TREES = 3000
PATIENCE = 100
EXPERIMENTS_FILE = Path("reports/experiments.csv")
EXPERIMENT_COLUMNS = ["time", "target", "run", "trial", "settings", "n_trees", "fold_1", "fold_2", "mean"]


def params_file(target: str) -> Path:
    return ARTIFACTS_DIR / f"{target}_params.json"


def load_params(target: str) -> tuple[dict[str, Any], int]:
    saved = json.loads(params_file(target).read_text(encoding="utf-8"))
    return saved["params"], saved["n_trees"]


def log_experiment(row: dict[str, Any], path: Path | None = None) -> None:
    path = path or EXPERIMENTS_FILE
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPERIMENT_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row})


def fold_sets(target: str) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """(train, test) per tuning fold, with synopsis numbers from a PCA fitted on that fold's train years."""
    return [refit_synopsis(*fold_data(target, fold), fold.train_last) for fold in TUNE_FOLDS]


def middle_params(target: str, params: dict[str, Any], features: list[str]) -> dict[str, Any]:
    if target != "revenue":
        out = _lgb_params(params, "quantile", 0.5)
    else:
        out = _lgb_params(params, "huber")
        out["monotone_constraints"] = [1 if c in MONOTONE else 0 for c in features]
    out["metric"] = "l1"
    return out


def fit_fold(target: str, params: dict[str, Any], train: pd.DataFrame, test: pd.DataFrame,
             features: list[str]) -> tuple[float, int]:
    """Middle model on one fold with early stopping; returns (test MAE, best tree count)."""
    weight = train["score_weight"].to_numpy() if target == "score" else None
    dtrain = lgb.Dataset(train[features], train["target"].to_numpy(), weight=weight)
    dtest = lgb.Dataset(test[features], test["target"].to_numpy(), reference=dtrain)  # unweighted: plain MAE
    booster = lgb.train(middle_params(target, params, features), dtrain, num_boost_round=MAX_TREES,
                        valid_sets=[dtest], callbacks=[lgb.early_stopping(PATIENCE, verbose=False)])
    pred = booster.predict(test[features], num_iteration=booster.best_iteration)
    return float(np.mean(np.abs(test["target"].to_numpy() - pred))), booster.best_iteration


def evaluate_settings(target: str, params: dict[str, Any], folds, features: list[str]) -> tuple[list[float], int]:
    results = [fit_fold(target, params, train, test, features) for train, test in folds]
    return [r[0] for r in results], int(round(np.mean([r[1] for r in results])))


def suggest(trial: optuna.Trial, target: str) -> dict[str, Any]:
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 8, 128, log=True),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 200, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.4, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": 1,
        "lambda_l1": trial.suggest_float("lambda_l1", 1e-3, 10.0, log=True),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
    }
    if target == "revenue":
        params["huber_delta"] = trial.suggest_float("huber_delta", 0.3, 3.0, log=True)
    return params


def tune(target: str, minutes: float) -> dict[str, Any]:
    features = model_features(target, DEFAULT_DROP[target])
    folds = fold_sets(target)

    def record(run: str, trial: int, params: dict[str, Any], maes: list[float], n_trees: int) -> None:
        log_experiment({"target": target, "run": run, "trial": trial, "settings": json.dumps(params),
                        "n_trees": n_trees, "fold_1": round(maes[0], 4), "fold_2": round(maes[1], 4),
                        "mean": round(float(np.mean(maes)), 4)})

    default = {k: v for k, v in DEFAULT_PARAMS.items() if target == "revenue" or k != "huber_delta"}

    def objective(trial: optuna.Trial) -> float:
        params = suggest(trial, target)
        maes, n_trees = evaluate_settings(target, params, folds, features)
        trial.set_user_attr("params", params)
        trial.set_user_attr("n_trees", n_trees)
        trial.set_user_attr("maes", maes)
        record("tune", trial.number, params, maes, n_trees)
        return float(np.mean(maes))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
    # trial 0 = the defaults (L1/L2 at the 0.001 floor of their log range instead of 0)
    study.enqueue_trial({k: max(v, 1e-3) if k.startswith("lambda") else v
                         for k, v in default.items() if k != "bagging_freq"})
    study.optimize(objective, timeout=minutes * 60)

    best, first = study.best_trial, study.trials[0]
    result = {
        "target": target,
        "params": best.user_attrs["params"],
        "n_trees": best.user_attrs["n_trees"],
        "fold_mae": best.user_attrs["maes"],
        "mean_mae": best.value,
        "default": {"params": first.user_attrs["params"], "n_trees": first.user_attrs["n_trees"],
                    "fold_mae": first.user_attrs["maes"], "mean_mae": first.value},
        "trials": len(study.trials),
        "minutes": minutes,
        "folds": [f"{f.name}: <={f.train_last} -> {f.test_first}-{f.test_last}" for f in TUNE_FOLDS],
        "tuned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    params_file(target).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=float, default=15.0, help="time limit per target")
    parser.add_argument("--target", choices=TARGETS, action="append", help="default: every target")
    args = parser.parse_args()
    for target in args.target or TARGETS:
        start = time.perf_counter()
        r = tune(target, args.minutes)
        d = r["default"]
        print(f"{target}: {r['trials']} trials in {time.perf_counter() - start:.0f} s; folds 1-2 MAE "
              f"{r['mean_mae']:.4f} ({r['n_trees']} trees) vs defaults {d['mean_mae']:.4f} ({d['n_trees']} trees); "
              f"wrote {params_file(target)}")


if __name__ == "__main__":
    main()
