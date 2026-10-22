"""Creator-friendly groups for the raw features, so users never see names like `actors_revenue_max`.

    GROUPS                 -> group id -> label, in display order
    group_of(name, source) -> the group id of one feature (None for the synopsis numbers)
    feature_groups()       -> feature name -> group id for every grouped feature in feature_list.json

Groups follow the feature sources in feature_list.json, with three exceptions: the track record is
split into the director and the cast by prefix, and each budget track-record column joins the group it
describes (director_budget -> director, actors_budget_* -> cast, company_budget -> studio,
franchise_budget -> franchise). The synopsis numbers have no group: no model uses them (DEFAULT_DROP),
so a model that did would be refused by drivers.group_contributions instead of explained.
"""

from __future__ import annotations

import json
from pathlib import Path

from ml.features.build import FEATURE_LIST_FILE

GROUPS = {
    "budget": "Budget",
    "director": "Director's track record",
    "cast": "Cast's track record",
    "franchise": "Franchise",
    "studio": "Studio",
    "genre": "Genre",
    "themes": "Themes",
    "timing": "Release timing",
    "runtime": "Runtime",
    "certification": "Certification",
    "language": "Language",
    "country": "Country",
}
BY_SOURCE = {
    "budget (2025 dollars)": "budget",
    "franchise (earlier films in the collection)": "franchise",
    "companies": "studio",
    "genres": "genre",
    "themes": "themes",
    "release date": "timing",
    "runtime": "runtime",
    "certification": "certification",
    "language": "language",
    "countries": "country",
}
BY_PREFIX = {"director_": "director", "actors_": "cast", "company_": "studio", "franchise_": "franchise"}
UNGROUPED = "synopsis (MiniLM + PCA)"


def group_of(name: str, source: str) -> str | None:
    if source == UNGROUPED:
        return None
    if source in BY_SOURCE:
        return BY_SOURCE[source]
    for prefix, group in BY_PREFIX.items():  # the two track records
        if name.startswith(prefix):
            return group
    raise ValueError(f"no group for feature {name!r} (source {source!r})")


def feature_groups(path: Path = FEATURE_LIST_FILE) -> dict[str, str]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    out = {e["name"]: group_of(e["name"], e["source"]) for e in entries}
    return {name: group for name, group in out.items() if group is not None}
