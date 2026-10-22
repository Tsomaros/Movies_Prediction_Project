"""The one-time final run (Day 6): <=2018 models on the locked test split, then the all-data models.

    uv run python -m ml.eval.final test      -> ml/artifacts/final_corrections.json, reports/final_test.md and
                                                final_test.json; refuses to run again once the report exists
    uv run python -m ml.eval.final all-data  -> ml/artifacts/final/: every model retrained on 1960-2025 with
                                                the <=2018 corrections and the frozen tree counts, for the app

This is the only module that passes final=True (a test checks it). Everything it uses was frozen at the
`pre-test` tag: features, tuned settings and tree counts, the calibration method and the rough-estimate
rule. The <=2018 models train on train + validation; each correction comes from out-of-fold predictions
on all three backtest folds (2010-18), the same method as on Day 5 with one more fold. B0-B2 are refitted
on <=2018 too. Revenue is reported in both budget modes, with and without 2020-21.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.clean import COVID_YEARS, VALIDATION_LAST_YEAR
from ml.eval.evaluate import REPORTS_DIR, TITLES, _clean, _kind, _table, breakdowns, score
from ml.eval.splits import FOLDS, fold_data, load, through
from ml.models.baselines import BASELINES
from ml.models.calibrate import LEVEL, conformal_q, uncalibrated
from ml.models.chain import EstimatedBudgetRevenue
from ml.models.rough import LABELLED_TARGETS, _effect, is_rough, load_rule
from ml.models.train import ARTIFACTS_DIR, TARGETS, LgbmQuantile, meta_file, save_model
from ml.models.tune import load_params

LAST_TRAIN_YEAR = VALIDATION_LAST_YEAR  # the final models train on <=2018
CORRECTIONS_FILE = ARTIFACTS_DIR / "final_corrections.json"
REPORT_JSON, REPORT_MD = REPORTS_DIR / "final_test.json", REPORTS_DIR / "final_test.md"
FINAL_DIR = ARTIFACTS_DIR / "final"
RUNS = [(t, False) for t in TARGETS] + [("revenue", True)]  # (target, budget estimated)


def _key(target: str, estimated: bool) -> str:
    return "revenue_estimated" if estimated else target


# ---------------------------------------------------------------- corrections from all three folds


def corrections() -> dict[str, Any]:
    out: dict[str, Any] = {"level": LEVEL, "folds": [f"{f.name}: <={f.train_last} -> {f.test_first}-{f.test_last}"
                                                       for f in FOLDS]}
    for target, estimated in RUNS:
        ys, p10s, p90s = [], [], []
        for fold in FOLDS:
            train, test = fold_data(target, fold)
            p = uncalibrated(target, estimated).fit(train).predict(test)
            ys.append(test["target"].to_numpy()); p10s.append(p["p10"].to_numpy()); p90s.append(p["p90"].to_numpy())
        y, p10, p90 = map(np.concatenate, (ys, p10s, p90s))
        q = conformal_q(y, p10, p90)
        out[_key(target, estimated)] = {"q": q, "films": int(len(y)),
                                        "coverage_before": float(np.mean((y >= p10) & (y <= p90))),
                                        "coverage_after": float(np.mean((y >= p10 - q) & (y <= p90 + q)))}
    # the estimated range is never narrower than the given one (as in ml.models.chain.Chain)
    out["revenue_estimated"]["q_used"] = max(out["revenue_estimated"]["q"], out["revenue"]["q"])
    return out


def _q(corr: dict[str, Any], target: str, estimated: bool = False) -> float:
    return corr["revenue_estimated"]["q_used"] if estimated else corr[target]["q"]


# ---------------------------------------------------------------- the test run


def _models(target: str, corr: dict[str, Any]) -> list[Any]:
    models: list[Any] = [cls() for cls in BASELINES[target]]
    models.append(LgbmQuantile(target, *load_params(target), q=_q(corr, target), name="LightGBM (tuned, calibrated)"))
    if target == "revenue":
        models.append(EstimatedBudgetRevenue(*load_params("revenue"), *load_params("budget"),
                                             q=_q(corr, "revenue", True), name="LightGBM, budget estimated (calibrated)"))
    return models


def run_test() -> dict[str, Any]:
    if REPORT_JSON.exists():
        raise SystemExit(f"{REPORT_JSON} exists: the test split has already been opened. It is opened once.")
    corr = corrections()
    CORRECTIONS_FILE.write_text(json.dumps({**corr, "computed_at": _now()}, indent=1) + "\n", encoding="utf-8")
    rule = load_rule()
    results: dict[str, list[dict[str, Any]]] = {}
    for target in TARGETS:
        train = through(target, LAST_TRAIN_YEAR)
        test = load(target, "test", final=True)
        no_covid = ~test["year"].isin(COVID_YEARS).to_numpy()
        for model in _models(target, corr):
            p = model.fit(train).predict(test)
            entry = {"name": model.name, "train_films": len(train), "test": score(target, test, p),
                     "breakdowns": breakdowns(target, test, p)}
            if target == "revenue":
                entry["test_no_covid"] = score(target, test[no_covid], p[no_covid])
            if target in LABELLED_TARGETS and isinstance(model, (LgbmQuantile, EstimatedBudgetRevenue)):
                entry["rough"] = _effect(test, p, is_rough(target, p["p10"], p["p90"], rule))
            results.setdefault(target, []).append(entry)
    report = {"run_at": _now(), "train_years": f"<={LAST_TRAIN_YEAR}", "test_years": "2019+",
              "corrections": {k: v for k, v in corr.items() if isinstance(v, dict)}, "results": results}
    REPORT_JSON.write_text(json.dumps(_clean(report), indent=1) + "\n", encoding="utf-8")
    write_markdown(report)
    return report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_markdown(report: dict[str, Any]) -> None:
    lines = ["# Final test run", "",
             f"_Run once on {report['run_at'][:10]} by `uv run python -m ml.eval.final test`. Every model is fitted "
             f"on films released up to 2018 and scored on the locked test split (2019+). Ranges are widened by "
             f"corrections from out-of-fold predictions on all three backtest folds (2010–18)._", "",
             "| Correction | q | Calibration films | Fold coverage before → after |", "| --- | --- | --- | --- |"]
    units = {"score": " pts"}
    for key, c in report["corrections"].items():
        q = c.get("q_used", c["q"])
        lines.append(f"| {key.replace('_', ', budget ')} | {q:+.3f}{units.get(key, ' log')} | {c['films']:,} | "
                     f"{c['coverage_before']:.1%} → {c['coverage_after']:.1%} |")
    lines.append("")
    for target, rs in report["results"].items():
        lines += [f"## {TITLES[target]}", "", *_table([(r["name"], r["test"]) for r in rs], _kind(target)), ""]
        if target == "revenue":
            lines += ["**Without 2020–21**", "",
                      *_table([(r["name"], r["test_no_covid"]) for r in rs], _kind(target)), ""]
        rough = [(r["name"], r["rough"]) for r in rs if "rough" in r]
        if rough:
            lines += ["**Rough-estimate label** (frozen cut-offs)", "",
                      "| Model | Labelled | MAE log labelled / rest | Within 2× labelled / rest |", "| --- | --- | --- | --- |"]
            lines += [f"| {n} | {e['labelled_share']:.0%} | {e['mae_labelled']:.3f} / {e['mae_rest']:.3f} "
                      f"({e['mae_ratio']:.2f}×) | {e['within_2x_labelled']:.0%} / {e['within_2x_rest']:.0%} |"
                      for n, e in rough]
            lines.append("")
        for breakdown in rs[0]["breakdowns"]:
            for r in rs:
                if r["name"].startswith(("B2", "LightGBM")):
                    rows = list(r["breakdowns"][breakdown].items())
                    lines += [f"**{breakdown}: {r['name']}**", "", *_table(rows, _kind(target), first="Group"), ""]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- all-data models for the app


def run_all_data(out_dir: Path = FINAL_DIR) -> None:
    if not CORRECTIONS_FILE.exists():
        raise SystemExit("run the test first: the all-data models reuse its <=2018 corrections")
    corr = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
    for target in TARGETS:
        rows = pd.concat([through(target, LAST_TRAIN_YEAR), load(target, "test", final=True)], ignore_index=True)
        model = LgbmQuantile(target, *load_params(target), q=_q(corr, target), name="LightGBM (all data)").fit(rows)
        extra = {"q_estimated": _q(corr, "revenue", True)} if target == "revenue" else {}
        save_model(model, rows, None, out_dir=out_dir, extra={
            "corrections": "from <=2018 out-of-fold predictions on folds 1-3 (ml/artifacts/final_corrections.json)",
            **extra})
        print(f"{target}: {len(rows):,} films ({int(rows['year'].min())}-{int(rows['year'].max())}), "
              f"{len(model.features)} features, q = {model.q:+.3f}; wrote {meta_file(target, out_dir)}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage", choices=("test", "all-data"))
    args = parser.parse_args()
    start = time.perf_counter()
    if args.stage == "test":
        report = run_test()
        for target, rs in report["results"].items():
            key = "mae" if target == "score" else "mae_log"
            print(f"{target:8s}" + "  ".join(f"{r['name']}: {r['test'][key]:.3f} ({r['test']['coverage']:.0%})"
                                             for r in rs))
        print(f"wrote {REPORT_MD} and {REPORT_JSON} ({time.perf_counter() - start:.0f} s)")
    else:
        run_all_data()
        print(f"done in {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main()
