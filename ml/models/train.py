"""LightGBM models for revenue, budget and score, with the same fit / predict interface as the baselines.

    LgbmQuantile(target, params, n_trees).fit(train_df)   -> learns from train rows (ml.eval.splits.load output)
    model.predict(df)                                     -> DataFrame with p10, p50, p90 in the target's units
    model_features(target, drop)                          -> the feature columns a model may use
    save_model(model, train, validation) / load_model(target)
                                                          -> ml/artifacts/{target}_p10|p50|p90.joblib + {target}_meta.json
    uv run python -m ml.models.train                      -> fits every model on train (<=2015) with the tuned
                                                             settings and calibration, then saves them

| Target  | Middle (p50)                                  | Range (p10 / p90)                                         |
| Revenue | Huber, monotone in MONOTONE                   | middle + quantile models of the middle's residual         |
| Budget  | quantile 0.5                                  | quantile 0.1 / 0.9 on log budget                          |
| Score   | quantile 0.5, weighted by log(1 + votes)      | quantile 0.1 / 0.9 on the score, same weights              |

LightGBM refuses monotone constraints on quantile and L1 objectives, so revenue's middle is a Huber
model. Its range comes from quantile models fitted on out-of-fold residuals (in-sample residuals of a
boosted model are too small) and they never see the monotone columns, so a higher budget shifts the
whole range up and never lowers any of the three outputs. `q` is the conformal correction from
ml.models.calibrate: the range widens by q on both sides (apply_q). By default the synopsis numbers
are left out of every model and the budget track record out of score (DEFAULT_DROP); pass drop=() to use
every allowed feature. The budget model never sees log_budget (feature_list.json) and has no constraints.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from ml.features.build import FEATURE_LIST_FILE
from ml.features.synopsis import N_COMPONENTS
from ml.models.baselines import HIGH, LOW, SCORE_RANGE

TARGETS = ("revenue", "budget", "score")
MONOTONE = ("log_budget", "director_revenue", "franchise_revenue")  # non-decreasing, revenue only
EXCLUDED = {"score": {"log_budget"}}  # score stays independent of the budget chain (feature_list.json allows it)
DROP_GROUPS = {  # ablation name -> feature_list.json source
    "synopsis": "synopsis (MiniLM + PCA)",
    "track_record": "track record (earlier films only)",
    "themes": "themes",
    "budget": "budget (2025 dollars)",
    "budget_history": "budget track record (earlier budgets only)",
}
# The Day 5 ablation found the synopsis numbers don't help either model. The Day 6 budget track record
# improved revenue on validation and in the backtest, so revenue keeps it; score was never tried with it.
DEFAULT_DROP = {"revenue": ("synopsis",), "budget": ("synopsis",), "score": ("synopsis", "budget_history")}
DEFAULT_PARAMS = {
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l1": 0.0,
    "lambda_l2": 0.0,
    "huber_delta": 1.0,  # revenue middle only, in log units
}
DEFAULT_TREES = 500
RESIDUAL_FOLDS = 5


def model_features(target: str, drop: tuple[str, ...] = ()) -> list[str]:
    """Columns from feature_list.json the target's model may use, minus the dropped groups."""
    dropped = {DROP_GROUPS[d] for d in drop}
    entries = json.loads(FEATURE_LIST_FILE.read_text(encoding="utf-8"))
    excluded = EXCLUDED.get(target, set())
    return [e["name"] for e in entries
            if target in e["models"] and e["source"] not in dropped and e["name"] not in excluded]


def _lgb_params(params: dict[str, Any], objective: str, alpha: float | None = None) -> dict[str, Any]:
    out = {k: v for k, v in params.items() if k != "huber_delta"}
    out.update(objective=objective, verbose=-1, seed=0)
    if objective == "huber":
        out["alpha"] = params.get("huber_delta", DEFAULT_PARAMS["huber_delta"])
    elif alpha is not None:
        out["alpha"] = alpha
    return out


def _train(X: pd.DataFrame, y: np.ndarray, params: dict[str, Any], n_trees: int,
           weight: np.ndarray | None = None) -> lgb.Booster:
    return lgb.train(params, lgb.Dataset(X, y, weight=weight, free_raw_data=False), num_boost_round=n_trees)


class LgbmQuantile:
    def __init__(self, target: str, params: dict[str, Any] | None = None, n_trees: int = DEFAULT_TREES,
                 drop: tuple[str, ...] | None = None, monotone: bool = True, q: float = 0.0,
                 features: list[str] | None = None, name: str | None = None,
                 synopsis_components: int = N_COMPONENTS):
        if target not in TARGETS:
            raise ValueError(f"unknown target {target!r}; expected one of {TARGETS}")
        drop = DEFAULT_DROP[target] if drop is None else drop
        self.target = target
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.n_trees = n_trees
        self.drop = tuple(drop)
        self.uses_synopsis = "synopsis" not in self.drop  # the backtest then gives it fold-fitted synopsis numbers
        self.monotone = monotone and target == "revenue"
        self.q = q
        self.features = features or model_features(target, self.drop)
        self.synopsis_components = synopsis_components  # above 16: the data needs refit_synopsis columns
        if synopsis_components > N_COMPONENTS and "synopsis" not in self.drop:
            self.features += [f"synopsis_{i:02d}" for i in range(N_COMPONENTS, synopsis_components)]
        self.name = name or f"LightGBM {target}"
        self.models: dict[str, lgb.Booster] = {}
        if q:
            self.backtest_note = ("Range correction learned on folds 1-2, so coverage there is fitted, not tested; "
                                  "fold 3 (2016-18) is the honest check. Settings tuned on folds 1-2 as well.")

    @property
    def residual_features(self) -> list[str]:
        return [c for c in self.features if c not in MONOTONE]

    def fit(self, train: pd.DataFrame) -> LgbmQuantile:
        X, y = train[self.features], train["target"].to_numpy()
        if self.target != "revenue":  # budget and score: three plain quantile models
            w = train["score_weight"].to_numpy() if self.target == "score" else None
            for key, alpha in (("p10", LOW), ("p50", 0.5), ("p90", HIGH)):
                self.models[key] = _train(X, y, _lgb_params(self.params, "quantile", alpha), self.n_trees, w)
            return self

        middle = _lgb_params(self.params, "huber")
        if self.monotone:
            middle["monotone_constraints"] = [1 if c in MONOTONE else 0 for c in self.features]
        self.models["p50"] = _train(X, y, middle, self.n_trees)

        # out-of-fold residuals, folds grouped by release year
        residual = np.empty(len(train))
        for fit_idx, out_idx in GroupKFold(RESIDUAL_FOLDS).split(X, groups=train["year"]):
            m = _train(X.iloc[fit_idx], y[fit_idx], middle, self.n_trees)
            residual[out_idx] = y[out_idx] - m.predict(X.iloc[out_idx])
        R = train[self.residual_features]
        for key, alpha in (("p10", LOW), ("p90", HIGH)):
            self.models[key] = _train(R, residual, _lgb_params(self.params, "quantile", alpha), self.n_trees)
        return self

    def predict(self, df: pd.DataFrame, q: float | None = None) -> pd.DataFrame:
        """p10 / p50 / p90, widened by `q` (default: the model's own correction)."""
        X = df[self.features]
        if self.target != "revenue":
            raw = np.column_stack([self.models[k].predict(X) for k in ("p10", "p50", "p90")])
            p10, p50, p90 = np.sort(raw, axis=1).T  # quantile models can cross
        else:
            p50 = self.models["p50"].predict(X)
            R = df[self.residual_features]
            p10 = p50 + np.minimum(self.models["p10"].predict(R), 0.0)
            p90 = p50 + np.maximum(self.models["p90"].predict(R), 0.0)
        out = pd.DataFrame({"p10": p10, "p50": p50, "p90": p90}, index=df.index)
        return self.apply_q(out, self.q if q is None else q, self.target)

    @staticmethod
    def apply_q(p: pd.DataFrame, q: float, target: str) -> pd.DataFrame:
        """Widen the range by q on both sides (narrow it if q < 0, never past the middle); clip score to 0-10."""
        out = pd.DataFrame({"p10": np.minimum(p["p10"] - q, p["p50"]), "p50": p["p50"],
                            "p90": np.maximum(p["p90"] + q, p["p50"])}, index=p.index)
        if target == "score":
            out = out.clip(*SCORE_RANGE)
        return out


# ---------------------------------------------------------------- artifacts

ARTIFACTS_DIR = Path("ml/artifacts")
QUANTILE_KEYS = ("p10", "p50", "p90")


def meta_file(target: str, out_dir: Path = ARTIFACTS_DIR) -> Path:
    return out_dir / f"{target}_meta.json"


def save_model(model: LgbmQuantile, train: pd.DataFrame, validation_metrics: dict[str, float] | None = None,
               out_dir: Path = ARTIFACTS_DIR) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in QUANTILE_KEYS:
        joblib.dump(model.models[key], out_dir / f"{model.target}_{key}.joblib")
    meta = {
        "target": model.target,
        "name": model.name,
        "units": "score points (0-10)" if model.target == "score" else "log 2025 $",
        "features": model.features,
        "residual_features": model.residual_features if model.target == "revenue" else None,
        "drop": list(model.drop),
        "monotone": list(MONOTONE) if model.monotone else [],
        "params": model.params,
        "n_trees": model.n_trees,
        "q": model.q,
        "trained_on": f"train split, {int(train['year'].min())}-{int(train['year'].max())}",
        "train_films": len(train),
        "validation_metrics": validation_metrics,
        "lightgbm": lgb.__version__,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    meta_file(model.target, out_dir).write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def load_model(target: str, out_dir: Path = ARTIFACTS_DIR) -> LgbmQuantile:
    meta = json.loads(meta_file(target, out_dir).read_text(encoding="utf-8"))
    model = LgbmQuantile(target, meta["params"], meta["n_trees"], drop=tuple(meta["drop"]),
                         monotone=bool(meta["monotone"]), q=meta["q"], features=meta["features"], name=meta["name"])
    model.models = {key: joblib.load(out_dir / f"{target}_{key}.joblib") for key in QUANTILE_KEYS}
    return model


def main() -> None:
    from ml.eval.evaluate import score
    from ml.eval.splits import load
    from ml.models.calibrate import load_q
    from ml.models.tune import load_params

    sys.stdout.reconfigure(encoding="utf-8")
    for target in TARGETS:
        start = time.perf_counter()
        params, n_trees = load_params(target)
        train, validation = load(target, "train"), load(target, "validation")
        model = LgbmQuantile(target, params, n_trees, q=load_q(target), name="LightGBM (tuned, calibrated)").fit(train)
        metrics = score(target, validation, model.predict(validation))
        save_model(model, train, metrics)
        key = "mae" if target == "score" else "mae_log"
        print(f"{target}: {len(model.features)} features, {n_trees} trees, q = {model.q:+.3f}; validation {key} "
              f"{metrics[key]:.3f}, coverage {metrics['coverage']:.1%} ({time.perf_counter() - start:.0f} s); "
              f"wrote {ARTIFACTS_DIR}/{target}_p10|p50|p90.joblib and {meta_file(target)}")


if __name__ == "__main__":
    main()
