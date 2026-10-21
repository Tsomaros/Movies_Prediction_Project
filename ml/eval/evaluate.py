"""The evaluation harness: every model, baseline or not, goes through evaluate().

    evaluate(model_factory, target)          -> {"name", "target", "validation", "breakdowns", "backtest"}
    score(target, df, predictions)           -> the metrics for one set of predictions (ml.eval.metrics)
    breakdown_groups(target, df)             -> {breakdown: {group: boolean mask}}

A model is anything with fit(train_df) and predict(df) -> p10 / p50 / p90 (see ml.models.baselines).
It is fitted on the train split and scored on validation; the test split is never touched here.

Breakdowns (validation): budget size (revenue and budget only), English vs other languages,
new vs experienced director, franchise (sequel) vs original.

CLI: uv run python -m ml.eval.evaluate   (B0-B2 for every target and LightGBM for revenue and score
                                          -> reports/metrics.json, metrics.md, breakdowns.md, backtest.md)
LightGBM needs `make tune` and the calibration (ml.models.calibrate) to have run first.
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from ml.eval.metrics import money_metrics, score_metrics
from ml.eval.splits import load

BUDGET_BINS = [0, 10e6, 50e6, 150e6, np.inf]  # 2025 dollars
BUDGET_LABELS = ["<$10M", "$10-50M", "$50-150M", "$150M+"]


def score(target: str, df: pd.DataFrame, predictions: pd.DataFrame) -> dict[str, float]:
    y = df["target"].to_numpy()
    p10, p50, p90 = (predictions[c].to_numpy() for c in ("p10", "p50", "p90"))
    if target == "score":
        return score_metrics(y, p10, p50, p90, df["score_weight"].to_numpy())
    return money_metrics(y, p10, p50, p90)


def breakdown_groups(target: str, df: pd.DataFrame) -> dict[str, dict[str, pd.Series]]:
    groups: dict[str, dict[str, pd.Series]] = {}
    if target in ("revenue", "budget"):
        size = pd.cut(df["budget_2025"], BUDGET_BINS, labels=BUDGET_LABELS, right=False)
        groups["budget size"] = {label: size == label for label in BUDGET_LABELS}
    english = df["original_language"] == "en"
    groups["language"] = {"English": english, "other languages": ~english}
    new = df["director_is_new"] == 1
    groups["director"] = {"new director": new, "experienced director": ~new}
    sequel = df["is_franchise"] == 1
    groups["franchise"] = {"sequel": sequel, "original": ~sequel}
    return groups


def breakdowns(target: str, df: pd.DataFrame, predictions: pd.DataFrame) -> dict[str, dict[str, dict[str, float]]]:
    return {
        name: {label: score(target, df[mask], predictions[mask]) for label, mask in groups.items() if mask.any()}
        for name, groups in breakdown_groups(target, df).items()
    }


def evaluate(model_factory: Callable[[], Any], target: str, with_backtest: bool = True) -> dict[str, Any]:
    """Fit a fresh model on train, score it on validation overall and by breakdown, then run the backtest."""
    from ml.eval.backtest import backtest  # backtest imports score() from here

    train, validation = load(target, "train"), load(target, "validation")
    model = model_factory().fit(train)
    predictions = model.predict(validation)
    result = {
        "name": model.name,
        "target": target,
        "validation": score(target, validation, predictions),
        "breakdowns": breakdowns(target, validation, predictions),
    }
    if getattr(model, "backtest_note", None):
        result["backtest_note"] = model.backtest_note
    if with_backtest:
        result["backtest"] = backtest(model_factory, target)
    return result


# ---------------------------------------------------------------- reports

REPORTS_DIR = Path("reports")
COLUMNS = {  # metric -> (header, format)
    "money": [("n", "Films", "{:,}"), ("mae_log", "MAE log", "{:.3f}"), ("median_pct_error", "Median % error", "{:.0f}%"),
              ("within_2x", "Within 2×", "{:.1%}"), ("spearman", "Spearman", "{:.3f}"),
              ("coverage", "Coverage 10–90", "{:.1%}"), ("width", "Range width", "{:.1f}×")],
    "score": [("n", "Films", "{:,}"), ("mae", "MAE", "{:.3f}"), ("weighted_mae", "Weighted MAE", "{:.3f}"),
              ("spearman", "Spearman", "{:.3f}"), ("coverage", "Coverage 10–90", "{:.1%}"),
              ("width", "Range width", "{:.2f} pts")],
}
TITLES = {"revenue": "Revenue (log 2025 $)", "budget": "Budget (log 2025 $)", "score": "Score (vote_average)"}


def _fmt(value: Any, pattern: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return pattern.format(int(value) if pattern == "{:,}" else value)


def _table(rows: list[tuple[str, dict[str, float]]], kind: str, first: str = "Model") -> list[str]:
    cols = COLUMNS[kind]
    lines = ["| " + " | ".join([first] + [h for _, h, _ in cols]) + " |", "|" + " --- |" * (len(cols) + 1)]
    lines += ["| " + " | ".join([label] + [_fmt(m.get(k), f) for k, _, f in cols]) + " |" for label, m in rows]
    return lines


def _kind(target: str) -> str:
    return "score" if target == "score" else "money"


def _clean(obj: Any) -> Any:
    """NaN -> None so the JSON is valid."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def write_reports(results: dict[str, list[dict[str, Any]]], out_dir: Path = REPORTS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"_Generated {stamp} by `make evaluate`. Fitted on train (≤2015), scored on validation (2016–18); the test split (2019+) is not used._"
    (out_dir / "metrics.json").write_text(json.dumps(_clean(results), indent=1) + "\n", encoding="utf-8")

    metrics = ["# Metrics", "", header, ""]
    for target, rs in results.items():
        metrics += [f"## {TITLES[target]}", "", *_table([(r["name"], r["validation"]) for r in rs], _kind(target)), ""]
    (out_dir / "metrics.md").write_text("\n".join(metrics), encoding="utf-8")

    lines = ["# Breakdowns (validation)", "", header, ""]
    for target, rs in results.items():
        lines += [f"## {TITLES[target]}", ""]
        for breakdown in rs[0]["breakdowns"]:
            for r in rs:
                rows = [(group, m) for group, m in r["breakdowns"][breakdown].items()]
                lines += [f"**{breakdown}: {r['name']}**", "", *_table(rows, _kind(target), first="Group"), ""]
    (out_dir / "breakdowns.md").write_text("\n".join(lines), encoding="utf-8")

    fold_header = (f"_Generated {stamp} by `make evaluate`. Each fold is fitted on its train years and scored on the "
                   "next three; the test split (2019+) is not used._")
    lines = ["# Rolling backtest", "", fold_header, "",
             "| Fold | Train | Test |", "| --- | --- | --- |"]
    lines += [f"| {f['fold']} | {f['train_years']} | {f['test_years']} |" for f in next(iter(results.values()))[0]["backtest"]["folds"]]
    lines.append("")
    for target, rs in results.items():
        lines += [f"## {TITLES[target]}", ""]
        for r in rs:
            bt = r["backtest"]
            rows = [(f"{f['fold']} ({f['test_years']})", f["metrics"]) for f in bt["folds"]]
            rows += [("mean", bt["mean"]), ("spread (std)", {**bt["std"], "n": None})]
            note = [f"_{r['backtest_note']}_", ""] if r.get("backtest_note") else []
            lines += [f"**{r['name']}**", "", *note, *_table(rows, _kind(target), first="Fold"), ""]
    (out_dir / "backtest.md").write_text("\n".join(lines), encoding="utf-8")


def model_factories() -> dict[str, list[Callable[[], Any]]]:
    """B0-B2 for every target, plus the tuned and calibrated LightGBM model for revenue and score."""
    from ml.models.baselines import BASELINES
    from ml.models.calibrate import load_q
    from ml.models.train import TARGETS, LgbmQuantile
    from ml.models.tune import load_params

    factories = {target: list(classes) for target, classes in BASELINES.items()}
    for target in TARGETS:
        params, n_trees = load_params(target)
        q = load_q(target)
        factories[target].append(lambda target=target, params=params, n_trees=n_trees, q=q:
                                 LgbmQuantile(target, params, n_trees, q=q, name="LightGBM (tuned, calibrated)"))
    return factories


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    start = time.perf_counter()
    results = {target: [evaluate(f, target) for f in factories] for target, factories in model_factories().items()}
    write_reports(results)
    print(f"Evaluated {sum(map(len, results.values()))} models in {time.perf_counter() - start:.0f} s; "
          f"wrote {REPORTS_DIR}/metrics.json, metrics.md, breakdowns.md, backtest.md")
    for target, rs in results.items():
        key = "mae" if target == "score" else "mae_log"
        print(f"  {target:8s}" + "  ".join(f"{r['name']}: {r['validation'][key]:.3f}" for r in rs))


if __name__ == "__main__":
    main()
