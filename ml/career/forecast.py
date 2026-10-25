"""The track-record forecast of a person's next film (Day 14.8): pure maths, no I/O; the score and log revenue.

    MIN_RATED                                    -> rated films needed for a forecast (5)
    RoleSettings(h, k, q)                        -> one role's settings from the backtest: half-life in years
                                                    (math.inf: every film counts the same), shrinkage strength in
                                                    films, range multiplier
    Forecast(low, mid, high, n_rated, own_avg, own_share, db_avg)
    track_record(history, settings, mu, sigma_pop, bounds=(1.0, 10.0))
                                                 -> Forecast, or None with fewer than MIN_RATED films; bounds
                                                    None: no clipping (revenue, in log 2025 $)
    rolling_line(points, window=5)               -> the career line: a centred mean over the ordered films

history is (year, value) of the films that count: rated films' scores, or the log 2025 $ of trusted revenues.
With L the latest year, a film counts w = 0.5 ** ((L - year) / h). Their weighted average m is trusted
n_eff / (n_eff + k), where n_eff = (Σw)² / Σw² is the effective film count, and the role's database average mu the
rest; the spread blends their own weighted variance with sigma_pop the same way. The range is middle ± q·σ,
clipped to bounds (the 1-10 score scale by default). The latest film always weighs 1, so nothing divides by zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MIN_RATED = 5
LOW, HIGH = 1.0, 10.0  # TMDB's score scale


@dataclass(frozen=True)
class RoleSettings:
    h: float
    k: float
    q: float


@dataclass(frozen=True)
class Forecast:
    low: float
    mid: float
    high: float
    n_rated: int
    own_avg: float
    own_share: float
    db_avg: float


def track_record(history: list[tuple[int, float]], s: RoleSettings, mu: float, sigma_pop: float,
                 bounds: tuple[float, float] | None = (LOW, HIGH)) -> Forecast | None:
    if len(history) < MIN_RATED:
        return None
    years = np.array([y for y, _ in history], dtype=float)
    scores = np.array([x for _, x in history], dtype=float)
    w = np.ones_like(years) if math.isinf(s.h) else 0.5 ** ((years.max() - years) / s.h)
    m = float(np.sum(w * scores) / np.sum(w))
    n_eff = float(np.clip(np.sum(w) ** 2 / np.sum(w ** 2), 1, len(history)))
    share = n_eff / (n_eff + s.k)
    c = share * m + (1 - share) * mu
    v = float(np.sum(w * (scores - m) ** 2) / np.sum(w))
    sigma = math.sqrt(share * v + (1 - share) * sigma_pop ** 2)

    def clip(x: float) -> float:
        return x if bounds is None else min(max(x, bounds[0]), bounds[1])

    return Forecast(clip(c - s.q * sigma), clip(c), clip(c + s.q * sigma), len(history), m, share, mu)


def rolling_line(points: list[tuple[int, float]], window: int = 5) -> list[tuple[int, float]]:
    half = window // 2
    scores = [x for _, x in points]
    return [(y, sum(part) / len(part)) for i, (y, _) in enumerate(points)
            for part in [scores[max(0, i - half):i + half + 1]]]
