"""Wikidata budgets and worldwide box office for our films (V1.5).

A small SPARQL client, statement parsing and a survey of what Wikidata holds.
Films are matched by their TMDB id (property P4947); every budget (P2130) and box office (P2142)
statement is kept with its rank, currency, region (P3005) and point in time (P585).

Public API:
    SPARQL_URL, USER_AGENT, RAW_WIKIDATA, SURVEY_FILE
    WikidataClient(timeout, retries, sleep, transport).query(sparql) -> [{var: value}]
    flatten_bindings(payload) -> [{var: value}]
    year_query(year) -> str
    parse_rows(rows, year=None) -> (statements, report)
    survey(client) -> dict

CLI:
    uv run python -m ml.data.wikidata survey
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from typing import Any, Callable

import httpx

from ml.data.pull import RAW_DIR

SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "MoviePredictionApp/1.5 (https://github.com/Tsomaros)"
RAW_WIKIDATA = RAW_DIR / "wikidata_money.jsonl"
SURVEY_FILE = RAW_DIR / "wikidata_survey.json"

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_DELAY = 120.0
RANKS = {"PreferredRank": "preferred", "NormalRank": "normal"}
DECADES = range(1960, 2030, 10)


class WikidataError(Exception):
    """Raised when a query still fails after all retries."""


def flatten_bindings(payload: dict[str, Any]) -> list[dict[str, str]]:
    """SPARQL JSON bindings -> one {var: value} dict per row."""
    return [{k: v["value"] for k, v in b.items()} for b in payload["results"]["bindings"]]


class WikidataClient:
    def __init__(
        self,
        timeout: float = 90.0,
        retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.retries = retries
        self.sleep = sleep
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        )

    def query(self, sparql: str) -> list[dict[str, str]]:
        """Run a query; retry 429, 5xx and timeouts with exponential backoff (Retry-After wins)."""
        last = "no attempt"
        for attempt in range(self.retries + 1):
            delay = min(2.0**attempt, MAX_RETRY_DELAY)
            try:
                response = self._http.post(SPARQL_URL, data={"query": sparql})
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = repr(e)
            else:
                if response.status_code == 200:
                    return flatten_bindings(response.json())
                last = f"HTTP {response.status_code}"
                if response.status_code not in RETRY_STATUSES:
                    raise WikidataError(last)
                try:
                    delay = min(float(response.headers["Retry-After"]), MAX_RETRY_DELAY)
                except (KeyError, ValueError):
                    pass
            if attempt < self.retries:
                self.sleep(delay)
        raise WikidataError(f"query failed after {self.retries + 1} attempts: {last}")


# ---------------------------------------------------------------- queries


def year_query(year: int) -> str:
    """Every budget and box office statement of films released in `year` that have a TMDB id."""
    return f"""SELECT ?st ?item ?tmdb ?prop ?amount ?iso ?rank ?region ?time WHERE {{
  ?item wdt:P4947 ?tmdb ; wdt:P577 ?date .
  FILTER(YEAR(?date) = {year})
  {{ ?item p:P2142 ?st . ?st psv:P2142 ?v . BIND("box_office" AS ?prop) }}
  UNION
  {{ ?item p:P2130 ?st . ?st psv:P2130 ?v . BIND("budget" AS ?prop) }}
  ?v wikibase:quantityAmount ?amount ; wikibase:quantityUnit ?unit .
  OPTIONAL {{ ?unit wdt:P498 ?iso }}
  ?st wikibase:rank ?rank .
  OPTIONAL {{ ?st pq:P3005 ?region }}
  OPTIONAL {{ ?st pq:P585 ?time }}
}}"""


def _decade_body(decade: int) -> str:
    return f"""  ?item wdt:P4947 ?tmdb ; wdt:P577 ?date .
  FILTER(YEAR(?date) >= {decade} && YEAR(?date) < {decade + 10})
  {{ ?item p:P2142 ?st . ?st psv:P2142 ?v }}
  UNION
  {{ ?item p:P2130 ?st . ?st psv:P2130 ?v }}
  ?v wikibase:quantityUnit ?unit .
  ?st wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)"""


def currency_survey_query(decade: int) -> str:
    """Films with money statements per currency (ISO 4217) in one decade."""
    return f"""SELECT ?iso (COUNT(DISTINCT ?item) AS ?films) WHERE {{
{_decade_body(decade)}
  OPTIONAL {{ ?unit wdt:P498 ?iso }}
}} GROUP BY ?iso"""


def region_survey_query(decade: int) -> str:
    """Statements per region qualifier (P3005) in one decade."""
    return f"""SELECT ?region (COUNT(?st) AS ?n) WHERE {{
{_decade_body(decade)}
  OPTIONAL {{ ?st pq:P3005 ?region }}
}} GROUP BY ?region"""


def films_query(decade: int) -> str:
    return f"""SELECT (COUNT(DISTINCT ?item) AS ?films) WHERE {{
{_decade_body(decade)}
}}"""


# ---------------------------------------------------------------- parsing


def _tail(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _amount(text: str) -> int | None:
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return int(math.floor(value + 0.5))  # half up, not banker's rounding


def parse_rows(
    rows: list[dict[str, str]], year: int | None = None
) -> tuple[list[dict], dict[str, int]]:
    """Flattened bindings -> statement dicts (plus `year`, the query year) and a skip report."""
    report = {"skipped_bad_tmdb_id": 0, "skipped_bad_amount": 0, "skipped_deprecated": 0}
    out: list[dict] = []
    for r in rows:
        rank = RANKS.get(_tail(r.get("rank", "")))
        if rank is None:
            report["skipped_deprecated"] += 1
            continue
        tmdb = r.get("tmdb", "")
        if not re.fullmatch(r"[0-9]+", tmdb):
            report["skipped_bad_tmdb_id"] += 1
            continue
        amount = _amount(r.get("amount", ""))
        if amount is None:
            report["skipped_bad_amount"] += 1
            continue
        out.append(
            {
                "statement": _tail(r["st"]),
                "wikidata_id": _tail(r["item"]),
                "tmdb_id": int(tmdb),
                "prop": r["prop"],
                "amount": amount,
                "currency": r.get("iso") or None,
                "rank": rank,
                "region": _tail(r["region"]) if r.get("region") else None,
                "point_in_time": r["time"][:10] if r.get("time") else None,
                "year": year,
            }
        )
    return out, report


# ---------------------------------------------------------------- survey


def survey(client: WikidataClient) -> dict:
    """What Wikidata holds: films per currency, statements per region, films with any money."""
    currencies: dict[str, int] = {}
    regions: dict[str, int] = {}
    films = 0
    for decade in DECADES:
        for r in client.query(currency_survey_query(decade)):
            iso = r.get("iso") or "unknown"
            currencies[iso] = currencies.get(iso, 0) + int(r["films"])
        for r in client.query(region_survey_query(decade)):
            qid = _tail(r["region"]) if r.get("region") else "none"
            regions[qid] = regions.get(qid, 0) + int(r["n"])
        films += int(client.query(films_query(decade))[0]["films"])
    result = {
        "currencies": dict(sorted(currencies.items(), key=lambda kv: -kv[1])),
        "regions": dict(sorted(regions.items(), key=lambda kv: -kv[1])),
        "films_with_money": films,
    }
    SURVEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SURVEY_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wikidata budgets and box office")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("survey", help="count currencies and regions per decade -> wikidata_survey.json")
    args = parser.parse_args(argv)
    if args.command == "survey":
        print(json.dumps(survey(WikidataClient()), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
