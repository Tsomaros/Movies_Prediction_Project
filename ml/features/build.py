"""The one feature function, shared by the training table and the API.

    FeatureContext.load(con)                 -> everything the features need, loaded once
    build_features(form, as_of, ctx)         -> one feature row for a contract-shaped form
    api_as_of(form)                          -> the date a creator's film is judged at (1st of its release month)
    FilmForms.from_db(con)                   -> every film's own data, for turning films into forms
    film_to_form(movie_id, films, ctx)       -> a training film written as a creator form
    build_table(con, ctx)                    -> the features DataFrame for every film
    feature_list()                           -> name, source and allowed models for each feature

Training films go through exactly the same build_features call as a creator's form: the film is
written as a form (film_to_form) and judged at its release date, so earlier films are the only
history it sees. A creator's film is judged at the first day of its release month.

CLI: uv run python -m ml.features.build   (writes the `features` table to data/movies.db
                                            and ml/features/feature_list.json)
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.features.basic import Franchises, basic_features, load_vocab
from ml.features.contract import certification_category
from ml.features.history import History, day_number
from ml.features.history import feature_names as history_feature_names
from ml.features.synopsis import FEATURE_NAMES as SYNOPSIS_FEATURES
from ml.features.synopsis import EMBEDDINGS_FILE, embed_overviews, load_pca, synopsis_features
from ml.features.text import Embedder
from ml.features.themes import load_themes

FEATURE_LIST_FILE = Path("ml/features/feature_list.json")
MODELS = ("revenue", "budget", "score")
NOT_ALLOWED = {"log_budget": {"budget"}}  # a model never gets its own target as an input


@dataclass
class FeatureContext:
    history: History
    franchises: Franchises
    vocab: dict[str, Any]
    themes: dict[str, set[int]]
    pca: dict[str, np.ndarray]
    embedder: Embedder | None = None  # only needed for a synopsis that has no cached vector

    @classmethod
    def load(cls, con: sqlite3.Connection, embedder: Embedder | None = None) -> FeatureContext:
        return cls(History.from_db(con), Franchises.from_db(con), load_vocab(), load_themes(), load_pca(), embedder)

    def embed(self, text: str) -> np.ndarray:
        if self.embedder is None:
            self.embedder = Embedder()
        return self.embedder.embed([text])[0]


def api_as_of(form: dict[str, Any]) -> int:
    return day_number(date(form["release_year"], form["release_month"], 1))


def build_features(
    form: dict[str, Any], as_of: int, ctx: FeatureContext, synopsis_vector: np.ndarray | None = None
) -> dict[str, float]:
    """Feature row for a contract-shaped form judged at day `as_of` (days since 1970-01-01).

    `synopsis_vector` lets the training table pass a cached embedding of form["synopsis"]; it is the
    same vector embedding that text gives (checked in the tests)."""
    director = ctx.history.resolve(form.get("director"), "director")
    actors = [ctx.history.resolve(ref, "actor") for ref in form.get("actors") or []]
    if synopsis_vector is None and form.get("synopsis"):
        synopsis_vector = ctx.embed(form["synopsis"])
    return {
        **basic_features(form, as_of, ctx.vocab, ctx.franchises, ctx.themes),
        **ctx.history.director_features([director], as_of),
        **ctx.history.actor_features(actors, as_of),
        **synopsis_features(synopsis_vector, ctx.pca),
    }


# ---------------------------------------------------------------- training films as forms


@dataclass
class FilmForms:
    movies: pd.DataFrame  # indexed by id
    genres: pd.Series  # movie id -> list of genre names
    directors: pd.Series  # movie id -> list of person ids
    actors: pd.Series  # movie id -> list of person ids in billing order
    companies: pd.Series
    countries: pd.Series
    keywords: pd.Series  # movie id -> set of keyword ids

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> FilmForms:
        def lists(sql: str) -> pd.Series:
            df = pd.read_sql_query(sql, con)
            return df.groupby("movie_id", sort=False)[df.columns[1]].agg(list)

        movies = pd.read_sql_query(
            "SELECT id, split, release_date, year, month, runtime, original_language, us_certification, "
            "collection_id, budget_2025, overview FROM movies WHERE release_date IS NOT NULL", con).set_index("id")
        return cls(
            movies=movies,
            genres=lists("SELECT mg.movie_id, g.name FROM movie_genres mg JOIN genres g ON g.id = mg.genre_id ORDER BY g.name"),
            directors=lists("SELECT movie_id, person_id FROM movie_crew WHERE job = 'Director' ORDER BY movie_id, person_id"),
            actors=lists("SELECT movie_id, person_id FROM movie_cast ORDER BY movie_id, ord"),
            companies=lists("SELECT movie_id, company_id FROM movie_companies ORDER BY movie_id, company_id"),
            countries=lists("SELECT movie_id, country FROM movie_countries ORDER BY movie_id, country"),
            keywords=lists("SELECT movie_id, keyword_id FROM movie_keywords").map(set),
        )


def film_to_form(movie_id: int, films: FilmForms, ctx: FeatureContext) -> dict[str, Any]:
    """A training film written as a creator form (ids instead of names; missing values stay missing).

    The form has one director; for a film with several, the one with the most earlier films is used."""
    m = films.movies.loc[movie_id]
    as_of = day_number(m["release_date"])
    directors = films.directors.get(movie_id, [])
    director = max(directors, key=lambda pid: ctx.history.person(pid, "director", as_of)["n_films"], default=None)
    keywords = films.keywords.get(movie_id, set())

    def value(column: str) -> Any:
        v = m[column]
        return None if pd.isna(v) else v

    return {
        "genres": films.genres.get(movie_id, []),
        "release_year": int(m["year"]),
        "release_month": int(m["month"]),
        "runtime": None if value("runtime") is None else int(m["runtime"]),
        "language": value("original_language"),
        "certification": certification_category(value("us_certification")),
        "director": None if director is None else {"id": int(director), "name": None},
        "actors": [{"id": int(pid), "name": None} for pid in films.actors.get(movie_id, [])],
        "themes": [name for name, ids in ctx.themes.items() if keywords & ids],
        "companies": [{"id": int(cid), "name": None} for cid in films.companies.get(movie_id, [])],
        "countries": films.countries.get(movie_id, []),
        "franchise": None if value("collection_id") is None else {"id": int(m["collection_id"]), "name": None},
        "synopsis": value("overview"),
        "budget": value("budget_2025"),
    }


def build_table(con: sqlite3.Connection, ctx: FeatureContext, cache: Path = EMBEDDINGS_FILE) -> pd.DataFrame:
    films = FilmForms.from_db(con)
    ids, vectors = embed_overviews(con, ctx.embedder, cache)
    vector_of = dict(zip(ids.tolist(), vectors))
    rows = []
    for movie_id in films.movies.index:
        form = film_to_form(movie_id, films, ctx)
        as_of = day_number(films.movies.at[movie_id, "release_date"])
        rows.append({"movie_id": int(movie_id), "split": films.movies.at[movie_id, "split"],
                     **build_features(form, as_of, ctx, vector_of.get(movie_id))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- feature list


def _source(name: str) -> str:
    if name.startswith(("director_", "actors_")):
        return "track record (earlier films only)"
    if name.startswith(("synopsis_", "has_synopsis")):
        return "synopsis (MiniLM + PCA)"
    if name.startswith("franchise_") or name == "is_franchise":
        return "franchise (earlier films in the collection)"
    for prefix, source in [("genre_", "genres"), ("theme_", "themes"), ("language_", "language"),
                           ("country_", "countries"), ("company_", "companies"), ("cert_", "certification")]:
        if name.startswith(prefix):
            return source
    return {"major_studio": "companies", "log_budget": "budget (2025 dollars)", "runtime": "runtime"}.get(
        name, "release date")


def feature_list(columns: list[str]) -> list[dict[str, Any]]:
    return [{"name": c, "source": _source(c), "models": [m for m in MODELS if m not in NOT_ALLOWED.get(c, set())]}
            for c in columns]


def write_table(con: sqlite3.Connection, table: pd.DataFrame) -> None:
    """Replace the features table in one transaction, so a failed write keeps the old one."""
    with con:
        con.execute("DROP TABLE IF EXISTS features_tmp")
        table.to_sql("features_tmp", con, index=False)
        con.execute("DROP TABLE IF EXISTS features")
        con.execute("ALTER TABLE features_tmp RENAME TO features")
        con.execute("CREATE UNIQUE INDEX idx_features_movie ON features(movie_id)")
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('features', ?)", (json.dumps({
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "films": len(table),
            "features": len(table.columns) - 2,
        }),))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    start = time.perf_counter()
    with sqlite3.connect(DB_FILE) as con:
        ctx = FeatureContext.load(con)
        table = build_table(con, ctx)
        write_table(con, table)
    columns = [c for c in table.columns if c not in ("movie_id", "split")]
    expected = len(history_feature_names()) + len(SYNOPSIS_FEATURES)
    FEATURE_LIST_FILE.write_text(json.dumps(feature_list(columns), indent=1) + "\n", encoding="utf-8")
    print(f"Wrote features for {len(table):,} films x {len(columns)} features "
          f"({expected} track-record and synopsis) in {time.perf_counter() - start:.0f} s; {FEATURE_LIST_FILE} updated")


if __name__ == "__main__":
    main()
