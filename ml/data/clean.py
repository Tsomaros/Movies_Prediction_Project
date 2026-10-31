"""Turn the raw TMDB pull into clean tables for the SQLite build.

    load_raw(path)           -> list of trimmed film records (one per JSONL line)
    select_records(records)  -> released films only, one record per id
    flatten(records)         -> {"movies": DataFrame, "genres": ..., "movie_genres": ..., ...}
    basic_clean(movies)      -> movies with tidy text, parsed dates, NULLed bad values and a split column
    money_rules(movies, cpi, wikidata=None)
                             -> placeholder money NULLed, Wikidata money merged in (V1.5), 2025 dollars,
                                money_source_*, money_suspect and other flags
    score_rules(movies)      -> score_weight and score_ok
    clean(records, cpi, keep_unreleased=False, wikidata=None) -> all of the above: (tables, report)

Each step that changes data also returns a report: {rule: rows affected}.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.data.pull import MOVIES_FILE, RAW_DIR

RAW_MOVIES = RAW_DIR / MOVIES_FILE
CPI_FILE = Path("data/cpi_us_annual.csv")

MOVIE_COLUMNS = [
    "id",
    "title",
    "original_title",
    "original_language",
    "release_date",
    "status",
    "runtime",
    "overview",
    "tagline",
    "budget",
    "revenue",
    "poster_path",
    "popularity",
    "vote_count",
    "vote_average",
    "us_certification",
    "pulled_at",
]
TEXT_COLUMNS = ["title", "original_title", "original_language", "overview", "tagline", "poster_path", "us_certification"]

MAX_RUNTIME = 600  # minutes; longer entries are miniseries or errors
TRAIN_LAST_YEAR, VALIDATION_LAST_YEAR = 2015, 2018  # train <=2015, validation 2016-18, test 2019+
MODEL_DATA_MAX_YEAR = 2025  # the models, their track records and their comparables never see a later film (V1.2: the database now holds 2026 films too)

MIN_MONEY = 1_000  # USD; smaller values are TMDB placeholders such as 7 meaning $7M
CPI_BASE_YEAR = 2025
LOW_RATIO = 0.0001  # revenue / budget below this is token box office (e.g. streaming releases)
CURRENCY_CAP_MULTIPLE = 3  # x the language's 99th-percentile budget in 2025 dollars
CURRENCY_CAP_MIN_BUDGETS = 30  # languages with fewer budgets share one non-English cap
POOLED_LANGUAGE = "other non-English"
WIKIDATA_DISAGREE = 3.0  # TMDB and Wikidata money further apart than this (either way) is suspect (V1.5)
INCOMPLETE_DAYS = 182  # films this young at pull time may still be earning
COVID_YEARS = (2020, 2021)
MIN_VOTES = 50


# ---------------------------------------------------------------- load and flatten


def load_raw(path: Path = RAW_MOVIES) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def select_records(records: list[dict[str, Any]], keep_unreleased: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep released films only; when an id appears twice (a re-pull), keep the latest pull.

    keep_unreleased keeps every status (Planned, In Production, Post Production, ...): only the app's refresher
    of new and upcoming films (backend/app/services/fresh/, V1.2) asks for it; `make db` never does."""
    latest: dict[int, dict[str, Any]] = {}
    for r in records:
        kept = latest.get(r["id"])
        if kept is None or (r.get("pulled_at") or "") >= (kept.get("pulled_at") or ""):
            latest[r["id"]] = r
    released = [r for r in latest.values() if keep_unreleased or r.get("status") == "Released"]
    report = {
        "duplicate_ids_dropped": len(records) - len(latest),
        "not_released_dropped": len(latest) - len(released),
    }
    return released, report


def _entities(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    """One row per id; when TMDB spells an entity differently across films, keep the most common spelling."""
    df = pd.DataFrame(rows, columns=["id", *columns])
    counts = df.groupby(["id", *columns], dropna=False).size().reset_index(name="n")
    counts = counts.sort_values(["id", "n", *columns], ascending=[True, False, *[True] * len(columns)])
    return counts.drop_duplicates("id").drop(columns="n").reset_index(drop=True)


def _links(rows: list[tuple], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns).drop_duplicates().reset_index(drop=True)


def flatten(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    """Split trimmed records into a movies table, lookup tables and movie-to-X link tables."""
    movies = []
    genres, companies, keywords, collections, people = [], [], [], [], []
    movie_genres, movie_companies, movie_keywords = [], [], []
    movie_cast, movie_crew, movie_countries, movie_languages = [], [], [], []

    for r in records:
        mid = r["id"]
        collection = r.get("collection")
        movies.append({**{c: r.get(c) for c in MOVIE_COLUMNS}, "collection_id": collection["id"] if collection else None})
        if collection:
            collections.append(collection)
        for i, g in enumerate(r.get("genres", [])):
            genres.append(g)
            movie_genres.append((mid, g["id"], i))  # TMDB's order; ord 0 is the main genre
        for c in r.get("production_companies", []):
            companies.append(c)
            movie_companies.append((mid, c["id"]))
        for k in r.get("keywords", []):
            keywords.append(k)
            movie_keywords.append((mid, k["id"]))
        for p in r.get("cast", []):
            people.append(p)
            movie_cast.append((mid, p["id"], p.get("character"), p.get("order")))
        for p in r.get("crew", []):
            people.append(p)
            movie_crew.append((mid, p["id"], p["job"]))
        movie_countries += [(mid, iso) for iso in r.get("production_countries", [])]
        movie_languages += [(mid, iso) for iso in r.get("spoken_languages", [])]

    movies_df = pd.DataFrame(movies, columns=[*MOVIE_COLUMNS, "collection_id"])
    movies_df["collection_id"] = movies_df["collection_id"].astype("Int64")
    return {
        "movies": movies_df,
        "genres": _entities(genres, ["name"]),
        "companies": _entities(companies, ["name", "origin_country"]),
        "keywords": _entities(keywords, ["name"]),
        "collections": _entities(collections, ["name"]),
        "people": _entities(people, ["name"]),
        "movie_genres": _links(movie_genres, ["movie_id", "genre_id", "ord"])
        .drop_duplicates(["movie_id", "genre_id"])  # a genre listed twice keeps its first position
        .reset_index(drop=True),
        "movie_companies": _links(movie_companies, ["movie_id", "company_id"]),
        "movie_keywords": _links(movie_keywords, ["movie_id", "keyword_id"]),
        # Cast keeps one row per film and actor: the lowest order (an actor can play two parts).
        "movie_cast": _links(movie_cast, ["movie_id", "person_id", "character", "ord"])
        .sort_values(["movie_id", "ord"])
        .drop_duplicates(["movie_id", "person_id"])
        .reset_index(drop=True),
        "movie_crew": _links(movie_crew, ["movie_id", "person_id", "job"]),
        "movie_countries": _links(movie_countries, ["movie_id", "country"]),
        "movie_languages": _links(movie_languages, ["movie_id", "language"]),
    }


# ---------------------------------------------------------------- basic cleaning


def split_for_year(year: pd.Series) -> pd.Series:
    split = pd.Series(pd.NA, index=year.index, dtype="string")
    split[year <= TRAIN_LAST_YEAR] = "train"
    split[(year > TRAIN_LAST_YEAR) & (year <= VALIDATION_LAST_YEAR)] = "validation"
    split[(year > VALIDATION_LAST_YEAR) & (year <= MODEL_DATA_MAX_YEAR)] = "test"
    split[year > MODEL_DATA_MAX_YEAR] = "later"  # shown in the app, never used by a model
    return split


def basic_clean(movies: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    m = movies.copy()
    report: dict[str, int] = {}

    # Text: trim whitespace; empty strings become NULL; a missing title falls back to the original title.
    for col in TEXT_COLUMNS:
        text = m[col].astype("string").str.strip()
        m[col] = text.mask(text == "")
    no_title = m["title"].isna()
    report["title_from_original_title"] = int((no_title & m["original_title"].notna()).sum())
    m["title"] = m["title"].fillna(m["original_title"])

    # Dates: keep ISO text for SQLite, plus integer year and month.
    dates = pd.to_datetime(m["release_date"], format="%Y-%m-%d", errors="coerce")
    report["release_date_unparseable"] = int((dates.isna() & m["release_date"].notna()).sum())
    m["release_date"] = dates.dt.strftime("%Y-%m-%d").astype("string")
    m["year"] = dates.dt.year.astype("Int64")
    m["month"] = dates.dt.month.astype("Int64")

    # Runtime: 0 means unknown, and anything over 10 hours isn't a feature film.
    runtime = pd.to_numeric(m["runtime"]).astype("Int64")
    bad_runtime = runtime.notna() & ((runtime <= 0) | (runtime > MAX_RUNTIME))
    report["runtime_nulled"] = int(bad_runtime.sum())
    m["runtime"] = runtime.mask(bad_runtime)

    # Score: TMDB reports 0.0 for films nobody has voted on.
    m["vote_count"] = pd.to_numeric(m["vote_count"]).fillna(0).astype("Int64")
    no_votes = m["vote_count"] == 0
    report["score_nulled_no_votes"] = int((no_votes & m["vote_average"].notna()).sum())
    m["vote_average"] = m["vote_average"].astype("Float64").mask(no_votes)

    m["split"] = split_for_year(m["year"])
    report["no_split_missing_year"] = int(m["split"].isna().sum())
    return m, report


# ---------------------------------------------------------------- money rules


def load_cpi(path: Path = CPI_FILE) -> dict[int, float]:
    with path.open(newline="", encoding="utf-8") as f:
        return {int(row["year"]): float(row["cpi"]) for row in csv.DictReader(f)}


def to_base_dollars(amount: pd.Series, year: pd.Series, cpi: dict[int, float]) -> pd.Series:
    """Nominal USD -> CPI_BASE_YEAR dollars, using the release year's annual average CPI."""
    factor = cpi[CPI_BASE_YEAR] / year.map(cpi).astype("Float64")
    return (amount.astype("Float64") * factor).round(0)


def leave_one_out_quantile(values: pd.Series, q: float) -> pd.Series:
    """For each value, the q-quantile of all the *other* values (linear interpolation, as pandas does).

    Removing the value at sorted rank r shifts every later value down one place, so only
    the two values the quantile interpolates between can change.
    """
    n = len(values)
    if n < 2:
        return pd.Series(np.nan, index=values.index)
    order = np.argsort(values.to_numpy(dtype=float), kind="stable")
    s = values.to_numpy(dtype=float)[order]
    rank = np.empty(n, dtype=int)
    rank[order] = np.arange(n)
    pos = (n - 2) * q  # position in the n-1 remaining values
    lo, frac = int(pos), pos - int(pos)
    v_lo = np.where(rank > lo, s[lo], s[lo + 1])
    v_hi = np.where(rank > lo + 1, s[lo + 1], s[min(lo + 2, n - 1)])
    return pd.Series(v_lo + (v_hi - v_lo) * frac, index=values.index)


def currency_caps(movies: pd.DataFrame) -> tuple[pd.Series, dict[str, float]]:
    """Budget cap (2025 dollars) for every non-English film with a budget, plus the caps per language.

    A film is compared with its language's other budgets only, so one budget entered in
    local currency can't raise its own cap. Languages with few budgets share the pooled cap.
    The returned dict gives each language's cap over all its budgets, for the report.

    Only films up to MODEL_DATA_MAX_YEAR make the caps, so adding later films to the database never changes
    whether an earlier film is flagged; a later film is compared with its language's cap over those films.
    """
    foreign = movies[(movies["original_language"] != "en") & movies["budget_2025"].notna()]
    ref = foreign[foreign["year"] <= MODEL_DATA_MAX_YEAR]
    budgets = ref.groupby("original_language")["budget_2025"]
    big = sorted(budgets.size()[lambda n: n >= CURRENCY_CAP_MIN_BUDGETS].index)

    cap = CURRENCY_CAP_MULTIPLE * leave_one_out_quantile(ref["budget_2025"], 0.99)
    for lang in big:
        group = budgets.get_group(lang)
        cap[group.index] = CURRENCY_CAP_MULTIPLE * leave_one_out_quantile(group, 0.99)

    summary = {lang: CURRENCY_CAP_MULTIPLE * float(budgets.get_group(lang).quantile(0.99)) for lang in big}
    if len(ref):  # no non-English budgets at all -> no caps, nothing to flag
        summary[POOLED_LANGUAGE] = CURRENCY_CAP_MULTIPLE * float(ref["budget_2025"].quantile(0.99))
    later = foreign[foreign["year"] > MODEL_DATA_MAX_YEAR]
    if len(later):
        cap = pd.concat([cap, later["original_language"].map(summary).fillna(summary.get(POOLED_LANGUAGE, np.nan))
                         .astype(float)])
    return cap.reindex(movies.index).astype("Float64"), summary


def _suspicion(m: pd.DataFrame, cpi: dict[int, float]) -> tuple[pd.Series, pd.Series, dict[str, float]]:
    """2025 dollars for both columns (in place), then the low-ratio and currency-cap flags and the caps."""
    for col in ("budget", "revenue"):
        m[f"{col}_{CPI_BASE_YEAR}"] = to_base_dollars(m[col], m["year"], cpi)
    low_ratio = (m["revenue"] / m["budget"]) < LOW_RATIO
    film_cap, caps = currency_caps(m)
    over_cap = m["budget_2025"] > film_cap  # film_cap is NULL for English films and films without a budget
    return low_ratio.fillna(False).astype(bool), over_cap.fillna(False).astype(bool), caps


def _merge_wikidata(m: pd.DataFrame, wikidata: pd.DataFrame, bad: dict[str, pd.Series],
                    report: dict[str, Any]) -> pd.Series:
    """Fill missing and replace bad TMDB money with Wikidata's (in place); returns the films where both sources
    have a good value that differ by more than WIKIDATA_DISAGREE. Films after MODEL_DATA_MAX_YEAR or without a
    year are left alone."""
    usable = (m["year"] <= MODEL_DATA_MAX_YEAR).fillna(False).astype(bool)
    frame = wikidata.set_index("id")
    disagree = pd.Series(False, index=m.index)
    confirmed = 0
    for col in ("budget", "revenue"):
        wd = m["id"].map(frame[f"wd_{col}"]).astype("Int64")
        wd = wd.mask(~usable | (wd < MIN_MONEY))  # the placeholder rule holds for Wikidata too
        has = wd.notna()
        filled = has & m[col].isna()
        replaced = has & m[col].notna() & bad[col]
        # Same film, same year, same CPI factor: the nominal ratio is the ratio in 2025 dollars.
        compared = has & m[col].notna() & ~bad[col]
        ratio = m[col].astype("Float64") / wd.astype("Float64")
        differs = compared & ((ratio > WIKIDATA_DISAGREE) | (ratio < 1 / WIKIDATA_DISAGREE)).fillna(False)
        take = filled | replaced
        m[col] = m[col].mask(take, wd)
        m[f"money_source_{col}"] = m[f"money_source_{col}"].mask(take, "wikidata")
        report[f"wikidata_{col}_filled"] = int(filled.sum())
        report[f"wikidata_{col}_replaced"] = int(replaced.sum())
        confirmed += int((compared & ~differs).sum())
        disagree |= differs.astype(bool)
    report["wikidata_confirmed"] = confirmed
    return disagree


def money_rules(movies: pd.DataFrame, cpi: dict[int, float],
                wikidata: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, Any], dict[str, float]]:
    """Placeholder money NULLed, Wikidata merged in (V1.5, when given), then 2025 dollars and the suspect flags on
    the final values. wikidata: select_money's frame (id = TMDB id, nominal USD)."""
    m = movies.copy()
    report: dict[str, Any] = {}

    # Placeholders: 0 means unknown, and 1-999 is almost always shorthand for millions.
    for col in ("budget", "revenue"):
        amount = pd.to_numeric(m[col]).astype("Int64")
        report[f"{col}_zero_or_missing"] = int((amount.isna() | (amount <= 0)).sum())
        report[f"{col}_placeholder_nulled"] = int(((amount > 0) & (amount < MIN_MONEY)).sum())
        m[col] = amount.mask(amount < MIN_MONEY)
        m[f"money_source_{col}"] = pd.Series(pd.NA, index=m.index, dtype="string").mask(m[col].notna(), "tmdb")

    disagree = pd.Series(False, index=m.index)
    if wikidata is not None:
        # TMDB-only suspicion first: a currency budget or a token box office is replaced when Wikidata has one.
        low_ratio, over_cap, _ = _suspicion(m, cpi)
        disagree = _merge_wikidata(m, wikidata, {"budget": over_cap, "revenue": low_ratio}, report)

    # Suspect money stays for display but is kept out of financial training.
    low_ratio, over_cap, caps = _suspicion(m, cpi)
    m["money_suspect"] = low_ratio | over_cap | disagree
    reason = pd.Series(
        np.select([low_ratio & over_cap, low_ratio, over_cap], ["low_ratio,currency", "low_ratio", "currency"], ""),
        index=m.index,
        dtype="string",
    )
    reason = reason.mask(disagree, (reason + ",wikidata_disagree").str.lstrip(","))
    m["money_suspect_reason"] = reason.replace("", pd.NA)
    report["money_suspect_low_ratio"] = int(low_ratio.sum())
    report["money_suspect_currency"] = int(over_cap.sum())
    if wikidata is not None:
        report["money_suspect_wikidata_disagree"] = int(disagree.sum())

    released = pd.to_datetime(m["release_date"])
    pulled = pd.to_datetime(m["pulled_at"], utc=True).dt.tz_localize(None).dt.normalize()
    m["revenue_incomplete"] = (pulled - released).dt.days.lt(INCOMPLETE_DAYS).fillna(False).astype(bool)
    m["covid_period"] = m["year"].isin(COVID_YEARS).fillna(False).astype(bool)
    report["revenue_incomplete"] = int(m["revenue_incomplete"].sum())
    report["covid_period"] = int(m["covid_period"].sum())
    return m, report, caps


# ---------------------------------------------------------------- score rules


def score_rules(movies: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Low-vote scores are noisy: train on films with MIN_VOTES+ votes, weighted by log(1 + votes)."""
    m = movies.copy()
    m["score_weight"] = np.log1p(m["vote_count"].astype("float64"))
    m["score_ok"] = ((m["vote_count"] >= MIN_VOTES) & m["vote_average"].notna()).fillna(False).astype(bool)
    return m, {"score_ok": int(m["score_ok"].sum()), "score_below_min_votes": int((~m["score_ok"]).sum())}


# ---------------------------------------------------------------- pipeline


def clean(records: list[dict[str, Any]], cpi: dict[int, float], keep_unreleased: bool = False,
          wikidata: pd.DataFrame | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Raw trimmed records -> cleaned tables, plus a report of what every rule changed. keep_unreleased: see
    select_records (a film from a year with no CPI row gets NULL 2025-dollar money). wikidata: see money_rules."""
    report: dict[str, Any] = {"raw_records": len(records)}
    records, selected = select_records(records, keep_unreleased)
    tables = flatten(records)
    movies, basic = basic_clean(tables["movies"])
    movies, money, caps = money_rules(movies, cpi, wikidata)
    movies, score = score_rules(movies)
    tables["movies"] = movies
    report.update(selected | basic | money | score)
    report["films"] = len(movies)
    report["currency_caps_2025_usd"] = {lang: round(cap) for lang, cap in caps.items()}
    return tables, report
