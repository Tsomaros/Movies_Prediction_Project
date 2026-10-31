"""Learning curve: does a model still gain from more films? The middle model only, on samples of the train years.

    sample_train(train, fraction, seed)  -> a seeded random sample of that share of the train films
    fit_middle(target, train)            -> the p50 LightGBM booster, as LgbmQuantile.fit trains it (tuned
                                            params, same features; revenue: monotone Huber; budget: quantile 0.5;
                                            score: quantile 0.5 weighted by score_weight)
    middle_mae(target, train, validation)-> validation MAE of that middle (MAE log for money, MAE for score)
    curve(targets)                       -> rows {target, fraction, films, seed, mae}

Fractions FRACTIONS of the train films (<=2015), seeds SEEDS, scored on validation (2016-18), which is only
predicted, never fitted on. The tree count stays the tuned full-data one at every fraction. At fraction 1.0 every
seed takes the same films (and LightGBM's own seed is fixed), so that point is fitted once. No backtest here.

CLI: uv run python -m ml.eval.learning_curve [--targets revenue budget score] [--out reports/learning_curve.md]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from ml.eval.metrics import mae
from ml.eval.splits import load

FRACTIONS = (0.15, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0)
SEEDS = (0, 1, 2)
TARGETS = ("revenue", "budget", "score")
OUT_FILE = Path("reports/learning_curve.md")


def sample_train(train: pd.DataFrame, fraction: float, seed: int) -> pd.DataFrame:
    if fraction >= 1.0:
        return train.reset_index(drop=True)
    n = max(1, round(fraction * len(train)))
    return train.sample(n=n, random_state=seed).reset_index(drop=True)


def _model(target: str):
    from ml.models.train import LgbmQuantile
    from ml.models.tune import load_params

    return LgbmQuantile(target, *load_params(target))


def fit_middle(target: str, train: pd.DataFrame) -> tuple[lgb.Booster, list[str]]:
    from ml.models.train import MONOTONE, _lgb_params, _train

    model = _model(target)
    X, y = train[model.features], train["target"].to_numpy()
    if target == "revenue":
        params = _lgb_params(model.params, "huber")
        if model.monotone:
            params["monotone_constraints"] = [1 if c in MONOTONE else 0 for c in model.features]
        return _train(X, y, params, model.n_trees), model.features
    w = train["score_weight"].to_numpy() if target == "score" else None
    return _train(X, y, _lgb_params(model.params, "quantile", 0.5), model.n_trees, w), model.features


def middle_mae(target: str, train: pd.DataFrame, validation: pd.DataFrame) -> float:
    booster, features = fit_middle(target, train)
    return mae(validation["target"].to_numpy(), booster.predict(validation[features]))


def curve(targets: tuple[str, ...] = TARGETS) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        train, validation = load(target, "train"), load(target, "validation")
        for fraction in FRACTIONS:
            for seed in SEEDS[:1] if fraction >= 1.0 else SEEDS:
                sample = sample_train(train, fraction, seed)
                rows.append({"target": target, "fraction": fraction, "films": len(sample), "seed": seed,
                             "mae": middle_mae(target, sample, validation)})
                print(f"{target:8s} {fraction:.2f} seed {seed}: {len(sample):,} films, MAE {rows[-1]['mae']:.4f}")
    return rows


def write(rows: list[dict[str, Any]], out: Path = OUT_FILE) -> None:
    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# Learning curve", "",
             f"_Generated {stamp} by `uv run python -m ml.eval.learning_curve`. The middle (p50) LightGBM with the "
             f"tuned settings, fitted on a random share of the train films (≤2015, seeds {', '.join(map(str, SEEDS))}) "
             "and scored on validation (2016–18). MAE log for revenue and budget, MAE in points for score; "
             "the spread is the std over seeds (one fit at 100%)._", ""]
    for target, g in df.groupby("target", sort=False):
        lines += [f"## {target}", "", "| Share of train | Films | MAE (mean) | Spread (std) |", "| --- | --- | --- | --- |"]
        for fraction, f in g.groupby("fraction"):
            lines.append(f"| {fraction:.0%} | {int(f['films'].iloc[0]):,} | {f['mae'].mean():.3f} | "
                         f"{np.std(f['mae'], ddof=0):.3f} |")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--targets", nargs="+", choices=TARGETS, default=list(TARGETS))
    parser.add_argument("--out", type=Path, default=OUT_FILE)
    args = parser.parse_args()
    start = time.perf_counter()
    write(curve(tuple(args.targets)), args.out)
    print(f"wrote {args.out} ({time.perf_counter() - start:.0f} s)")


if __name__ == "__main__":
    main()
