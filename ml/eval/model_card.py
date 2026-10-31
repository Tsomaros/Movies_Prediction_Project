"""The model card behind GET /api/v1/model-card: the app's honest accuracy numbers, in one small JSON file.

    build(final_test, audit, manifest, metrics)
                                        -> the card: the one-time 2019+ test (Day 6, <=2018 models) and the
                                           2026 holdout (audit, the app's own models), each with LightGBM next
                                           to the strongest baseline (B2), the models' version and data, and
                                           the "within the uncertainty" thresholds for comparing versions
    uncertainty(metrics)                -> those thresholds from the 2016-18 validation ranges
    write(out_dir)                      -> ml/artifacts/final/model_card.json from reports/final_test.json,
                                           reports/audit_metrics.json, reports/metrics.json and
                                           ml/artifacts/final/manifest.json
    CARD_FILE                           -> the file's name inside the models folder

The card is committed next to the models, because the Docker image has no reports/ folder. Nothing here is
recomputed: every number is copied from the two reports, so the card can't disagree with them
(tests/ml/test_model_card.py checks the committed file is current). Money metrics are on the log scale, with
"typical_factor" = exp(MAE log): the middle is typically off by this factor. Score metrics are in points.

Thresholds (Day 13): a change between two versions of a film counts as "within the uncertainty" when it moves
the middle by less than UNCERTAINTY_FRACTION of the median 10-90 range on validation (2016-18): for money a
factor of width ** 0.1 (the range is high / low, so a tenth of it on the log scale), for score 0.1 * width points.

CLI: uv run python -m ml.eval.model_card   (rerun after the reports or the models change)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

CARD_FILE = "model_card.json"
FINAL_DIR = Path("ml/artifacts/final")
REPORTS = Path("reports")
COVERAGE_TARGET = 0.8

MONEY = ("mae_log", "within_2x", "coverage", "width")
POINTS = ("mae", "coverage", "width")

# target -> (the LightGBM entry in final_test.json, the one in the audit's holdout, metrics)
TARGETS = {
    "revenue": ("LightGBM (tuned, calibrated)", "LightGBM app (budget given)", MONEY),
    "revenue_estimated": ("LightGBM, budget estimated (calibrated)", "LightGBM app (budget estimated)", MONEY),
    "budget": ("LightGBM (tuned, calibrated)", "LightGBM app", MONEY),
    "score": ("LightGBM (tuned, calibrated)", "LightGBM app", POINTS),
}
REPORT_KEY = {"revenue_estimated": "revenue"}  # both revenue modes are in the revenue section
UNCERTAINTY_FRACTION = 0.1
# target -> the LightGBM entry in metrics.json (validation, <=2015 models)
VALIDATION = {
    "revenue": "LightGBM (tuned, calibrated)",
    "revenue_estimated": "LightGBM, budget estimated (calibrated)",
    "budget": "LightGBM (tuned, calibrated)",
    "score": "LightGBM (tuned, calibrated)",
}


def _metrics(m: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    out = {k: round(float(m[k]), 4) for k in keys}
    if "mae_log" in out:
        out["typical_factor"] = round(math.exp(m["mae_log"]), 2)
    return out


def _entry(models: dict[str, dict[str, Any]], model: str, keys: tuple[str, ...]) -> dict[str, Any]:
    """LightGBM and B2 (the strongest baseline on every target) on the same films."""
    b2 = next(name for name in models if name.startswith("B2"))
    return {"films": int(models[model]["n"]), "model": _metrics(models[model], keys),
            "baseline": {"name": b2, **_metrics(models[b2], keys)}}


def uncertainty(metrics: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"fraction": UNCERTAINTY_FRACTION, "years": "2016-2018"}
    for target, model in VALIDATION.items():
        entry = next(m for m in metrics[REPORT_KEY.get(target, target)] if m["name"] == model)
        width = float(entry["validation"]["width"])
        if target == "score":
            out[target] = {"width": round(width, 4), "points": round(UNCERTAINTY_FRACTION * width, 4)}
        else:
            out[target] = {"width": round(width, 4), "ratio": round(width ** UNCERTAINTY_FRACTION, 4)}
    return out


def build(final_test: dict[str, Any], audit: dict[str, Any], manifest: dict[str, Any],
          metrics: dict[str, Any]) -> dict[str, Any]:
    holdout = audit["holdout"]
    test = {t: {m["name"]: {**m["test"]} for m in final_test["results"][REPORT_KEY.get(t, t)]} for t in TARGETS}
    years = {m["trained_on"].removeprefix("films released ") for m in manifest["models"].values()}
    return {
        "model_version": manifest["version"],
        "coverage_target": COVERAGE_TARGET,
        "training": {"years": years.pop() if len(years) == 1 else sorted(years),
                     "films": {t: m["train_films"] for t, m in manifest["models"].items()}},
        "test": {
            "about": "Films released 2019 onwards, locked away until the models were final and scored once, "
                     "by models trained on films up to 2018.",
            "years": final_test["test_years"], "trained_on": final_test["train_years"],
            "run_at": final_test["run_at"][:10],
            "targets": {t: _entry(test[t], model, keys) for t, (model, _, keys) in TARGETS.items()},
        },
        "holdout": {
            "about": "Films released in 2026, after the app's training data ends, scored by the app's own models. "
                     "Revenue and score only for films 6+ months old.",
            "years": "2026", "released_by": holdout["mature_released_by"],
            "run_at": audit["run_at"][:10],
            "targets": {t: _entry(holdout[REPORT_KEY.get(t, t)]["models"], model, keys)
                        for t, (_, model, keys) in TARGETS.items()},
        },
        "uncertainty": uncertainty(metrics),
        "sources": {"test": "reports/final_test.md", "holdout": "reports/audit.md", "uncertainty": "reports/metrics.md"},
    }


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(out_dir: Path = FINAL_DIR, reports: Path = REPORTS) -> dict[str, Any]:
    card = build(_read(reports / "final_test.json"), _read(reports / "audit_metrics.json"),
                 _read(out_dir / "manifest.json"), _read(reports / "metrics.json"))
    (out_dir / CARD_FILE).write_text(json.dumps(card, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return card


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    card = write()
    r = card["test"]["targets"]["revenue"]
    print(f"wrote {FINAL_DIR / CARD_FILE} for model version {card['model_version']} "
          f"(2019+ revenue coverage {r['model']['coverage']:.1%} on {r['films']:,} films)")


if __name__ == "__main__":
    main()
