"""V1.5: freeze v1's per-film predictions, then judge v2 against them like for like and give a verdict.

    predictions(target_name)        -> DataFrame[target_name, movie_id, part, target, score_weight, p10, p50, p90]
                                       for part in PARTS: "validation" (fitted on train <=2015, as evaluate() does)
                                       and "fold 1".."fold 3" (refitted per fold, as backtest() does)
    all_predictions()               -> predictions() for every name in TARGET_NAMES, concatenated
    like_for_like(v1, v2)           -> (shared, counts): the films in both, scored on v2's target, and the
                                       counts of changed targets, v1 films missing from v2 and new v2 films
    summarise(target_name, df, who) -> {"validation", "backtest_mean", "backtest_std", "coverage", "n", ...}
                                       for the "v1" or "v2" columns of a like_for_like frame
    keep_rule(v1, v2)               -> (keep, reasons) on {target_name: summarise(...)} dicts

Every prediction comes from the "LightGBM (tuned, calibrated)" factory of ml.eval.evaluate.model_factories()
(tuned params and the saved calibration q), so v1 reproduces reports/metrics.json. Revenue's keep-rule model is
the budget-given one; "revenue_estimated" (the budget-estimated chain) is reported but not part of the verdict.
Nothing here fits, early-stops or calibrates on 2016-18: those films are only predicted and scored.

The keep rule: revenue must be lower (MAE log) than v1 on validation and on the backtest mean, with validation
coverage in 0.77-0.83 inclusive; budget (MAE log) and score (MAE) may be worse than v1 on validation and on the
backtest mean by at most v1's backtest std.

CLI: uv run python -m ml.eval.compare_v2 reference   (v1, before the data changes -> reports/v1_reference.csv.gz)
     uv run python -m ml.eval.compare_v2 compare     (v2 from the current code, data and params
                                                      -> reports/v2_compare.md and reports/v2_compare.json)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.eval.evaluate import REPORTS_DIR, _clean, score
from ml.eval.splits import FOLDS, fold_data, load

REFERENCE_FILE = REPORTS_DIR / "v1_reference.csv.gz"
COMPARE_MD = REPORTS_DIR / "v2_compare.md"
COMPARE_JSON = REPORTS_DIR / "v2_compare.json"
PARTS = ("validation", *(f.name for f in FOLDS))
FOLD_PARTS = PARTS[1:]
TARGET_NAMES = ("revenue", "revenue_estimated", "budget", "score")
VERDICT_TARGETS = ("revenue", "budget", "score")
FACTORY = {  # target_name -> (data target, model name in model_factories())
    "revenue": ("revenue", "LightGBM (tuned, calibrated)"),
    "revenue_estimated": ("revenue", "LightGBM, budget estimated (calibrated)"),
    "budget": ("budget", "LightGBM (tuned, calibrated)"),
    "score": ("score", "LightGBM (tuned, calibrated)"),
}
COVERAGE_RANGE = (0.77, 0.83)
KEYS = ("target_name", "part", "movie_id")
PRED = ("p10", "p50", "p90")


def data_target(target_name: str) -> str:
    return FACTORY[target_name][0]


def headline(target_name: str) -> str:
    """The metric the reports headline: MAE log for money, MAE for score."""
    return "mae" if data_target(target_name) == "score" else "mae_log"


# ---------------------------------------------------------------- predictions

def _factory(target_name: str):
    from ml.eval.evaluate import model_factories

    target, name = FACTORY[target_name]
    matches = [f for f in model_factories()[target] if f().name == name]
    if len(matches) != 1:
        raise LookupError(f"expected one {name!r} factory for {target}, found {len(matches)}")
    return matches[0]


def _rows(target_name: str, part: str, df: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"target_name": target_name, "movie_id": df["movie_id"].to_numpy(), "part": part,
                         "target": df["target"].to_numpy(), "score_weight": df["score_weight"].to_numpy(),
                         **{c: p[c].to_numpy() for c in PRED}})


def predictions(target_name: str) -> pd.DataFrame:
    """Validation as in ml.eval.evaluate.evaluate(), folds as in ml.eval.backtest.backtest()."""
    from ml.eval.backtest import refit_synopsis
    from ml.features.synopsis import N_COMPONENTS

    target, factory = data_target(target_name), _factory(target_name)
    train, validation = load(target, "train"), load(target, "validation")
    parts = [_rows(target_name, "validation", validation, factory().fit(train).predict(validation))]
    for fold in FOLDS:
        train, test = fold_data(target, fold)
        model = factory()
        if getattr(model, "uses_synopsis", False):
            train, test = refit_synopsis(train, test, fold.train_last,
                                         n_components=getattr(model, "synopsis_components", N_COMPONENTS))
        parts.append(_rows(target_name, fold.name, test, model.fit(train).predict(test)))
    return pd.concat(parts, ignore_index=True)


def all_predictions() -> pd.DataFrame:
    return pd.concat([predictions(t) for t in TARGET_NAMES], ignore_index=True)


# ---------------------------------------------------------------- like for like

def _counts(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for (name, part), n in df.groupby(["target_name", "part"]).size().items():
        out.setdefault(name, {})[part] = int(n)
    return out


def _zeros(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {name: {part: 0 for part in g["part"].unique()} for name, g in df.groupby("target_name")}


def _merge_counts(base: dict, extra: dict) -> dict:
    return {name: {**parts, **extra.get(name, {})} for name, parts in base.items()}


def like_for_like(v1: pd.DataFrame, v2: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Films present in both versions for the same target and part, with v2's target and weight."""
    merged = v1.merge(v2, on=list(KEYS), how="outer", suffixes=("_v1", "_v2"), indicator=True,
                      validate="one_to_one")
    shared = merged[merged["_merge"] == "both"]
    changed = shared[~np.isclose(shared["target_v1"], shared["target_v2"], rtol=0, atol=1e-9)]
    counts = {
        "target_changed": _merge_counts(_zeros(shared), _counts(changed)),
        "missing_from_v2": _merge_counts(_zeros(v1), _counts(merged[merged["_merge"] == "left_only"])),
        "new_in_v2": _merge_counts(_zeros(v2), _counts(merged[merged["_merge"] == "right_only"])),
        "shared": _counts(shared),
    }
    out = pd.DataFrame({k: shared[k].to_numpy() for k in KEYS})
    out["target"] = shared["target_v2"].to_numpy()
    out["score_weight"] = shared["score_weight_v2"].to_numpy()
    for who in ("v1", "v2"):
        for c in PRED:
            out[f"{who}_{c}"] = shared[f"{c}_{who}"].to_numpy()
    return out, counts


def summarise(target_name: str, df: pd.DataFrame, who: str) -> dict[str, Any]:
    """Metrics of one version's columns (v1_p10.. or v2_p10..) on df, per part, with the backtest mean and std
    (ddof=0, as ml.eval.backtest does). df holds one target_name's rows or several (filtered here)."""
    if "target_name" in df:
        df = df[df["target_name"] == target_name]
    target, key = data_target(target_name), headline(target_name)
    parts: dict[str, dict[str, float]] = {}
    for part in PARTS:
        rows = df[df["part"] == part]
        if len(rows):
            preds = pd.DataFrame({c: rows[f"{who}_{c}"].to_numpy() for c in PRED})
            parts[part] = score(target, rows.reset_index(drop=True), preds)
    folds = [parts[p][key] for p in FOLD_PARTS if p in parts]
    validation = parts.get("validation", {})
    return {
        "metric": key,
        "validation": validation.get(key, math.nan),
        "backtest_mean": float(np.mean(folds)) if folds else math.nan,
        "backtest_std": float(np.std(folds, ddof=0)) if folds else math.nan,
        "coverage": validation.get("coverage", math.nan),
        "n": int(validation.get("n", 0)),
        "fold_n": {p: int(parts[p]["n"]) for p in FOLD_PARTS if p in parts},
        "parts": parts,
    }


def keep_rule(v1: dict[str, dict[str, float]], v2: dict[str, dict[str, float]]) -> tuple[bool, list[str]]:
    """Keep v2 only if every rule holds; each failed rule adds one reason. revenue_estimated is ignored."""
    reasons: list[str] = []
    a, b = v1["revenue"], v2["revenue"]
    if not b["validation"] < a["validation"]:
        reasons.append(f"revenue validation MAE log {b['validation']:.3f} is not lower than v1's {a['validation']:.3f}")
    if not b["backtest_mean"] < a["backtest_mean"]:
        reasons.append(f"revenue backtest mean MAE log {b['backtest_mean']:.3f} is not lower than "
                       f"v1's {a['backtest_mean']:.3f}")
    low, high = COVERAGE_RANGE
    if not low <= b["coverage"] <= high:
        reasons.append(f"revenue validation coverage {b['coverage']:.1%} is outside {low:.0%}-{high:.0%}")
    for name in ("budget", "score"):
        a, b = v1[name], v2[name]
        allowed = a["backtest_std"]
        for key, label in (("validation", "validation"), ("backtest_mean", "backtest mean")):
            if not b[key] <= a[key] + allowed:
                reasons.append(f"{name} {label} {b[key]:.3f} is worse than v1's {a[key]:.3f} by more than "
                               f"v1's backtest std {allowed:.3f}")
    return not reasons, reasons


# ---------------------------------------------------------------- reports

def _fmt(x: Any, pattern: str = "{:.3f}") -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else pattern.format(x)


def _table(rows: list[tuple[str, str, dict[str, Any]]]) -> list[str]:
    lines = ["| Target | Version | Metric | Validation | Backtest mean | Backtest std | Coverage | Films (val) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, who, m in rows:
        lines.append(f"| {name} | {who} | {m['metric']} | {_fmt(m['validation'])} | {_fmt(m['backtest_mean'])} | "
                     f"{_fmt(m['backtest_std'])} | {_fmt(m['coverage'], '{:.1%}')} | {m['n']:,} |")
    return lines


def _count_table(counts: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    lines = ["| Target | Part | Shared | Target changed | v1 missing from v2 | New in v2 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for name in TARGET_NAMES:
        for part in PARTS:
            get = lambda kind: counts[kind].get(name, {}).get(part, 0)  # noqa: E731
            lines.append(f"| {name} | {part} | {get('shared'):,} | {get('target_changed'):,} | "
                         f"{get('missing_from_v2'):,} | {get('new_in_v2'):,} |")
    return lines


def compare(reference: Path = REFERENCE_FILE, md: Path = COMPARE_MD, out_json: Path = COMPARE_JSON) -> dict[str, Any]:
    v1 = pd.read_csv(reference)
    v2 = all_predictions()
    shared, counts = like_for_like(v1, v2)
    v2_all = v2.rename(columns={c: f"v2_{c}" for c in PRED})
    like = {name: {who: summarise(name, shared, who) for who in ("v1", "v2")} for name in TARGET_NAMES}
    all_films = {name: summarise(name, v2_all, "v2") for name in TARGET_NAMES}
    keep, reasons = keep_rule({n: like[n]["v1"] for n in VERDICT_TARGETS}, {n: like[n]["v2"] for n in VERDICT_TARGETS})
    result = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "keep": keep,
              "reasons": reasons, "like_for_like": like, "all_films": all_films, "counts": counts}
    md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(_clean(result), indent=1) + "\n", encoding="utf-8")

    lines = ["# v2 against v1", "",
             f"_Generated {result['generated']} by `uv run python -m ml.eval.compare_v2 compare`. "
             "Validation = fitted on train (≤2015), scored on 2016–18; backtest = the three rolling folds. "
             "The test split (2019+) is not used._", "",
             f"**Verdict: {'keep v2' if keep else 'reject v2'}.**", ""]
    lines += [f"- {r}" for r in reasons] + ([""] if reasons else [])
    lines += ["Keep rule: revenue lower than v1 on validation and on the backtest mean, revenue validation coverage "
              "in 77–83%; budget and score no worse than v1 (validation and backtest mean) by more than v1's "
              "backtest std. `revenue_estimated` is reported only.", "",
              "## Like for like", "",
              "Films in both versions for the same target and part; both versions scored against v2's target.", "",
              *_table([(n, who, like[n][who]) for n in TARGET_NAMES for who in ("v1", "v2")]), "",
              "## All films (v2)", "", "v2 on every film it has, new ones included.", "",
              *_table([(n, "v2", all_films[n]) for n in TARGET_NAMES]), "",
              "## Films", "", *_count_table(counts), ""]
    md.write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=("reference", "compare"))
    args = parser.parse_args()
    start = time.perf_counter()
    if args.stage == "reference":
        df = all_predictions()
        REFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(REFERENCE_FILE, index=False)
        for name, g in df.groupby("target_name", sort=False):
            m = summarise(name, g.rename(columns={c: f"v1_{c}" for c in PRED}), "v1")
            print(f"{name:18s} validation {m['metric']} {m['validation']:.4f}, backtest mean {m['backtest_mean']:.4f}, "
                  f"coverage {m['coverage']:.1%}, {len(g):,} rows")
        print(f"wrote {REFERENCE_FILE} ({time.perf_counter() - start:.0f} s)")
    else:
        result = compare()
        print(f"{'keep' if result['keep'] else 'reject'} v2" + "".join(f"\n  {r}" for r in result["reasons"]))
        print(f"wrote {COMPARE_MD} and {COMPARE_JSON} ({time.perf_counter() - start:.0f} s)")


if __name__ == "__main__":
    main()
