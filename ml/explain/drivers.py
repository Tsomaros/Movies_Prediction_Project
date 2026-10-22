"""What pushed a prediction up or down: LightGBM's own feature contributions, grouped and labelled.

    contributions(model, df)                  -> one column per model feature plus EXPECTED, in the target's units
    group_contributions(contribs, groups)     -> the same summed per group (every feature must have a group)
    effect(target, c)                         -> the size people see: a % change for money, points for score
    strength(target, c)                       -> "strong" / "moderate" / "slight"
    top_drivers(target, row, n, estimated)    -> the n largest groups with direction, strength and effect
    main_feature(contribs_row, group, groups) -> the feature contributing most inside one group (for the wording)

Only the middle (p50) model is explained: revenue's monotone Huber model, the budget and score
quantile-0.5 models. `pred_contrib=True` splits each prediction into one amount per feature plus the
model's expected value (the "typical film"), and these add up exactly to the middle prediction. The
one exception is crossed budget / score quantiles (see contributions). The range correction q moves
only p10 / p90, never the middle.

Money models work in log 2025 $, so a contribution c means "times e^c": the effect is e^c - 1 and the
strength cut-offs are the same size up or down on the log scale (+50% and -33% are both "strong").
The cut-offs were set in notebooks/07_explanations.ipynb: with +25% / +10% (the plan's starting point)
72% of revenue's top-5 drivers on 2016-18 read "strong"; with +50% / +20% it is 30%.
Score contributions are already in points.
"""

from __future__ import annotations

import math
from typing import Any, Collection, Mapping

import numpy as np
import pandas as pd

from ml.models.train import LgbmQuantile

EXPECTED = "expected"  # the model's average prediction, what the contributions start from
STRONG, MODERATE = "strong", "moderate"
SLIGHT = "slight"
CUTOFFS = {  # target -> (strong at or above, moderate at or above), in the target's units
    "revenue": (math.log(1.5), math.log(1.2)),
    "budget": (math.log(1.5), math.log(1.2)),
    "score": (0.3, 0.1),
}
TOP_N = 5


def contributions(model: LgbmQuantile, df: pd.DataFrame) -> pd.DataFrame:
    """Each feature's contribution to the middle prediction; the row sums equal model.predict(df)["p50"].

    When the budget or score quantile models cross, predict() sorts them and the middle shown is not
    the p50 model's own value (about 3% of 2016-18 budget films, under 0.2% for score; up to 0.3 log).
    Those rows are scaled so the features still add up to the middle that is shown."""
    raw = model.models["p50"].predict(df[model.features], pred_contrib=True)
    out = pd.DataFrame(raw, index=df.index, columns=[*model.features, EXPECTED])
    if model.target != "revenue":
        shown = model.predict(df, q=0.0)["p50"].to_numpy()
        own = raw[:, :-1].sum(axis=1)
        wanted = shown - raw[:, -1]
        scale = np.divide(wanted, own, out=np.ones_like(own), where=np.abs(own) > 1e-12)
        out[model.features] = raw[:, :-1] * scale[:, None]
    return out


def group_contributions(contribs: pd.DataFrame, groups: Mapping[str, str]) -> pd.DataFrame:
    """Sum feature contributions per group, groups in order of first appearance; EXPECTED is kept.

    A feature without a group raises KeyError, so a raw feature name can never reach the user."""
    features = [c for c in contribs.columns if c != EXPECTED]
    missing = [f for f in features if f not in groups]
    if missing:
        raise KeyError(f"features without a group: {missing}")
    grouped = contribs[features].T.groupby([groups[f] for f in features], sort=False).sum().T
    grouped[EXPECTED] = contribs[EXPECTED]
    return grouped


def effect(target: str, c: float) -> float:
    """Money: the % change the contribution makes (0.25 = +25%); score: points."""
    return c if target == "score" else math.expm1(c)


def strength(target: str, c: float) -> str:
    strong, moderate = CUTOFFS[target]
    size = abs(c)
    return STRONG if size >= strong else MODERATE if size >= moderate else SLIGHT


def top_drivers(target: str, row: pd.Series, n: int = TOP_N,
                estimated: Collection[str] = ()) -> list[dict[str, Any]]:
    """The n groups with the largest contributions (one row of group_contributions), largest first.

    Groups contributing exactly zero are left out. `estimated` names groups whose value was not given
    by the creator (revenue's budget in "budget estimated" mode); they are flagged so the wording can
    say so."""
    values = row.drop(EXPECTED, errors="ignore").astype(float)
    values = values[values != 0]
    order = np.argsort(-values.abs().to_numpy(), kind="stable")[:n]
    return [{
        "group": group,
        "direction": "up" if c > 0 else "down",
        "strength": strength(target, c),
        "contribution": float(c),
        "effect": effect(target, c),
        "estimated": group in estimated,
    } for group, c in values.iloc[order].items()]


def main_feature(contribs_row: pd.Series, group: str, groups: Mapping[str, str]) -> str | None:
    """The feature with the largest contribution inside `group`, so a sentence can name what matters
    (release timing: the year or the month). Internal only: the name never reaches the text."""
    members = [f for f in contribs_row.index if groups.get(f) == group]
    if not members:
        return None
    return str(contribs_row[members].abs().astype(float).idxmax())
