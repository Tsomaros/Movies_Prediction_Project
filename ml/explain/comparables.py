"""Comparable films: the past films most like a creator's planned film, with their real money and score.

    Index.build(con, cache, theme_names=None)    -> the pool, from data/movies.db and the embedding cache
    index.save(path) / Index.load(path)          -> ml/artifacts/final/comparables.npz (not in git)
    index.query(genres, themes, language, vector, year, log_budget, as_of, n=5, exclude=None)
                                                 -> up to n films as JSON-ready dicts, most similar first;
                                                    as_of=None (movie pages) allows any year, exclude skips one id
    index.row(movie_id)                          -> the film's position in the pool, or None
    similarity(index, ...)                       -> the similarity of every film in the pool (0-1)

The pool is every released film with a usable audience score (`score_ok`, about 33,000). Only films
released strictly before `as_of` (days since 1970-01-01) can be returned, so a film planned for 2005
never gets a 2010 comparable. Of the TOP_POOL most similar, the n with a real budget or revenue come
first; films with no reported money only fill the remaining places ("not reported" in the app).

Similarity is a weighted average (WEIGHTS) of
- genres and themes: Jaccard overlap of the two sets (0 when either side has none);
- language: 1 when the original language is the same, else 0;
- synopsis: cosine of the 384-number MiniLM vectors (unit length, stored as float16), clipped at 0;
  left out of the average when the creator gave no synopsis;
- era: exp(-years apart / ERA_YEARS);
- budget level: exp(-|log budget difference|), with the creator's budget or the budget model's middle;
  a film with no reported budget gets 0.5.

The weights were set in notebooks/07_explanations.ipynb on 600 films from 2016-18 (each judged at its
release): adding language and doubling budget brought the comparables' median revenue closer to the
film's own (MAE log 1.88 -> 1.80) and raised same-language comparables from 60% to 84%. A tie-break
towards well-known films was tried and dropped: their revenue was further off.

CLI: uv run python -m ml.explain.comparables   (writes ml/artifacts/final/comparables.npz)
"""

from __future__ import annotations

import sqlite3
import sys
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.features.basic import slug
from ml.features.contract import GENRES
from ml.features.history import day_number
from ml.features.synopsis import EMBEDDINGS_FILE
from ml.features.themes import load_themes

INDEX_FILE = Path("ml/artifacts/final/comparables.npz")
WEIGHTS = {"genres": 0.3, "themes": 0.2, "synopsis": 0.3, "era": 0.1, "budget": 0.2, "language": 0.1}
ERA_YEARS = 10.0
UNKNOWN_BUDGET = 0.5  # budget closeness of a film with no reported budget
TOP_POOL = 50
N_COMPARABLES = 5


@dataclass
class Index:
    ids: np.ndarray  # TMDB ids
    titles: np.ndarray
    years: np.ndarray
    days: np.ndarray  # release day, days since 1970-01-01
    posters: np.ndarray  # TMDB poster path ("" when none)
    budget: np.ndarray  # 2025 $, NaN when unknown or suspect
    revenue: np.ndarray
    score: np.ndarray  # TMDB vote_average
    languages: np.ndarray  # original language code ("" when unknown)
    genres: np.ndarray  # bool, one column per contract GENRES
    themes: np.ndarray  # bool, one column per theme in themes.json
    theme_names: np.ndarray
    vectors: np.ndarray  # unit MiniLM vectors (zeros without an overview): float16 on disk, float32 in memory

    def __post_init__(self) -> None:
        self.vectors = np.asarray(self.vectors, dtype=np.float32)  # converted once, not on every query
        # numpy stores text as fixed-width UTF-32 (titles: 127 characters each, 17 MB); plain strings take ~3 MB
        self.titles, self.posters = (np.asarray(a, dtype=object) for a in (self.titles, self.posters))

    @classmethod
    def build(cls, con: sqlite3.Connection, cache: Path = EMBEDDINGS_FILE,
              theme_names: Sequence[str] | None = None) -> Index:
        theme_names = list(load_themes() if theme_names is None else theme_names)
        flags = [f"genre_{slug(g)}" for g in GENRES] + [f"theme_{slug(t)}" for t in theme_names]
        films = pd.read_sql(
            f"""SELECT m.id, m.title, m.year, m.release_date, COALESCE(m.poster_path, '') AS poster_path,
                       CASE WHEN m.money_suspect THEN NULL ELSE m.budget_2025 END AS budget,
                       CASE WHEN m.money_suspect THEN NULL ELSE m.revenue_2025 END AS revenue,
                       m.vote_average, COALESCE(m.original_language, '') AS language,
                       {', '.join('f.' + c for c in flags)}
                FROM movies m JOIN features f ON f.movie_id = m.id
                WHERE m.score_ok ORDER BY m.id""", con)
        z = np.load(cache)
        row = {int(i): k for k, i in enumerate(z["ids"])}
        vectors = np.zeros((len(films), z["vectors"].shape[1]), dtype=np.float16)
        have = [k for k, i in enumerate(films["id"]) if int(i) in row]
        vectors[have] = z["vectors"][[row[int(films["id"].iloc[k])] for k in have]].astype(np.float16)
        n_genres = len(GENRES)
        flag_values = films[flags].to_numpy(dtype=bool)
        return cls(
            ids=films["id"].to_numpy(np.int64), titles=films["title"].to_numpy(str),
            years=films["year"].to_numpy(np.int32),
            days=np.array([day_number(d) for d in films["release_date"]], dtype=np.int32),
            posters=films["poster_path"].to_numpy(str), budget=films["budget"].to_numpy(float),
            revenue=films["revenue"].to_numpy(float), score=films["vote_average"].to_numpy(float),
            languages=films["language"].to_numpy(str),
            genres=flag_values[:, :n_genres], themes=flag_values[:, n_genres:],
            theme_names=np.array(theme_names), vectors=vectors)

    def save(self, path: Path = INDEX_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {f.name: getattr(self, f.name) for f in fields(self)}
        np.savez_compressed(path, **{**arrays, "vectors": self.vectors.astype(np.float16),
                                     "titles": self.titles.astype(str), "posters": self.posters.astype(str)})

    @classmethod
    def load(cls, path: Path = INDEX_FILE) -> Index:
        z = np.load(path)
        return cls(**{f.name: z[f.name] for f in fields(cls)})

    def __len__(self) -> int:
        return len(self.ids)

    def row(self, movie_id: int) -> int | None:
        i = int(np.searchsorted(self.ids, movie_id))  # ids are sorted (ORDER BY m.id)
        return i if i < len(self.ids) and self.ids[i] == movie_id else None

    def query(self, genres: Sequence[str], themes: Sequence[str], language: str | None, vector: np.ndarray | None,
              year: int, log_budget: float | None, as_of: int | None, n: int = N_COMPARABLES,
              exclude: int | None = None) -> list[dict[str, Any]]:
        """as_of=None drops the date rule (a movie page's similar films, any year); `exclude` is a TMDB id
        that is never returned (the film itself)."""
        sim = similarity(self, genres, themes, language, vector, year, log_budget)
        if as_of is not None:
            sim[self.days >= as_of] = -np.inf  # only films released before the planned date
        if exclude is not None:
            sim[self.ids == exclude] = -np.inf
        k = min(TOP_POOL, int(np.isfinite(sim).sum()))
        if k == 0:
            return []
        top = np.argpartition(-sim, k - 1)[:k]
        top = top[np.argsort(-sim[top], kind="stable")]
        money = ~np.isnan(self.budget[top]) | ~np.isnan(self.revenue[top])
        chosen = [*top[money][:n], *top[~money][:max(0, n - int(money.sum()))]]
        return [self._film(i, sim[i]) for i in chosen]

    def _film(self, i: int, sim: float) -> dict[str, Any]:
        money = lambda x: None if np.isnan(x) else float(x)
        return {"id": int(self.ids[i]), "title": str(self.titles[i]), "year": int(self.years[i]),
                "poster_path": str(self.posters[i]) or None, "budget": money(self.budget[i]),
                "revenue": money(self.revenue[i]), "score": float(self.score[i]), "similarity": round(float(sim), 3)}


def _jaccard(flags: np.ndarray, wanted: np.ndarray) -> np.ndarray:
    if not wanted.any():
        return np.zeros(len(flags))
    both = (flags & wanted).sum(axis=1)
    either = (flags | wanted).sum(axis=1)
    return both / either  # either >= 1 because wanted has at least one flag


def similarity(index: Index, genres: Sequence[str], themes: Sequence[str], language: str | None,
               vector: np.ndarray | None, year: int, log_budget: float | None) -> np.ndarray:
    parts = {
        "genres": _jaccard(index.genres, np.isin(np.array(GENRES), list(genres))),
        "themes": _jaccard(index.themes, np.isin(index.theme_names, list(themes))),
        "era": np.exp(-np.abs(index.years - year) / ERA_YEARS),
    }
    if language:
        parts["language"] = (index.languages == language).astype(float)
    if log_budget is not None and np.isfinite(log_budget):
        with np.errstate(divide="ignore", invalid="ignore"):
            closeness = np.exp(-np.abs(np.log(index.budget) - log_budget))
        parts["budget"] = np.where(np.isnan(index.budget), UNKNOWN_BUDGET, closeness)
    if vector is not None:
        v = np.asarray(vector, dtype=np.float32)
        v = v / max(float(np.linalg.norm(v)), 1e-12)
        parts["synopsis"] = np.clip(index.vectors @ v, 0.0, 1.0)
    total = sum(WEIGHTS[p] for p in parts)
    return sum(WEIGHTS[p] * s for p, s in parts.items()) / total


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    start = time.perf_counter()
    with sqlite3.connect(DB_FILE) as con:
        index = Index.build(con)
    index.save()
    money = int((~np.isnan(index.budget) | ~np.isnan(index.revenue)).sum())
    with_vector = int((np.abs(index.vectors).sum(axis=1) > 0).sum())
    print(f"{len(index):,} films ({money:,} with a budget or revenue, {with_vector:,} with a synopsis vector); "
          f"wrote {INDEX_FILE} ({INDEX_FILE.stat().st_size / 1e6:.0f} MB, {time.perf_counter() - start:.0f} s)")


if __name__ == "__main__":
    main()
