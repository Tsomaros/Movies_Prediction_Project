"""Non-people features: genres, themes, language, country, company, certification, runtime, franchise, dates, budget.

    fit_vocab(con)                    -> top languages, countries and companies in train films (saved to vocab.json)
    load_vocab(path)                  -> the committed vocab
    Franchises.from_db(con)           -> each collection's dated films, for leak-safe franchise features
    franchises.budget(cid, as_of)     -> franchise_budget, the median earlier log budget in the collection
    basic_features(form, as_of, ...)  -> one dict of feature columns for a contract-shaped form

Lists are fitted on train films (<=2015) only. A film counts as a franchise film only when its
collection already had an earlier film (a sequel or later entry): a first entry belongs to a
collection only because sequels came later, which would leak future success into training.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from ml.data.clean import COVID_YEARS
from ml.features.contract import CERTIFICATIONS, GENRES, UNRATED
from ml.features.history import LOG_BUDGET_SQL, MATURE_DAYS, Groups

VOCAB_FILE = Path("ml/features/vocab.json")
N_LANGUAGES, N_COUNTRIES, N_COMPANIES = 15, 15, 30
MAJOR_STUDIOS = {  # TMDB company id -> name: the classic Hollywood majors (and Fox's current name)
    33: "Universal Pictures",
    174: "Warner Bros. Pictures",
    4: "Paramount Pictures",
    5: "Columbia Pictures",
    25: "20th Century Fox",
    127928: "20th Century Studios",
    2: "Walt Disney Pictures",
    21: "Metro-Goldwyn-Mayer",
    60: "United Artists",
}
SUMMER_MONTHS = (5, 6, 7, 8)
HOLIDAY_MONTHS = (11, 12)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")


# ---------------------------------------------------------------- vocab (fitted on train)


def fit_vocab(con: sqlite3.Connection) -> dict[str, Any]:
    languages = con.execute(
        "SELECT original_language FROM movies WHERE split = 'train' AND original_language IS NOT NULL "
        "GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT ?", (N_LANGUAGES,)).fetchall()
    countries = con.execute(
        "SELECT country FROM movie_countries mc JOIN movies m ON m.id = mc.movie_id WHERE m.split = 'train' "
        "GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT ?", (N_COUNTRIES,)).fetchall()
    companies = con.execute(
        "SELECT co.id, co.name FROM movie_companies mc JOIN companies co ON co.id = mc.company_id "
        "JOIN movies m ON m.id = mc.movie_id WHERE m.split = 'train' "
        "GROUP BY co.id ORDER BY COUNT(*) DESC, co.id LIMIT ?", (N_COMPANIES,)).fetchall()
    return {
        "about": "Fitted on train films (<=2015): the most common original languages, production countries "
                 "and production companies. Anything else counts as 'other'.",
        "languages": [r[0] for r in languages],
        "countries": [r[0] for r in countries],
        "companies": [{"id": int(i), "name": n} for i, n in companies],
        "major_studios": [{"id": i, "name": n} for i, n in MAJOR_STUDIOS.items()],
    }


def save_vocab(vocab: dict[str, Any], path: Path = VOCAB_FILE) -> None:
    path.write_text(json.dumps(vocab, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_vocab(path: Path = VOCAB_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _company_ids(refs: Iterable[dict[str, Any]], vocab: dict[str, Any]) -> list[int | None]:
    """Company refs -> TMDB ids where we can tell (by id, or by name for the listed companies), else None."""
    by_name = {c["name"].casefold(): c["id"] for c in vocab["companies"] + vocab["major_studios"]}
    out = []
    for ref in refs:
        if ref.get("id") is not None:
            out.append(int(ref["id"]))
        else:
            out.append(by_name.get((ref.get("name") or "").strip().casefold()))
    return out


# ---------------------------------------------------------------- franchises


class Franchises:
    def __init__(self, films: pd.DataFrame, collections: pd.DataFrame) -> None:
        """films: collection_id, release_date, log_revenue, log_budget (NaN if unusable). collections: id, name."""
        films = films[films["collection_id"].notna()].copy()
        films["day"] = pd.to_datetime(films["release_date"]).values.astype("datetime64[D]").astype(np.int64)
        films = films.sort_values(["collection_id", "day"], kind="stable")
        rev, bud = films[films["log_revenue"].notna()], films[films["log_budget"].notna()]
        # Each collection's films, and those with a usable revenue / budget, packed by collection (see Groups)
        self.films, self.days = Groups.of(films["collection_id"].to_numpy()), films["day"].to_numpy(np.int64)
        self.revenue_films = Groups.of(rev["collection_id"].to_numpy())
        self.revenue_days, self.revenue = rev["day"].to_numpy(np.int64), rev["log_revenue"].to_numpy(float)
        self.budget_films = Groups.of(bud["collection_id"].to_numpy())
        self.budget_days, self.budget_values = bud["day"].to_numpy(np.int64), bud["log_budget"].to_numpy(float)
        named = collections.assign(key=collections["name"].str.casefold()).sort_values(["key", "id"])
        named = named[named["id"].isin(self.films.ids)]
        self.by_name = {r.key: int(r.id) for r in named.drop_duplicates("key").itertuples()}

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> Franchises:
        films = pd.read_sql_query(
            f"""
            SELECT collection_id, release_date,
                   CASE WHEN budget IS NOT NULL AND revenue IS NOT NULL AND NOT money_suspect
                             AND NOT revenue_incomplete THEN LN(revenue_2025) END AS log_revenue,
                   {LOG_BUDGET_SQL} AS log_budget
            FROM movies WHERE collection_id IS NOT NULL AND release_date IS NOT NULL
            """,  # same revenue rule as v_train_revenue, budget rule as v_train_budget
            con,
        )
        return cls(films, pd.read_sql_query("SELECT id, name FROM collections", con))

    def resolve(self, ref: dict[str, Any] | None) -> int | None:
        """A known collection id, else a case-insensitive name match, else None (a new franchise)."""
        if not ref:
            return None
        if ref.get("id") is not None and int(ref["id"]) in self.films:
            return int(ref["id"])
        return self.by_name.get((ref.get("name") or "").strip().casefold())

    def features(self, collection_id: int | None, as_of: int) -> dict[str, float]:
        span = self.films.span(collection_id)
        earlier = int(np.searchsorted(self.days[span[0]:span[1]], as_of, "left")) if span else 0
        revenue = np.array([])
        rev_span = self.revenue_films.span(collection_id) if earlier else None
        if rev_span:
            s, e = rev_span
            revenue = self.revenue[s:s + int(np.searchsorted(self.revenue_days[s:e], as_of - MATURE_DAYS, "right"))]
        return {
            "is_franchise": int(earlier > 0),
            "franchise_earlier_films": earlier,
            "franchise_revenue": float(np.median(revenue)) if len(revenue) else float("nan"),
        }

    def budget(self, collection_id: int | None, as_of: int) -> dict[str, float]:
        """Median log budget of the collection's films released strictly earlier (NaN for none, like franchise_revenue)."""
        span = self.budget_films.span(collection_id)
        n = int(np.searchsorted(self.budget_days[span[0]:span[1]], as_of, "left")) if span else 0
        return {"franchise_budget": float(np.median(self.budget_values[span[0]:span[0] + n])) if n else float("nan")}


# ---------------------------------------------------------------- features


def basic_features(
    form: dict[str, Any], as_of: int, vocab: dict[str, Any], franchises: Franchises, theme_names: Iterable[str]
) -> dict[str, float]:
    """Feature columns for one contract-shaped form (see contract.validate); missing values become NaN or 'unknown'."""
    f: dict[str, float] = {}
    genres = set(form.get("genres") or [])
    f.update({f"genre_{slug(g)}": int(g in genres) for g in GENRES})
    themes = set(form.get("themes") or [])
    f.update({f"theme_{slug(t)}": int(t in themes) for t in theme_names})

    language = form.get("language")
    f.update({f"language_{code}": int(language == code) for code in vocab["languages"]})
    f["language_other"] = int(language is not None and language not in vocab["languages"])

    countries = set(form.get("countries") or [])
    f.update({f"country_{code}": int(code in countries) for code in vocab["countries"]})
    f["country_other"] = int(bool(countries - set(vocab["countries"])))
    f["country_unknown"] = int(not countries)

    company_refs = form.get("companies") or []
    ids = _company_ids(company_refs, vocab)
    listed = {c["id"] for c in vocab["companies"]}
    f.update({f"company_{slug(c['name'])}": int(c["id"] in ids) for c in vocab["companies"]})
    f["company_other"] = int(any(i not in listed for i in ids))
    f["company_unknown"] = int(not company_refs)
    f["major_studio"] = int(any(i in MAJOR_STUDIOS for i in ids))

    certification = form.get("certification") or UNRATED
    f.update({f"cert_{slug(c)}": int(certification == c) for c in CERTIFICATIONS})

    runtime = form.get("runtime")
    f["runtime"] = float(runtime) if runtime is not None else float("nan")

    f.update(franchises.features(franchises.resolve(form.get("franchise")), as_of))

    year, month = form["release_year"], form["release_month"]
    f.update({
        "year": year,
        "month": month,
        "summer": int(month in SUMMER_MONTHS),
        "holiday": int(month in HOLIDAY_MONTHS),
        "covid_period": int(year in COVID_YEARS),
    })

    budget = form.get("budget")
    f["log_budget"] = math.log(budget) if budget else float("nan")
    return f


def main() -> None:
    from ml.data.build_db import DB_FILE

    with sqlite3.connect(DB_FILE) as con:
        vocab = fit_vocab(con)
    save_vocab(vocab)
    print(f"Wrote {VOCAB_FILE}: {len(vocab['languages'])} languages, {len(vocab['countries'])} countries, "
          f"{len(vocab['companies'])} companies, {len(vocab['major_studios'])} major studios")


if __name__ == "__main__":
    main()
