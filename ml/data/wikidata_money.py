"""One nominal-USD budget and one worldwide box office per TMDB film from Wikidata statements.

Public API:
    WORLDWIDE, BUDGET_AMBIGUOUS
    load_statements(path) -> statement dicts (marker lines skipped)
    select_money(statements, fx) -> (DataFrame[id, wd_budget, wd_revenue, year], report counts)

Rules per film and property: amounts <= 0 are dropped; box office keeps the worldwide region
(or the untagged statement when it is the film's only box office statement); preferred rank
beats normal; amounts are converted to nominal USD in the film's year; box office takes the
latest point in time; budget is dropped when its values differ by more than BUDGET_AMBIGUOUS,
else the latest is taken.

There is no CLI; ``ml.data.clean`` (V1.5) uses ``select_money``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from ml.data.fx import to_usd
from ml.data.wikidata import RAW_WIKIDATA

WORLDWIDE = "Q13780930"
BUDGET_AMBIGUOUS = 2.0

REPORT_KEYS = (
    "wikidata_region_dropped",
    "wikidata_currency_dropped",
    "wikidata_fx_missing",
    "wikidata_budget_ambiguous",
    "wikidata_nonpositive_dropped",
)


def load_statements(path: Path = RAW_WIKIDATA) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if not r.get("empty") and "statement" in r]


def _preferred(rows: list[dict]) -> list[dict]:
    pref = [r for r in rows if r["rank"] == "preferred"]
    return pref or rows


def _convert(rows: list[dict], fx: dict, known: set[str], report: dict[str, int]) -> list[tuple[dict, float]]:
    out = []
    for r in rows:
        cur = r["currency"]
        if cur is None or (cur != "USD" and cur not in known):
            report["wikidata_currency_dropped"] += 1
            continue
        usd = to_usd(r["amount"], cur, r["year"], fx)
        if usd is None:
            report["wikidata_fx_missing"] += 1
            continue
        out.append((r, usd))
    return out


def _latest(pairs: list[tuple[dict, float]]) -> float:
    return max(pairs, key=lambda p: (p[0]["point_in_time"] or "", p[1]))[1]


def select_money(statements: list[dict], fx: dict) -> tuple[pd.DataFrame, dict[str, int]]:
    report = dict.fromkeys(REPORT_KEYS, 0)
    known = {c for c, _ in fx}
    by_film: dict[int, dict[str, list[dict]]] = defaultdict(lambda: {"box_office": [], "budget": []})
    years: dict[int, int] = {}
    for s in statements:
        tid = s["tmdb_id"]
        years[tid] = min(years.get(tid, s["year"]), s["year"])
        if s["amount"] <= 0:
            report["wikidata_nonpositive_dropped"] += 1
            continue
        by_film[tid][s["prop"]].append(s)

    rows = []
    for tid, props in by_film.items():
        revenue = budget = None

        box = props["box_office"]
        single = len(box) == 1
        kept = []
        for r in box:
            if r["region"] == WORLDWIDE or (r["region"] is None and single):
                kept.append(r)
            else:
                report["wikidata_region_dropped"] += 1
        pairs = _convert(_preferred(kept), fx, known, report)
        if pairs:
            revenue = _latest(pairs)

        pairs = _convert(_preferred(props["budget"]), fx, known, report)
        if pairs:
            values = [v for _, v in pairs]
            if max(values) / min(values) > BUDGET_AMBIGUOUS:
                report["wikidata_budget_ambiguous"] += 1
            else:
                budget = _latest(pairs)

        if revenue is not None or budget is not None:
            rows.append({"id": tid, "wd_budget": budget, "wd_revenue": revenue, "year": years[tid]})

    df = pd.DataFrame(rows, columns=["id", "wd_budget", "wd_revenue", "year"])
    for col in ("wd_budget", "wd_revenue"):
        df[col] = pd.to_numeric(df[col]).round().astype("Int64")
    df["id"] = df["id"].astype("int64")
    df["year"] = df["year"].astype("int64")
    return df, report
