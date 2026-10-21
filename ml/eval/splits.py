"""Evaluation data: each model's training view joined with the features table, split by release year.

    load(model, split)                 -> train / validation rows; the test split needs final=True
    load(model, "test", final=True, exclude_covid=True)
                                       -> the test split without 2020-21 (reported both ways for revenue)
    fold_data(model, fold)             -> (train, test) for one rolling-backtest fold, all before 2019

Every row has movie_id, split, the model's target, score_weight, main_genre, budget_2025,
original_language, release_date, typical_revenue / typical_score (the typical film at that date,
from earlier films only) and every feature column.

Targets: revenue and budget as log 2025 dollars, score as vote_average (0-10).
The test split (2019+) stays locked until the final run at the end of Day 6.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data.build_db import DB_FILE
from ml.data.clean import COVID_YEARS, TRAIN_LAST_YEAR, VALIDATION_LAST_YEAR
from ml.features.history import load_films, typical_at

MODELS = ("revenue", "budget", "score")
SPLITS = ("train", "validation", "test")
VIEWS = {"revenue": "v_train_revenue", "budget": "v_train_budget", "score": "v_train_score"}
TARGETS = {"revenue": "LN(v.revenue_2025)", "budget": "LN(v.budget_2025)", "score": "v.vote_average"}
NO_GENRE = "none"


class TestSetLocked(RuntimeError):
    """Raised when the test split is requested without final=True."""


@dataclass(frozen=True)
class Fold:
    name: str
    train_last: int  # train on films released up to and including this year
    test_first: int
    test_last: int


FOLDS = (
    Fold("fold 1", 2009, 2010, 2012),
    Fold("fold 2", 2012, 2013, 2015),
    Fold("fold 3", TRAIN_LAST_YEAR, TRAIN_LAST_YEAR + 1, VALIDATION_LAST_YEAR),  # = train vs validation
)


@lru_cache(maxsize=8)
def _view(model: str, db_path: str) -> pd.DataFrame:
    """Every row of the model's view (all splits), cached per process; callers get copies."""
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}; expected one of {MODELS}")
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT f.*, {TARGETS[model]} AS target, v.title, v.release_date, v.original_language,
                   v.budget_2025, v.score_weight, COALESCE(g.name, '{NO_GENRE}') AS main_genre
            FROM {VIEWS[model]} v
            JOIN features f ON f.movie_id = v.id
            LEFT JOIN movie_genres mg ON mg.movie_id = v.id AND mg.ord = 0
            LEFT JOIN genres g ON g.id = mg.genre_id
            ORDER BY v.release_date, v.id
            """,
            con,
        )
        days = pd.to_datetime(df["release_date"]).values.astype("datetime64[D]").astype(np.int64)
        df = pd.concat([df, typical_at(load_films(con), days)], axis=1)
    finally:
        con.close()
    return df


def load(model: str, split: str, final: bool = False, exclude_covid: bool = False,
         db_path: Path = DB_FILE) -> pd.DataFrame:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {SPLITS}")
    if split == "test" and not final:
        raise TestSetLocked("the test split is locked until the final run; pass final=True only then")
    df = _view(model, str(db_path))
    df = df[df["split"] == split]
    if exclude_covid:
        df = df[~df["year"].isin(COVID_YEARS)]
    return df.reset_index(drop=True).copy()


def fold_data(model: str, fold: Fold, db_path: Path = DB_FILE) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _view(model, str(db_path))
    df = df[df["split"] != "test"]  # folds never touch 2019+
    train = df[df["year"] <= fold.train_last]
    test = df[df["year"].between(fold.test_first, fold.test_last)]
    return train.reset_index(drop=True).copy(), test.reset_index(drop=True).copy()
