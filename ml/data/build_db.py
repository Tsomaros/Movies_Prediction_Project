"""Build data/movies.db from the raw pull: cleaned tables, indexes, full-text search and views.

The database is written to a temp file and swapped in at the end, so a failed
build never replaces a working database.

    uv run python -m ml.data.build_db
    uv run python -m ml.data.build_db --raw data/raw/tmdb_movies.jsonl --out data/movies.db

The person_details table (Day 14.6) is always created; it is filled from data/raw/tmdb_people.jsonl when that
pull exists (ml/data/people.py; `make people-db` refills it in place without a rebuild).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ml.data import people
from ml.data.clean import (
    CPI_BASE_YEAR,
    CPI_FILE,
    MIN_VOTES,
    MODEL_DATA_MAX_YEAR,
    RAW_MOVIES,
    TRAIN_LAST_YEAR,
    VALIDATION_LAST_YEAR,
    clean,
    load_cpi,
    load_raw,
)

DB_FILE = Path("data/movies.db")

SCHEMA = """
CREATE TABLE genres      (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE companies   (id INTEGER PRIMARY KEY, name TEXT, origin_country TEXT);
CREATE TABLE keywords    (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE people      (id INTEGER PRIMARY KEY, name TEXT);

CREATE TABLE movies (
    id                   INTEGER PRIMARY KEY,
    title                TEXT NOT NULL,
    original_title       TEXT,
    original_language    TEXT,
    release_date         TEXT,
    year                 INTEGER,
    month                INTEGER,
    split                TEXT,     -- train <=2015, validation 2016-18, test 2019-2025, later 2026+ (no model uses these)
    status               TEXT,
    runtime              INTEGER,
    overview             TEXT,
    tagline              TEXT,
    us_certification     TEXT,
    collection_id        INTEGER REFERENCES collections(id),
    poster_path          TEXT,
    budget               INTEGER,  -- nominal USD; NULL when unknown or a placeholder
    revenue              INTEGER,
    budget_2025          REAL,
    revenue_2025         REAL,
    money_suspect        INTEGER NOT NULL,  -- shown, but kept out of financial training
    money_suspect_reason TEXT,
    revenue_incomplete   INTEGER NOT NULL,
    covid_period         INTEGER NOT NULL,
    -- Post-release fields: targets and display only, never model features.
    popularity           REAL,
    vote_count           INTEGER,
    vote_average         REAL,
    score_weight         REAL,
    score_ok             INTEGER NOT NULL,
    pulled_at            TEXT
);

CREATE TABLE movie_genres    (movie_id INTEGER REFERENCES movies(id), genre_id INTEGER REFERENCES genres(id),
                              ord INTEGER,  -- TMDB's order; 0 is the main genre
                              PRIMARY KEY (movie_id, genre_id));
CREATE TABLE movie_companies (movie_id INTEGER REFERENCES movies(id), company_id INTEGER REFERENCES companies(id),
                              PRIMARY KEY (movie_id, company_id));
CREATE TABLE movie_keywords  (movie_id INTEGER REFERENCES movies(id), keyword_id INTEGER REFERENCES keywords(id),
                              PRIMARY KEY (movie_id, keyword_id));
CREATE TABLE movie_cast      (movie_id INTEGER REFERENCES movies(id), person_id INTEGER REFERENCES people(id),
                              character TEXT, ord INTEGER, PRIMARY KEY (movie_id, person_id));
CREATE TABLE movie_crew      (movie_id INTEGER REFERENCES movies(id), person_id INTEGER REFERENCES people(id),
                              job TEXT, PRIMARY KEY (movie_id, person_id, job));
CREATE TABLE movie_countries (movie_id INTEGER REFERENCES movies(id), country TEXT, PRIMARY KEY (movie_id, country));
CREATE TABLE movie_languages (movie_id INTEGER REFERENCES movies(id), language TEXT, PRIMARY KEY (movie_id, language));

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);  -- value is JSON
"""

# Lookup tables first, so movies' and the links' foreign keys point at existing rows.
TABLE_ORDER = [
    "genres",
    "companies",
    "keywords",
    "collections",
    "people",
    "movies",
    "movie_genres",
    "movie_companies",
    "movie_keywords",
    "movie_cast",
    "movie_crew",
    "movie_countries",
    "movie_languages",
]

INDEXES = """
CREATE INDEX idx_movies_year       ON movies(year);
CREATE INDEX idx_movies_release    ON movies(release_date);
CREATE INDEX idx_movies_language   ON movies(original_language);
CREATE INDEX idx_movies_votes      ON movies(vote_count);
CREATE INDEX idx_movies_collection ON movies(collection_id);
CREATE INDEX idx_people_name       ON people(name COLLATE NOCASE);
CREATE INDEX idx_movie_genres_genre        ON movie_genres(genre_id);
CREATE INDEX idx_movie_companies_company   ON movie_companies(company_id);
CREATE INDEX idx_movie_keywords_keyword    ON movie_keywords(keyword_id);
CREATE INDEX idx_movie_cast_person         ON movie_cast(person_id);
CREATE INDEX idx_movie_crew_person_job     ON movie_crew(person_id, job);
CREATE INDEX idx_movie_countries_country   ON movie_countries(country);
CREATE INDEX idx_movie_languages_language  ON movie_languages(language);
"""

SEARCH = """
CREATE VIRTUAL TABLE movies_fts USING fts5(
    title, original_title, overview,
    content='movies', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
INSERT INTO movies_fts(movies_fts) VALUES ('rebuild');
"""

VIEWS = f"""
-- Training views keep every split; the test rows stay unused until Day 6. Films after MODEL_DATA_MAX_YEAR (2025)
-- are in the database for the app only, so no view returns them (V1.2).
CREATE VIEW v_train_revenue AS
    SELECT * FROM movies
    WHERE budget IS NOT NULL AND revenue IS NOT NULL AND NOT money_suspect AND NOT revenue_incomplete
      AND year <= {MODEL_DATA_MAX_YEAR};
CREATE VIEW v_train_budget AS
    SELECT * FROM movies WHERE budget IS NOT NULL AND NOT money_suspect AND year <= {MODEL_DATA_MAX_YEAR};
CREATE VIEW v_train_score AS
    SELECT * FROM movies WHERE score_ok AND year <= {MODEL_DATA_MAX_YEAR};

-- Autocomplete: people ranked by how many films they have in the database.
CREATE VIEW v_directors AS
    SELECT p.id AS person_id, p.name, COUNT(DISTINCT c.movie_id) AS n_films
    FROM movie_crew c JOIN people p ON p.id = c.person_id
    WHERE c.job = 'Director'
    GROUP BY p.id ORDER BY n_films DESC, p.name;
CREATE VIEW v_actors AS
    SELECT p.id AS person_id, p.name, COUNT(*) AS n_films
    FROM movie_cast c JOIN people p ON p.id = c.person_id
    GROUP BY p.id ORDER BY n_films DESC, p.name;
"""


def _rows(df: pd.DataFrame, columns: list[str]) -> list[tuple]:
    """DataFrame -> plain Python tuples for sqlite3 (pandas NA -> None, booleans -> 0/1)."""
    out = df[columns].astype(object)
    out = out.where(out.notna(), None)
    return [tuple(int(v) if isinstance(v, bool) else v for v in row) for row in out.itertuples(index=False)]


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({table})")]


def write_db(con: sqlite3.Connection, tables: dict[str, pd.DataFrame], meta: dict[str, Any]) -> None:
    con.executescript(SCHEMA)
    con.execute(people.TABLE)  # empty until people.load: every database has it, so the API never meets a missing table
    for name in TABLE_ORDER:
        columns = _columns(con, name)
        placeholders = ", ".join("?" * len(columns))
        con.executemany(f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({placeholders})", _rows(tables[name], columns))
    con.executescript(INDEXES + SEARCH + VIEWS)
    # Every value is stored as JSON, so readers decode them all the same way.
    con.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [(k, json.dumps(v)) for k, v in meta.items()])
    broken = con.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        raise RuntimeError(f"{len(broken)} rows point at missing ids, e.g. {broken[:3]}")
    con.commit()


def build(raw_path: Path = RAW_MOVIES, cpi_path: Path = CPI_FILE, db_path: Path = DB_FILE,
          people_path: Path | None = None) -> dict[str, Any]:
    """Clean the raw pull and write it to db_path via a temp file; returns the cleaning report. With people_path,
    person_details is filled from that person pull."""
    tables, report = clean(load_raw(raw_path), load_cpi(cpi_path))
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_file": raw_path.as_posix(),
        "cpi_file": cpi_path.as_posix(),
        "cpi_base_year": CPI_BASE_YEAR,
        "vote_threshold": MIN_VOTES,
        "splits": {"train": f"<={TRAIN_LAST_YEAR}", "validation": f"{TRAIN_LAST_YEAR + 1}-{VALIDATION_LAST_YEAR}",
                   "test": f"{VALIDATION_LAST_YEAR + 1}-{MODEL_DATA_MAX_YEAR}", "later": f">{MODEL_DATA_MAX_YEAR}"},
        "cleaning_report": report,
    }

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    tmp_path.unlink(missing_ok=True)
    con = sqlite3.connect(tmp_path)
    try:
        con.execute("PRAGMA journal_mode = OFF")  # a fresh file: if the build fails we just delete it
        con.execute("PRAGMA synchronous = OFF")
        write_db(con, tables, meta)
        if people_path is not None:
            report["people_details"] = people.load(con, people_path)
    except BaseException:
        con.close()
        tmp_path.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(tmp_path, db_path)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the SQLite database from the raw TMDB pull.")
    parser.add_argument("--raw", default=str(RAW_MOVIES))
    parser.add_argument("--cpi", default=str(CPI_FILE))
    parser.add_argument("--out", default=str(DB_FILE))
    parser.add_argument("--people", default=str(people.PEOPLE_FILE), help="the person pull, loaded when it exists")
    args = parser.parse_args(argv)

    start = time.monotonic()
    people_path = Path(args.people) if Path(args.people).exists() else None
    report = build(Path(args.raw), Path(args.cpi), Path(args.out), people_path)
    caps = report.pop("currency_caps_2025_usd")
    details = report.pop("people_details", None)
    print(f"built {args.out} in {time.monotonic() - start:.0f}s")
    for rule, n in report.items():
        print(f"  {rule:28} {n:>8,}")
    if caps:
        print(f"  currency caps (2025 USD): {len(caps)} groups, ${min(caps.values()) / 1e6:.0f}M-${max(caps.values()) / 1e6:.0f}M")
    if details:
        print(f"  person details: {json.dumps(details)}")
    print(f"Database size: {Path(args.out).stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
