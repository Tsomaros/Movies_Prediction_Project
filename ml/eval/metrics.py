"""Evaluation metrics. Money targets (revenue, budget) are passed as log 2025 dollars; score as 0-10.

    money_metrics(y, p10, p50, p90)         -> n, mae_log (selection), median_pct_error, within_2x (headline),
                                               spearman, coverage, width (median high/low ratio)
    score_metrics(y, p10, p50, p90, weight) -> n, mae, weighted_mae, spearman, coverage, width (mean points)

Each metric is also a small function, so tests can check them on hand-computed examples.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import spearmanr

TWO_X = math.log(2)


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def mae(y, pred) -> float:
    return float(np.mean(np.abs(_arr(pred) - _arr(y))))


def weighted_mae(y, pred, weight) -> float:
    return float(np.average(np.abs(_arr(pred) - _arr(y)), weights=_arr(weight)))


def median_pct_error(log_y, log_pred) -> float:
    """Median of |predicted / actual - 1| in dollars, as a percentage."""
    return float(100 * np.median(np.abs(np.exp(_arr(log_pred) - _arr(log_y)) - 1)))


def within_2x(log_y, log_pred) -> float:
    """Share of films whose prediction is between half and double the actual value."""
    return float(np.mean(np.abs(_arr(log_pred) - _arr(log_y)) <= TWO_X + 1e-12))


def spearman(y, pred) -> float:
    """Rank correlation; NaN when the prediction is the same for every film (e.g. a global median)."""
    y, pred = _arr(y), _arr(pred)
    if np.ptp(pred) == 0 or np.ptp(y) == 0:
        return float("nan")
    return float(spearmanr(y, pred).statistic)


def coverage(y, low, high) -> float:
    y = _arr(y)
    return float(np.mean((_arr(low) <= y) & (y <= _arr(high))))


def money_width(log_low, log_high) -> float:
    """Median high/low ratio of the range in dollars (e.g. 4.0 means the high end is 4x the low end)."""
    return float(np.median(np.exp(_arr(log_high) - _arr(log_low))))


def score_width(low, high) -> float:
    """Mean width of the range in score points."""
    return float(np.mean(_arr(high) - _arr(low)))


def money_metrics(log_y, p10, p50, p90) -> dict[str, float]:
    return {
        "n": int(len(_arr(log_y))),
        "mae_log": mae(log_y, p50),
        "median_pct_error": median_pct_error(log_y, p50),
        "within_2x": within_2x(log_y, p50),
        "spearman": spearman(log_y, p50),
        "coverage": coverage(log_y, p10, p90),
        "width": money_width(p10, p90),
    }


def score_metrics(y, p10, p50, p90, weight) -> dict[str, float]:
    return {
        "n": int(len(_arr(y))),
        "mae": mae(y, p50),
        "weighted_mae": weighted_mae(y, p50, weight),
        "spearman": spearman(y, p50),
        "coverage": coverage(y, p10, p90),
        "width": score_width(p10, p90),
    }
