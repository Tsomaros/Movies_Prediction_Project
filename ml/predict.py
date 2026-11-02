"""One call from a creator's form to the full prediction: ranges, drivers, comparable films and warnings.

    Predictor.load(out_dir, db_path)  -> the all-data models, feature context, rough rule and comparables
                                         index, checked against out_dir/manifest.json (about 20 s, once)
    predictor.predict(form)           -> a JSON-ready dict (below); raises InvalidForm with readable errors
    predictor.predict_many(forms, full=True)
                                      -> the same for several forms, one call per LightGBM model (compare, the
                                         sweep); full=False keeps only the three ranges
    predictor.embed(text)             -> the synopsis vector, cached (LRU, EMBED_CACHE texts)
    write_manifest(out_dir)           -> out_dir/manifest.json: checksums, training years, versions
    predict(form)                     -> the same with a Predictor loaded once from ml/artifacts/final

The steps follow the plan: validate -> features -> budget -> revenue (budget given or estimated) ->
score -> drivers -> comparables. The output has
- "budget", "revenue", "score": low / middle / high (2025 $, or score points), a text range, the rough
  flag (revenue and budget only), plus revenue's "mode", the budget comparison and the score's "note"
  (young films' TMDB scores are still settling);
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
import threading
from collections import OrderedDict
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
PLATEAU_BUDGET = 300_000_000  # 2025 $; revenue stops rising above about this (audit, Finding 4)
SCORE_NOTE = ("TMDB scores of new films usually start higher and settle during their first year; "
              "this range is for the settled score.")  # audit, Finding 1
EMBED_CACHE = 256  # synopsis vectors kept by Predictor.embed (384 float32 each: about 0.4 MB in all)
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


READ_WAIT_S = 30  # seconds a read waits for the app's refresher to commit: at 0.1 CPU a merge outlasts SQLite's default 5 s


def _read_only(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True, timeout=READ_WAIT_S)


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
    _vectors: OrderedDict[str, np.ndarray] = field(default_factory=OrderedDict, init=False, repr=False)
    _vectors_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def load(cls, out_dir: Path = FINAL_DIR, db_path: Path = DB_FILE, comparables: bool = True,
             context_file: Path | None = None) -> Predictor:
        """context_file: the track records prebuilt by `python -m ml.features.build prebuilt` (the Docker image's
        way to skip the memory-hungry build); None builds them from the database."""
        manifest = check_manifest(out_dir)
        with closing(_read_only(db_path)) as con:
            ctx = FeatureContext.load(con, prebuilt=context_file)
        index = Index.load(out_dir / INDEX_FILE.name) if comparables else None
        chain, score = Chain.load(out_dir), load_model("score", out_dir)
        for model in (chain.revenue, chain.budget, score):
            model.predict_threads = 1  # one request at a time on a small host: threads only add overhead
        return cls(chain, score, ctx, load_rule(out_dir / ROUGH_FILE.name),
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

    def embed(self, text: str) -> np.ndarray:
        """The synopsis vector, from an LRU cache of EMBED_CACHE texts keyed by the text's SHA-1 (the text is the
        contract's cleaned synopsis). The vector is read-only: callers share it."""
        key = hashlib.sha1(text.encode("utf-8")).hexdigest()
        with self._vectors_lock:
            if key in self._vectors:
                self._vectors.move_to_end(key)
                return self._vectors[key]
        vector = self.ctx.embed(text)
        vector.flags.writeable = False
        with self._vectors_lock:
            self._vectors[key] = vector
            while len(self._vectors) > EMBED_CACHE:
                self._vectors.popitem(last=False)
        return vector

    def _drivers(self, target: str, model: LgbmQuantile, X: pd.DataFrame, forms: list[dict[str, Any]],
                 names: list[dict[str, Any]], estimated: list[tuple[str, ...]],
                 shown: np.ndarray | None = None) -> list[dict[str, list[dict[str, Any]]]]:
        """One explanation per row of X; one pred_contrib call for all rows."""
        c = contributions(model, X, shown=shown)
        grouped = group_contributions(c, self.groups)
        out = []
        for i in range(len(X)):
            row = c.iloc[i]
            drivers = [{**d, "main_feature": main_feature(row, d["group"], self.groups)}
                       for d in top_drivers(target, grouped.iloc[i], estimated=estimated[i])]
            out.append(explain(target, drivers, forms[i], X.iloc[i].to_dict(), names[i]))
        return out

    def predict(self, form: dict[str, Any]) -> dict[str, Any]:
        return self.predict_many([form])[0]

    def predict_many(self, forms: list[dict[str, Any]], full: bool = True) -> list[dict[str, Any]]:
        """predict() for several forms with one call per LightGBM model (V1.5: compare and the sweep); each answer
        equals predict(form) alone. full=False gives only "model_version", "as_of" and the three ranges
        (no drivers, comparables or warnings: what the sweep shows)."""
        cleans = []
        for form in forms:
            clean, errors = validate(form, themes=list(self.ctx.themes))
            if errors:
                raise InvalidForm(errors)
            cleans.append(clean)
        as_ofs = [api_as_of(c) for c in cleans]
        vectors = [self.embed(c["synopsis"]) if c.get("synopsis") else None for c in cleans]
        rows = [build_features(c, a, self.ctx, synopsis_vector=v) for c, a, v in zip(cleans, as_ofs, vectors)]
        X = pd.DataFrame(rows, dtype=float)  # one row with missing values would otherwise be "object"
        budgets = [c.get("budget") for c in cleans]

        budget_p = self.chain.budget.predict(X)
        revenue_p, modes, log_budgets = self.chain.predict_revenue_rows(X, budgets, budget_p["p50"].to_numpy())
        score_p = self.score.predict(X)

        outs = []
        for i, clean in enumerate(cleans):
            b, r, s = (p.iloc[i] for p in (budget_p, revenue_p, score_p))
            budget, mode, log_budget = budgets[i], modes[i], float(log_budgets[i])
            outs.append({
                "model_version": self.manifest["version"],
                "as_of": date(clean["release_year"], clean["release_month"], 1).isoformat(),
                "budget": {**_money_range(*np.exp([b["p10"], b["p50"], b["p90"]]).tolist()),
                           "rough": bool(is_rough("budget", [b["p10"]], [b["p90"]], self.rule)[0]),
                           "given": budget, "comparison": _comparison(budget_p.iloc[[i]], budget)},
                "revenue": {**_money_range(*np.exp([r["p10"], r["p50"], r["p90"]]).tolist()),
                            "rough": bool(is_rough("revenue", [r["p10"]], [r["p90"]], self.rule)[0]), "mode": mode,
                            "budget_used": budget if mode == "given" else math.exp(log_budget)},
                "score": {**_score_range(float(s["p10"]), float(s["p50"]), float(s["p90"])), "rough": False,
                          "note": SCORE_NOTE},
            })
        if not full:
            return outs

        names = [self.names(c) for c in cleans]
        estimated = [("budget",) if m == "estimated" else () for m in modes]
        drivers = {
            "budget": self._drivers("budget", self.chain.budget, X, cleans, names, [()] * len(cleans),
                                    shown=budget_p["p50"].to_numpy()),
            "revenue": self._drivers("revenue", self.chain.revenue, X.assign(log_budget=log_budgets), cleans, names,
                                     estimated),
            "score": self._drivers("score", self.score, X, cleans, names, [()] * len(cleans),
                                   shown=score_p["p50"].to_numpy()),
        }
        for i, (clean, out) in enumerate(zip(cleans, outs)):
            log_budget = float(log_budgets[i])
            out["drivers"] = {t: drivers[t][i] for t in ("budget", "revenue", "score")}
            out["comparables"] = [] if self.index is None else self.index.query(
                clean["genres"], clean["themes"], clean["language"], vectors[i], clean["release_year"], log_budget,
                as_ofs[i])
            out["warnings"] = self._warnings(clean, modes[i], log_budget)
        return outs

    def _warnings(self, form: dict[str, Any], mode: str, log_budget: float) -> list[dict[str, str]]:
        out = []
        if math.exp(log_budget) >= BIG_BUDGET:
            which = "Your budget" if mode == "given" else "The estimated budget"
            out.append({"code": "big_budget", "text": (
                f"{which} is {format_money(BIG_BUDGET)} or more. Revenue ranges for films this big were less "
                f"reliable on 2019+ films than for smaller ones, and budgets above {format_money(PLATEAU_BUDGET)} "
                "don't raise the revenue estimate any further.")})
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
