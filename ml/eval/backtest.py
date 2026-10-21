"""Rolling backtest: refit on earlier years, score the next three, for each fold in ml.eval.splits.FOLDS.

    backtest(model_factory, target)              -> {"folds": [...], "mean": {...}, "std": {...}}
    refit_synopsis(train, test, train_last)      -> copies of both with the synopsis numbers rebuilt from
                                                    a PCA fitted on films released up to train_last only

| Fold | Train | Test    |
| 1    | <=2009 | 2010-12 |
| 2    | <=2012 | 2013-15 |
| 3    | <=2015 | 2016-18 |   (the same as train vs validation)

The features table's synopsis PCA was fitted on films up to 2015, so folds 1 and 2 would see their
test years through it. A model that uses the synopsis numbers sets `uses_synopsis = True` and gets
fold-fitted ones instead (a `synopsis_components` attribute asks for more than 16); baselines don't use them. Like the saved PCA, a fold's PCA is fitted on
every film from its train years that has an overview, not only the films in the model's view.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.eval.evaluate import score
from ml.eval.splits import FOLDS, fold_data
from ml.features.synopsis import EMBEDDINGS_FILE, FEATURE_NAMES, N_COMPONENTS, fit_pca

SYNOPSIS_COLUMNS = FEATURE_NAMES[:-1]  # synopsis_00..15 (has_synopsis doesn't change)


@lru_cache(maxsize=2)
def _embeddings(cache: str, db_path: str) -> pd.DataFrame:
    """Cached overview vectors with each film's release year."""
    with np.load(cache) as data:
        ids, vectors = data["ids"], data["vectors"]
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        years = dict(con.execute("SELECT id, year FROM movies"))
    finally:
        con.close()
    return pd.DataFrame({"movie_id": ids, "year": [years.get(int(i)) for i in ids], "vector": list(vectors)})


def synopsis_columns(n_components: int = N_COMPONENTS) -> list[str]:
    return [f"synopsis_{i:02d}" for i in range(n_components)]


def refit_synopsis(train: pd.DataFrame, test: pd.DataFrame, train_last: int,
                   cache: Path = EMBEDDINGS_FILE, db_path: Path = DB_FILE,
                   n_components: int = N_COMPONENTS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """n_components above 16 adds synopsis_16.. columns (the Day 5 ablation's 32-number row)."""
    emb = _embeddings(str(cache), str(db_path))
    fit_on = np.stack(emb.loc[emb["year"] <= train_last, "vector"].to_numpy())
    pca = fit_pca(fit_on, n_components)
    mean, components = np.array(pca["mean"], dtype=np.float32), np.array(pca["components"], dtype=np.float32)
    vector_of = dict(zip(emb["movie_id"].tolist(), emb["vector"]))
    columns = synopsis_columns(n_components)

    def apply(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        values = np.zeros((len(df), len(columns)))
        for i, (movie_id, has) in enumerate(zip(df["movie_id"], df["has_synopsis"])):
            if has and movie_id in vector_of:
                values[i] = (vector_of[movie_id] - mean) @ components.T
        df[columns] = values
        return df

    return apply(train), apply(test)


def backtest(model_factory: Callable[[], Any], target: str) -> dict[str, Any]:
    folds = []
    for fold in FOLDS:
        train, test = fold_data(target, fold)
        model = model_factory()
        if getattr(model, "uses_synopsis", False):
            train, test = refit_synopsis(train, test, fold.train_last,
                                         n_components=getattr(model, "synopsis_components", N_COMPONENTS))
        model.fit(train)
        folds.append({
            "fold": fold.name,
            "train_years": f"<={fold.train_last}",
            "test_years": f"{fold.test_first}-{fold.test_last}",
            "train_n": len(train),
            "metrics": score(target, test, model.predict(test)),
        })
    metrics = pd.DataFrame([f["metrics"] for f in folds])
    return {
        "folds": folds,
        "mean": metrics.mean().to_dict(),
        "std": metrics.std(ddof=0).to_dict(),  # spread across the three folds
    }
