"""Audit metrics after Day 7: reproduce validation, add proper scores and uncertainty, score a fresh 2026 holdout.

    proper_scores(y, p)            -> pinball loss at 0.1 / 0.5 / 0.9, interval score (alpha 0.2), R², shares
                                      below p10 and above p90, in the target's units
    bootstrap(y, p, base, ...)     -> 95% intervals for MAE and coverage, and for the MAE gap to a baseline
    validation_audit()             -> every B0-B2 and LightGBM model refitted as in `make evaluate`: the
                                      validation numbers next to reports/metrics.json, plus proper scores,
                                      bootstrap intervals, coverage by year / genre / language / budget, and
                                      proper scores per backtest fold
    holdout_films(raw_dir)         -> the 2026 pull cleaned with ml.data.clean and written as forms
    holdout_audit(raw_dir)         -> the app's all-data models (ml/artifacts/final) on films released in
                                      2026 that are 182+ days old, against baselines fitted on <=2018

CLI: uv run python -m ml.eval.audit [validation | holdout | all]   -> reports/audit_metrics.json and .md

The test split (2019+) stays locked: nothing here loads it. The 2026 holdout comes from
`uv run python -m ml.data.pull --years 2026 --out-dir data/holdout_2026` (not in git) and never
touches data/movies.db. 2026 money is in 2026 dollars, counted as 2025 dollars (no 2026 CPI yet).
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.data.clean import CPI_BASE_YEAR, clean, load_cpi, load_raw
from ml.eval.evaluate import REPORTS_DIR, breakdown_groups, model_factories, score
from ml.eval.splits import FOLDS, fold_data, load, through
from ml.features.build import FilmForms, api_as_of, build_features, film_to_form
from ml.models.baselines import BASELINES
from ml.models.train import TARGETS

HOLDOUT_DIR = Path("data/holdout_2026")
ALPHA = 0.2  # the 10th-90th range is an 80% interval
QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
N_BOOT = 1000
LIGHTGBM = "LightGBM (tuned, calibrated)"
B2 = {"revenue": "B2 budget x genre multiple", "budget": "B2 genre median x sequel factor",
      "score": "B2 genre median + director"}
REPRODUCED = {"money": ("mae_log", "within_2x", "coverage", "width", "spearman"),
              "score": ("mae", "weighted_mae", "coverage", "width", "spearman")}
TOP_GENRES = 8


# ---------------------------------------------------------------- scores


def pinball(y, q_pred, q: float) -> float:
    d = np.asarray(y, float) - np.asarray(q_pred, float)
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def interval_score(y, low, high, alpha: float = ALPHA) -> float:
    """Winkler / Gneiting-Raftery interval score: width plus 2/alpha times the miss; lower is better."""
    y, low, high = (np.asarray(a, float) for a in (y, low, high))
    return float(np.mean((high - low) + 2 / alpha * (low - y) * (y < low) + 2 / alpha * (y - high) * (y > high)))


def r_squared(y, pred) -> float:
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    return float(1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))


def proper_scores(y, p: pd.DataFrame) -> dict[str, float]:
    y = np.asarray(y, float)
    out = {f"pinball_{k}": pinball(y, p[k], q) for k, q in QUANTILES.items()}
    out["pinball_mean"] = float(np.mean([out[f"pinball_{k}"] for k in QUANTILES]))
    out["interval_score"] = interval_score(y, p["p10"], p["p90"])
    out["r2"] = r_squared(y, p["p50"])
    out["bias"] = float(np.mean(y - p["p50"]))  # > 0: the real values are above the middle on average
    out["below_p10"] = float(np.mean(y < p["p10"]))
    out["above_p90"] = float(np.mean(y > p["p90"]))
    return out


def bootstrap(y, p: pd.DataFrame, base: pd.DataFrame | None = None, n: int = N_BOOT, seed: int = 0) -> dict[str, list[float]]:
    """95% percentile intervals over films resampled with replacement (paired with the baseline)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, float)
    err = np.abs(p["p50"].to_numpy() - y)
    inside = ((p["p10"].to_numpy() <= y) & (y <= p["p90"].to_numpy())).astype(float)
    base_err = None if base is None else np.abs(base["p50"].to_numpy() - y)
    idx = rng.integers(0, len(y), size=(n, len(y)))
    out = {"mae": np.quantile(err[idx].mean(axis=1), [0.025, 0.975]).tolist(),
           "coverage": np.quantile(inside[idx].mean(axis=1), [0.025, 0.975]).tolist()}
    if base_err is not None:
        out["mae_gap_to_b2"] = np.quantile((err[idx] - base_err[idx]).mean(axis=1), [0.025, 0.975]).tolist()
    return out


def _coverage_by(y, p: pd.DataFrame, labels: pd.Series) -> dict[str, dict[str, float]]:
    y = np.asarray(y, float)
    inside = (p["p10"].to_numpy() <= y) & (y <= p["p90"].to_numpy())
    out = {}
    for label in labels.dropna().unique():
        mask = (labels == label).to_numpy()
        out[str(label)] = {"n": int(mask.sum()), "coverage": float(inside[mask].mean()),
                           "below_p10": float((y[mask] < p["p10"].to_numpy()[mask]).mean()),
                           "above_p90": float((y[mask] > p["p90"].to_numpy()[mask]).mean())}
    return dict(sorted(out.items()))


def coverage_groups(target: str, df: pd.DataFrame, p: pd.DataFrame) -> dict[str, dict[str, dict[str, float]]]:
    y = df["target"]
    top = df["main_genre"].value_counts().index[:TOP_GENRES]
    language = pd.Series(np.where(df["original_language"] == "en", "English", "other languages"), index=df.index)
    out = {"year": _coverage_by(y, p, df["year"].astype(int).astype(str)),
           "main genre": _coverage_by(y, p, df["main_genre"].where(df["main_genre"].isin(top), "other")),
           "language": _coverage_by(y, p, language)}
    if target != "score":
        groups = breakdown_groups(target, df)["budget size"]
        labels = pd.Series(pd.NA, index=df.index, dtype="object")
        for label, mask in groups.items():
            labels[mask] = label
        out["budget size"] = _coverage_by(y, p, labels)
    return out


# ---------------------------------------------------------------- validation and backtest (<=2015 / folds)


def _reported() -> dict[str, dict[str, dict[str, Any]]]:
    results = json.loads((REPORTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    return {t: {r["name"]: r for r in rs} for t, rs in results.items()}


def validation_audit() -> dict[str, Any]:
    reported = _reported()
    out: dict[str, Any] = {}
    for target, factories in model_factories().items():
        train, validation = load(target, "train"), load(target, "validation")
        kind = "score" if target == "score" else "money"
        models: dict[str, Any] = {}
        predictions: dict[str, pd.DataFrame] = {}
        for factory in factories:
            start = time.perf_counter()
            model = factory().fit(train)
            p = model.predict(validation)
            predictions[model.name] = p
            metrics = score(target, validation, p)
            old = reported[target][model.name]
            folds = []
            for fold in FOLDS[:2]:  # fold 3 is train vs validation, scored above
                f_train, f_test = fold_data(target, fold)
                fp = factory().fit(f_train).predict(f_test)
                folds.append({"fold": fold.name, "test_years": f"{fold.test_first}-{fold.test_last}",
                              "n": len(f_test), **score(target, f_test, fp), **proper_scores(f_test["target"], fp)})
                mae_key = "mae" if kind == "score" else "mae_log"
                reported_fold = next(f for f in old["backtest"]["folds"] if f["fold"] == fold.name)["metrics"]
                folds[-1]["reported_mae"] = reported_fold[mae_key]
            folds.append({"fold": "fold 3", "test_years": "2016-18", "n": len(validation), **metrics,
                          **proper_scores(validation["target"], p)})
            models[model.name] = {
                "validation": metrics,
                "reproduced": {k: {"now": metrics[k], "reported": old["validation"][k]} for k in REPRODUCED[kind]},
                "max_abs_diff": max(abs(metrics[k] - old["validation"][k]) for k in REPRODUCED[kind]
                                    if old["validation"][k] is not None and not math.isnan(metrics[k])),
                "proper": proper_scores(validation["target"], p),
                "folds": folds,
                "seconds": round(time.perf_counter() - start, 1),
            }
            print(f"  {target} {model.name}: max diff vs report {models[model.name]['max_abs_diff']:.2e} "
                  f"({models[model.name]['seconds']:.0f} s)", flush=True)
        y = validation["target"]
        lgbm = models[LIGHTGBM]
        lgbm["bootstrap"] = bootstrap(y, predictions[LIGHTGBM], predictions[B2[target]])
        lgbm["coverage_groups"] = coverage_groups(target, validation, predictions[LIGHTGBM])
        out[target] = models
    return out


# ---------------------------------------------------------------- the 2026 holdout (all-data app models)


def _currency_caps() -> dict[str, float]:
    with closing(sqlite3.connect(f"file:{DB_FILE.resolve().as_posix()}?mode=ro", uri=True)) as con:
        report = json.loads(con.execute("SELECT value FROM meta WHERE key = 'cleaning_report'").fetchone()[0])
    return report["currency_caps_2025_usd"]


def holdout_films(raw_dir: Path = HOLDOUT_DIR) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """The 2026 pull through the same cleaning rules. Currency caps come from data/movies.db, because
    the few 2026 budgets per language are too few to set their own."""
    cpi = load_cpi()
    year = max(cpi)
    cpi.update({y: cpi[CPI_BASE_YEAR] for y in range(year + 1, 2031)})  # no CPI yet: count as 2025 dollars
    tables, report = clean(load_raw(raw_dir / "tmdb_movies.jsonl"), cpi)
    m = tables["movies"]
    caps = _currency_caps()
    cap = m["original_language"].map(caps).fillna(caps["other non-English"])
    over_cap = (m["original_language"] != "en") & (m["budget_2025"] > cap)
    low_ratio = (m["money_suspect_reason"].fillna("").str.contains("low_ratio"))
    m["money_suspect"] = (over_cap.fillna(False) | low_ratio).astype(bool)
    tables["movies"] = m
    return tables, report


def holdout_forms(tables: dict[str, pd.DataFrame]) -> FilmForms:
    """The cleaned 2026 tables in the shape film_to_form reads, so forms are built exactly as for training."""
    m = tables["movies"].set_index("id")

    def lists(links: pd.DataFrame, key: str, sort: list[str], value: pd.Series | None = None) -> pd.Series:
        df = links.sort_values(sort)
        values = df[key] if value is None else df[key].map(value)
        return values.groupby(df["movie_id"], sort=False).agg(list)

    genre_names = tables["genres"].set_index("id")["name"]
    crew = tables["movie_crew"]
    return FilmForms(
        movies=m.assign(split="holdout")[["split", "release_date", "year", "month", "runtime", "original_language",
                                          "us_certification", "collection_id", "budget_2025", "overview"]],
        genres=lists(tables["movie_genres"], "genre_id", ["movie_id", "ord"], genre_names),
        directors=lists(crew[crew["job"] == "Director"], "person_id", ["movie_id", "person_id"]),
        actors=lists(tables["movie_cast"], "person_id", ["movie_id", "ord"]),
        companies=lists(tables["movie_companies"], "company_id", ["movie_id", "company_id"]),
        countries=lists(tables["movie_countries"], "country", ["movie_id", "country"]),
        keywords=lists(tables["movie_keywords"], "keyword_id", ["movie_id", "keyword_id"]).map(set),
    )


def _baselines(target: str, train: pd.DataFrame) -> dict[str, Any]:
    return {cls.name: cls().fit(train) for cls in BASELINES[target]}


def _holdout_scores(target: str, df: pd.DataFrame, p: pd.DataFrame, base: pd.DataFrame | None) -> dict[str, Any]:
    return {**score(target, df, p), **proper_scores(df["target"], p), "bootstrap": bootstrap(df["target"], p, base)}


def holdout_audit(raw_dir: Path = HOLDOUT_DIR) -> dict[str, Any]:
    from ml.predict import Predictor

    tables, report = holdout_films(raw_dir)
    m = tables["movies"]
    forms = holdout_forms(tables)
    predictor = Predictor.load(comparables=False)
    ctx = predictor.ctx

    rows, keep = [], []
    for movie_id in forms.movies.index:
        if pd.isna(forms.movies.at[movie_id, "release_date"]):
            continue
        form = film_to_form(movie_id, forms, ctx)
        rows.append(build_features(form, api_as_of(form), ctx))
        keep.append(movie_id)
    X = pd.DataFrame(rows, index=keep, dtype=float)
    info = m.set_index("id").loc[keep]
    genre_names = tables["genres"].set_index("id")["name"]
    first = tables["movie_genres"].sort_values("ord").drop_duplicates("movie_id").set_index("movie_id")["genre_id"]
    X["main_genre"] = pd.Series(keep, index=keep).map(first).map(genre_names).fillna("none")
    X["typical_score"] = [ctx.history.priors(api_as_of({"release_year": int(info.at[i, "year"]),
                                                        "release_month": int(info.at[i, "month"])}))[1] for i in keep]
    X["original_language"], X["budget_2025"], X["year"] = info["original_language"], info["budget_2025"], info["year"]

    # The training views' rules (ml/data/build_db.py). Scores of young films are still settling (they
    # start high and drift down), so the score row also needs 182+ days, like revenue; younger films
    # are reported apart.
    mature = ~info["revenue_incomplete"]
    sets = {
        "revenue": info["budget"].notna() & info["revenue"].notna() & ~info["money_suspect"] & mature,
        "budget": info["budget"].notna() & ~info["money_suspect"],
        "score": info["score_ok"] & mature,
    }
    targets = {"revenue": np.log(info["revenue_2025"].astype(float)), "budget": np.log(info["budget_2025"].astype(float)),
               "score": info["vote_average"].astype(float)}
    out: dict[str, Any] = {"pulled": int(len(m)), "mature": int(mature.sum()),
                           "mature_released_by": str(info.loc[mature, "release_date"].max()),
                           "clean_report": {k: v for k, v in report.items() if isinstance(v, int)}}
    young_scores = None
    for target in TARGETS:
        mask = sets[target].to_numpy(bool)
        df = X[mask].copy()
        df["target"] = targets[target][mask].to_numpy()
        df["score_weight"] = np.log1p(info["vote_count"][mask].astype(float)).to_numpy()
        base = _baselines(target, through(target, 2018))  # the lock-safe years; the app models saw 1960-2025
        base_p = {name: b.predict(df) for name, b in base.items()}
        if target == "revenue":
            app = {"LightGBM app (budget given)": predictor.chain.predict_revenue(df, budget=df["budget_2025"].to_numpy()),
                   "LightGBM app (budget estimated)": predictor.chain.predict_revenue(df)}
        elif target == "budget":
            app = {"LightGBM app": predictor.chain.budget.predict(df)}
        else:
            app = {"LightGBM app": predictor.score.predict(df)}
        b2 = base_p[B2[target]]
        res = {name: _holdout_scores(target, df, p, None) for name, p in base_p.items()}
        res.update({name: _holdout_scores(target, df, p, b2) for name, p in app.items()})
        if target == "score":
            many = (df["score_weight"] >= np.log1p(200)).to_numpy()
            res["LightGBM app, 200+ votes"] = _holdout_scores(target, df[many], app["LightGBM app"][many], b2[many])
            young = (info["score_ok"] & ~mature).to_numpy(bool)
            dy = X[young].copy()
            dy["target"], dy["score_weight"] = targets["score"][young].to_numpy(), 1.0
            young_scores = _holdout_scores(target, dy, predictor.score.predict(dy), None)
        out[target] = {"n": int(mask.sum()), "models": res,
                       "released": [str(info["release_date"][mask].min()), str(info["release_date"][mask].max())]}
        if target == "score":
            out[target]["younger_than_182_days"] = {"n": int(len(dy)), **young_scores}
        print(f"  holdout {target}: {mask.sum()} films", flush=True)
    return out


# ---------------------------------------------------------------- report


def _f(x: Any, pattern: str) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else pattern.format(x)


def _ci(ci: list[float] | None, pattern: str = "{:.3f}") -> str:
    return "—" if not ci else f"{pattern.format(ci[0])} to {pattern.format(ci[1])}"


def write_report(results: dict[str, Any], out_dir: Path = REPORTS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit_metrics.json").write_text(json.dumps(results, indent=1, default=float) + "\n", encoding="utf-8")
    stamp = results["run_at"][:16].replace("T", " ")
    lines = ["# Audit metrics", "",
             f"_Generated {stamp} UTC by `uv run python -m ml.eval.audit`. Validation: models fitted on ≤2015 "
             "exactly as `make evaluate` does, scored on 2016–18. Holdout: the app's all-data models on films "
             "released in 2026. The test split (2019+) is not used._", ""]
    val = results.get("validation")
    if val:
        lines += ["## Reproduction of reports/metrics.md", "", "| Target | Model | Largest difference |", "| --- | --- | --- |"]
        lines += [f"| {t} | {name} | {r['max_abs_diff']:.1e} |" for t, models in val.items() for name, r in models.items()]
        lines += ["", "## Proper scores on 2016–18 (lower is better, except R²)", "",
                  "Pinball loss scores each quantile on its own; the interval score is the range width plus 10× "
                  "every miss (α = 0.2). Units: log 2025 $ for money, points for score.", ""]
        for t, models in val.items():
            lines += [f"### {t}", "", "| Model | Pinball p10 | p50 | p90 | Mean | Interval score | R² | Below p10 | Above p90 |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
            for name, r in models.items():
                p = r["proper"]
                lines.append(f"| {name} | {p['pinball_p10']:.3f} | {p['pinball_p50']:.3f} | {p['pinball_p90']:.3f} | "
                             f"{p['pinball_mean']:.3f} | {p['interval_score']:.2f} | {p['r2']:.3f} | "
                             f"{p['below_p10']:.1%} | {p['above_p90']:.1%} |")
            b = models[LIGHTGBM]["bootstrap"]
            lines += ["", f"LightGBM 95% intervals ({N_BOOT:,} resamples of films): MAE {_ci(b['mae'])}, coverage "
                      f"{_ci(b['coverage'], '{:.1%}')}, MAE minus B2's {_ci(b['mae_gap_to_b2'])}.", ""]
            lines += ["| Fold | Films | LightGBM interval score | B2 interval score | LightGBM MAE (reported) |",
                      "| --- | --- | --- | --- | --- |"]
            mae_key = "mae" if t == "score" else "mae_log"
            for lf, bf in zip(models[LIGHTGBM]["folds"], models[B2[t]]["folds"]):
                rep = lf.get("reported_mae", models[LIGHTGBM]["validation"][mae_key])
                lines.append(f"| {lf['fold']} ({lf['test_years']}) | {lf['n']:,} | {lf['interval_score']:.2f} | "
                             f"{bf['interval_score']:.2f} | {lf[mae_key]:.3f} ({rep:.3f}) |")
            lines.append("")
            for group, rows in models[LIGHTGBM]["coverage_groups"].items():
                lines += [f"**LightGBM coverage by {group}**", "", "| Group | Films | Coverage | Below p10 | Above p90 |",
                          "| --- | --- | --- | --- | --- |"]
                lines += [f"| {g} | {r['n']:,} | {r['coverage']:.1%} | {r['below_p10']:.1%} | {r['above_p90']:.1%} |"
                          for g, r in rows.items()]
                lines.append("")
    hold = results.get("holdout")
    if hold:
        lines += ["## Fresh holdout: films released in 2026", "",
                  f"{hold['pulled']:,} films of 2026 pulled from TMDB; {hold['mature']:,} were 182+ days old (released "
                  f"by {hold['mature_released_by']}). Revenue and score use those only, budget every film with one. "
                  "The app's models were trained on 1960–2025, so none of these films was seen; the baselines are "
                  "fitted on ≤2018. Each film is judged at the 1st of its release month, as in the app.", ""]
        for t in TARGETS:
            h = hold[t]
            money = t != "score"
            rows = list(h["models"].items())
            if "younger_than_182_days" in h:
                rows.append(("LightGBM app, films under 182 days old", h["younger_than_182_days"]))
            lines += [f"### {t} ({h['n']:,} films released {h['released'][0]} to {h['released'][1]})", "",
                      "| Model | Films | MAE | Within 2× | Spearman | Coverage 10–90 | Width | Interval score | R² | Bias | "
                      "MAE 95% interval |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
            for name, r in rows:
                mae = r["mae_log"] if money else r["mae"]
                width = _f(r["width"], "{:.1f}×" if money else "{:.2f} pts")
                lines.append(f"| {name} | {r['n']:,} | {mae:.3f} | {_f(r.get('within_2x'), '{:.1%}')} | "
                             f"{_f(r['spearman'], '{:.3f}')} | {r['coverage']:.1%} | {width} | {r['interval_score']:.2f} | "
                             f"{r['r2']:.3f} | {r['bias']:+.2f} | {_ci(r['bootstrap']['mae'])} |")
            lines.append("")
    (out_dir / "audit_metrics.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which not in ("validation", "holdout", "all"):
        sys.exit("usage: uv run python -m ml.eval.audit [validation | holdout | all]")
    path = REPORTS_DIR / "audit_metrics.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    results["run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.perf_counter()
    if which in ("validation", "all"):
        results["validation"] = validation_audit()
    if which in ("holdout", "all"):
        results["holdout"] = holdout_audit()
    write_report(results)
    print(f"wrote {REPORTS_DIR}/audit_metrics.json and .md in {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main()
