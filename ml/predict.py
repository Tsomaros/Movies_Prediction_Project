"""One call from a creator's form to the full prediction: ranges, drivers, comparable films and warnings.

    Predictor.load(out_dir, db_path)  -> the all-data models, feature context, rough rule and comparables
                                         index, checked against out_dir/manifest.json (about 20 s, once)
    predictor.predict(form)           -> a JSON-ready dict (below); raises InvalidForm with readable errors
    write_manifest(out_dir)           -> out_dir/manifest.json: checksums, training years, versions
    predict(form)                     -> the same with a Predictor loaded once from ml/artifacts/final

The steps follow the plan: validate -> features -> budget -> revenue (budget given or estimated) ->
score -> drivers -> comparables. The output has
- "budget", "revenue", "score": low / middle / high (2025 $, or score points), a text range, the rough
  flag (revenue and budget only), plus revenue's "mode" and the budget comparison;
- "drivers": per target the top 5 groups as sentences, split into "up" and "down";
- "comparables": up to 5 earlier films; "warnings": codes with a sentence; "model_version", "as_of".

The app's models are the Day 6 all-data models in ml/artifacts/final/. The rough rule is copied there
by write_manifest, so the folder holds everything the app reads except the database.

CLI: uv run python -m ml.predict manifest   (writes ml/artifacts/final/manifest.json and copies the rough rule)
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.explain.comparables import INDEX_FILE, Index
from ml.explain.drivers import contributions, group_contributions, main_feature, top_drivers
from ml.explain.groups import feature_groups
from ml.explain.sentences import explain
from ml.features.build import FeatureContext, api_as_of, build_features
from ml.features.contract import validate
from ml.models.chain import Chain, compare_budget, format_money
from ml.models.rough import ROUGH_FILE, is_rough, load_rule
from ml.models.train import QUANTILE_KEYS, TARGETS, LgbmQuantile, load_model

FINAL_DIR = Path("ml/artifacts/final")
MANIFEST = "manifest.json"
MODELS_TAG = "final-models"  # the git tag of the Day 6 all-data models
BIG_BUDGET = 150_000_000  # 2025 $; revenue for $150M+ films was the weak spot on 2019+ (Day 6)
EDGE = 0.05  # a budget within 5% of an edge of the similar-films range is "at the low / high end"
POSITION_WORDS = {"below": "below", "at the low end": "at the low end of", "within": "within",
                  "at the high end": "at the high end of", "above": "above"}


class InvalidForm(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _model_files(out_dir: Path) -> list[Path]:
    return [out_dir / f"{t}_{k}.joblib" for t in TARGETS for k in QUANTILE_KEYS] + \
           [out_dir / f"{t}_meta.json" for t in TARGETS] + [out_dir / ROUGH_FILE.name]


def write_manifest(out_dir: Path = FINAL_DIR, rough_file: Path = ROUGH_FILE) -> dict[str, Any]:
    """Copy the rough rule into out_dir and record every file the app reads, with checksums."""
    shutil.copyfile(rough_file, out_dir / rough_file.name)
    files = {p.name: _sha256(p) for p in _model_files(out_dir)}
    metas = {t: json.loads((out_dir / f"{t}_meta.json").read_text(encoding="utf-8")) for t in TARGETS}
    digest = hashlib.sha256("".join(files[k] for k in sorted(files)).encode()).hexdigest()[:8]
    saved = max(m["saved_at"] for m in metas.values())[:10]
    manifest = {
        "version": f"{saved}.{digest}",
        "tag": MODELS_TAG,
        "models": {t: {"trained_on": m["trained_on"], "train_films": m["train_films"], "q": m["q"],
                       **({"q_estimated": m["q_estimated"]} if "q_estimated" in m else {})}
                   for t, m in metas.items()},
        "lightgbm": metas["revenue"]["lightgbm"],
        "files": files,
        "comparables": {"file": INDEX_FILE.name, "built_by": "uv run python -m ml.explain.comparables",
                        "checked": False},  # rebuilt from the database, so its bytes change; not checksummed
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def check_manifest(out_dir: Path = FINAL_DIR) -> dict[str, Any]:
    """The manifest, after checking every listed file against its checksum (ValueError if one differs)."""
    manifest = json.loads((out_dir / MANIFEST).read_text(encoding="utf-8"))
    bad = [name for name, sha in manifest["files"].items() if _sha256(out_dir / name) != sha]
    if bad:
        raise ValueError(f"{out_dir} does not match {MANIFEST}: {', '.join(bad)} changed; "
                         "rerun `uv run python -m ml.predict manifest` only if the change is intended")
    return manifest


# ---------------------------------------------------------------- formatting


def _money_range(low: float, middle: float, high: float) -> dict[str, Any]:
    return {"low": low, "middle": middle, "high": high,
            "text": f"{format_money(low)}–{format_money(high)}", "middle_text": format_money(middle)}


def _score_range(low: float, middle: float, high: float) -> dict[str, Any]:
    return {"low": low, "middle": middle, "high": high, "text": f"{low:.1f}–{high:.1f}", "middle_text": f"{middle:.1f}"}


def budget_position(budget: float, low: float, high: float) -> str:
    """below / at the low end / within / at the high end / above; the ends cover EDGE on both sides."""
    if abs(budget / low - 1) <= EDGE:
        return "at the low end"
    if abs(budget / high - 1) <= EDGE:
        return "at the high end"
    return "below" if budget < low else "above" if budget > high else "within"


def _comparison(budget_p: pd.DataFrame, budget: float | None) -> dict[str, Any]:
    c = compare_budget(budget_p, budget).iloc[0]
    out = {"low": float(c["low"]), "middle": float(c["middle"]), "high": float(c["high"]), "text": c["text"]}
    if budget is not None:
        position = budget_position(budget, out["low"], out["high"])
        sentence = f"Your budget of {format_money(budget)} is {POSITION_WORDS[position]} what similar films usually cost"
        out.update(budget=budget, position=position, ratio=float(c["ratio"]), sentence=sentence)
    return out


# ---------------------------------------------------------------- the predictor


def _read_only(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True)


@dataclass
class Predictor:
    chain: Chain
    score: LgbmQuantile
    ctx: FeatureContext
    rule: dict[str, Any]
    index: Index | None
    manifest: dict[str, Any]
    db_path: Path = DB_FILE
    groups: dict[str, str] = field(default_factory=feature_groups)

    @classmethod
    def load(cls, out_dir: Path = FINAL_DIR, db_path: Path = DB_FILE, comparables: bool = True) -> Predictor:
        manifest = check_manifest(out_dir)
        with closing(_read_only(db_path)) as con:
            ctx = FeatureContext.load(con)
        index = Index.load(out_dir / INDEX_FILE.name) if comparables else None
        return cls(Chain.load(out_dir), load_model("score", out_dir), ctx, load_rule(out_dir / ROUGH_FILE.name),
                   index, manifest, db_path)

    def names(self, form: dict[str, Any]) -> dict[str, Any]:
        """Display names for the ids in the form (read-only lookups; a typed name is kept as typed)."""
        def lookup(con: sqlite3.Connection, table: str, ref: dict[str, Any] | None) -> str | None:
            if not ref:
                return None
            if ref.get("id") is not None:
                row = con.execute(f"SELECT name FROM {table} WHERE id = ?", (ref["id"],)).fetchone()
                if row:
                    return row[0]
            return ref.get("name")

        with closing(_read_only(self.db_path)) as con:
            return {"director": lookup(con, "people", form.get("director")),
                    "actors": [lookup(con, "people", a) for a in form.get("actors") or []],
                    "companies": [lookup(con, "companies", c) for c in form.get("companies") or []],
                    "franchise": lookup(con, "collections", form.get("franchise"))}

    def _drivers(self, target: str, model: LgbmQuantile, X: pd.DataFrame, form: dict[str, Any],
                 names: dict[str, Any], estimated: tuple[str, ...] = ()) -> dict[str, list[dict[str, Any]]]:
        c = contributions(model, X)
        grouped = group_contributions(c, self.groups).iloc[0]
        drivers = [{**d, "main_feature": main_feature(c.iloc[0], d["group"], self.groups)}
                   for d in top_drivers(target, grouped, estimated=estimated)]
        return explain(target, drivers, form, X.iloc[0].to_dict(), names)

    def predict(self, form: dict[str, Any]) -> dict[str, Any]:
        clean, errors = validate(form, themes=list(self.ctx.themes))
        if errors:
            raise InvalidForm(errors)
        as_of = api_as_of(clean)
        vector = self.ctx.embed(clean["synopsis"]) if clean.get("synopsis") else None
        row = build_features(clean, as_of, self.ctx, synopsis_vector=vector)
        X = pd.DataFrame([row], dtype=float)  # one row with missing values would otherwise be "object"
        budget = clean.get("budget")
        names = self.names(clean)

        budget_p = self.chain.budget.predict(X)
        revenue_p = self.chain.predict_revenue(X, budget=budget)
        mode, log_budget = revenue_p.attrs["mode"], float(revenue_p.attrs["log_budget"][0])
        X_revenue = X.assign(log_budget=log_budget)
        score_p = self.score.predict(X)

        b, r, s = (p.iloc[0] for p in (budget_p, revenue_p, score_p))
        out = {
            "model_version": self.manifest["version"],
            "as_of": date(clean["release_year"], clean["release_month"], 1).isoformat(),
            "budget": {**_money_range(*np.exp([b["p10"], b["p50"], b["p90"]]).tolist()),
                       "rough": bool(is_rough("budget", [b["p10"]], [b["p90"]], self.rule)[0]),
                       "given": budget, "comparison": _comparison(budget_p, budget)},
            "revenue": {**_money_range(*np.exp([r["p10"], r["p50"], r["p90"]]).tolist()),
                        "rough": bool(is_rough("revenue", [r["p10"]], [r["p90"]], self.rule)[0]), "mode": mode,
                        "budget_used": budget if mode == "given" else math.exp(log_budget)},
            "score": {**_score_range(float(s["p10"]), float(s["p50"]), float(s["p90"])), "rough": False},
            "drivers": {
                "budget": self._drivers("budget", self.chain.budget, X, clean, names),
                "revenue": self._drivers("revenue", self.chain.revenue, X_revenue, clean, names,
                                         estimated=("budget",) if mode == "estimated" else ()),
                "score": self._drivers("score", self.score, X, clean, names),
            },
            "comparables": [] if self.index is None else self.index.query(
                clean["genres"], clean["themes"], clean["language"], vector, clean["release_year"], log_budget,
                as_of),
            "warnings": self._warnings(clean, mode, log_budget),
        }
        return out

    def _warnings(self, form: dict[str, Any], mode: str, log_budget: float) -> list[dict[str, str]]:
        out = []
        if math.exp(log_budget) >= BIG_BUDGET:
            which = "Your budget" if mode == "given" else "The estimated budget"
            out.append({"code": "big_budget", "text": (
                f"{which} is {format_money(BIG_BUDGET)} or more. Revenue ranges for films this big were less "
                "reliable on 2019+ films than for smaller ones.")})
        if self.ctx.history.resolve(form.get("director"), "director") is None:
            out.append({"code": "new_director", "text": (
                "We don't know this director, so they count as a first-time director with no track record.")})
        unknown = sum(self.ctx.history.resolve(a, "actor") is None for a in form.get("actors") or [])
        if unknown:
            out.append({"code": "new_actors", "text": (
                f"We don't know {unknown} of the {len(form['actors'])} actors, so they count as having no "
                "earlier films.")})
        for key, code, what in (("countries", "no_country", "production country"), ("companies", "no_studio", "studio")):
            if not form.get(key):
                out.append({"code": code, "text": (
                    f"No {what} given. Past films with none recorded are mostly small ones, so leaving it empty "
                    "lowers the ranges; fill it in if you know it.")})
        last_year = max(int(m["trained_on"].rsplit("-", 1)[-1]) for m in self.manifest["models"].values())
        if form["release_year"] > last_year:
            out.append({"code": "future_release", "text": (
                f"Our data ends in {last_year}. A release in {form['release_year']} is judged on films up to "
                f"{last_year}, so later trends are not included.")})
        return out


_PREDICTOR: Predictor | None = None


def predict(form: dict[str, Any]) -> dict[str, Any]:
    global _PREDICTOR
    if _PREDICTOR is None:
        _PREDICTOR = Predictor.load()
    return _PREDICTOR.predict(form)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] != ["manifest"]:
        sys.exit("usage: uv run python -m ml.predict manifest")
    manifest = write_manifest()
    print(f"model version {manifest['version']} ({len(manifest['files'])} files, LightGBM {manifest['lightgbm']}); "
          f"wrote {FINAL_DIR / MANIFEST} and copied {ROUGH_FILE.name}")


if __name__ == "__main__":
    main()
