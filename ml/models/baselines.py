"""B0-B2 baselines for revenue, budget and score, with the same fit / predict interface as later models.

    model.fit(train_df)    -> learns from train rows (ml.eval.splits.load output)
    model.predict(df)      -> DataFrame with p10, p50, p90 in the target's units (log 2025 $ or 0-10 score)
    BASELINES[target]      -> the B0, B1 and B2 classes for that target

|     | Revenue                                   | Budget                                 | Score                                          |
| B0  | global median                             | global median                          | global median                                  |
| B1  | median per main genre                     | median per main genre                  | median per main genre                          |
| B2  | log budget + genre median log multiple    | genre median + log sequel factor       | genre median + w x (director score - typical)  |

Genres with fewer than MIN_GENRE_FILMS train films use the global value. Every range is the middle
prediction plus the 10th and 90th percentiles of that baseline's own train residuals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_GENRE_FILMS = 30
LOW, HIGH = 0.10, 0.90
SCORE_RANGE = (0.0, 10.0)


class Baseline:
    name = "baseline"
    target = ""

    def fit(self, train: pd.DataFrame) -> Baseline:
        self._fit_center(train)
        residuals = train["target"].to_numpy() - self._center(train)
        self.low, self.high = np.nanquantile(residuals, [LOW, HIGH])
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        c = self._center(df)
        out = pd.DataFrame({"p10": c + self.low, "p50": c, "p90": c + self.high}, index=df.index)
        if self.target == "score":
            out = out.clip(*SCORE_RANGE)
        return out

    def _fit_center(self, train: pd.DataFrame) -> None:
        raise NotImplementedError

    def _center(self, df: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError


def _genre_medians(values: pd.Series, genres: pd.Series) -> tuple[dict[str, float], float]:
    """Median per genre (genres with enough films only) and the global median."""
    counts = genres.value_counts()
    kept = counts.index[counts >= MIN_GENRE_FILMS]
    medians = values.groupby(genres).median()
    return {g: float(medians[g]) for g in kept}, float(values.median())


def _lookup(genres: pd.Series, medians: dict[str, float], fallback: float) -> np.ndarray:
    return genres.map(medians).fillna(fallback).to_numpy(float)


class GlobalMedian(Baseline):
    name = "B0 global median"

    def _fit_center(self, train):
        self.median = float(train["target"].median())

    def _center(self, df):
        return np.full(len(df), self.median)


class GenreMedian(Baseline):
    name = "B1 genre median"

    def _fit_center(self, train):
        self.medians, self.fallback = _genre_medians(train["target"], train["main_genre"])

    def _center(self, df):
        return _lookup(df["main_genre"], self.medians, self.fallback)


class RevenueMultiple(Baseline):
    """Revenue = budget x the main genre's median revenue / budget multiple."""

    name = "B2 budget x genre multiple"
    target = "revenue"

    def _fit_center(self, train):
        self.multiples, self.fallback = _genre_medians(train["target"] - train["log_budget"], train["main_genre"])

    def _center(self, df):
        return df["log_budget"].to_numpy(float) + _lookup(df["main_genre"], self.multiples, self.fallback)


class BudgetSequel(Baseline):
    """Budget = genre median x a sequel factor (how much more sequels cost than their genre's median)."""

    name = "B2 genre median x sequel factor"
    target = "budget"

    def _fit_center(self, train):
        self.medians, self.fallback = _genre_medians(train["target"], train["main_genre"])
        base = _lookup(train["main_genre"], self.medians, self.fallback)
        sequel = train["is_franchise"].to_numpy() == 1
        self.sequel_factor = float(np.median(train["target"].to_numpy()[sequel] - base[sequel])) if sequel.any() else 0.0

    def _center(self, df):
        base = _lookup(df["main_genre"], self.medians, self.fallback)
        return base + self.sequel_factor * (df["is_franchise"].to_numpy() == 1)


class ScoreDirector(Baseline):
    """Score = genre median + w x (director's shrunk earlier score - typical score at that date), w fitted on train."""

    name = "B2 genre median + director"
    target = "score"

    def _fit_center(self, train):
        self.medians, self.fallback = _genre_medians(train["target"], train["main_genre"])
        d = self._director_gap(train)
        r = train["target"].to_numpy() - _lookup(train["main_genre"], self.medians, self.fallback)
        self.weight = float(np.sum(d * r) / np.sum(d * d)) if np.any(d) else 0.0  # least squares, no intercept

    def _director_gap(self, df):
        gap = df["director_score"].to_numpy(float) - df["typical_score"].to_numpy(float)
        return np.nan_to_num(gap)  # no history yet (earliest 1960 films): no adjustment

    def _center(self, df):
        return _lookup(df["main_genre"], self.medians, self.fallback) + self.weight * self._director_gap(df)


def _for(target: str, cls: type[Baseline]) -> type[Baseline]:
    return type(f"{cls.__name__}_{target}", (cls,), {"target": target})


BASELINES: dict[str, list[type[Baseline]]] = {
    "revenue": [_for("revenue", GlobalMedian), _for("revenue", GenreMedian), RevenueMultiple],
    "budget": [_for("budget", GlobalMedian), _for("budget", GenreMedian), BudgetSequel],
    "score": [_for("score", GlobalMedian), _for("score", GenreMedian), ScoreDirector],
}
