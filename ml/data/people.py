"""TMDB person details for the actor pages (Day 14.6): pull, clean and load into the movie database.

    PERSON_FIELDS                      -> the fields kept from TMDB's /person/{id}
    slim_person(raw, fetched_at)       -> PERSON_FIELDS plus fetched_at (one JSON line in data/raw/tmdb_people.jsonl)
    clean_person(rec, today)           -> a person_details row: blanks -> None, impossible dates -> None
    truncate_bio(text, max_chars)      -> the biography cut at a sentence end within max_chars
    person_ids(con, min_films, crew)   -> cast members with at least min_films films and every crew member
    drop_older_than(path, days, now)   -> rewrites the pull without records older than `days` (they are pulled again)
    summarize(path)                    -> people, with photo / biography / birthday (counts and %)
    load(con, path, today, bio_max_chars)
                                       -> fills person_details (the newest record per id, people we know only)

The pull reuses ml.data.pull.run_details: resumable, one line per person, 404s recorded in
data/raw/missing_people.txt. TMDB's terms want cached data refreshed within six months: --refresh-older-than 180.
tmdb_popularity is for display and ordering only, never a model input; feature code never reads person_details.

    uv run python -m ml.data.people pull [--min-films 2] [--limit N] [--refresh-older-than DAYS]
    uv run python -m ml.data.people load [--db data/movies.db] [--bio-max-chars N]
    uv run python -m ml.data.people summary
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ml.data.pull import RAW_DIR, repair_jsonl, run_details
from ml.data.tmdb_client import TMDBClient

PEOPLE_FILE = RAW_DIR / "tmdb_people.jsonl"
MISSING_FILE = RAW_DIR / "missing_people.txt"
DB_FILE = Path("data/movies.db")
PERSON_FIELDS = ["id", "name", "profile_path", "biography", "birthday", "deathday", "place_of_birth",
                 "known_for_department", "imdb_id", "homepage", "popularity"]
COLUMNS = ["person_id", "profile_path", "biography", "birthday", "deathday", "place_of_birth", "known_for_department",
           "imdb_id", "homepage", "tmdb_popularity", "fetched_at"]
MIN_FILMS = 2  # 118,245 cast members (Oct 2026), plus all 130,723 crew (Day 14.7): 239,459 people; every cast id is 321,259


def slim_person(raw: dict[str, Any], fetched_at: str | None = None) -> dict[str, Any]:
    out = {k: raw.get(k) for k in PERSON_FIELDS}
    out["fetched_at"] = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _date(value: Any, today: date) -> date | None:
    try:
        d = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return d if d is not None and d <= today else None


def clean_person(rec: dict[str, Any], today: date) -> dict[str, Any]:
    born, died = _date(rec.get("birthday"), today), _date(rec.get("deathday"), today)
    if born and died and died < born:  # one of them is wrong and we can't tell which
        born = died = None
    homepage = _text(rec.get("homepage"))
    imdb_id = _text(rec.get("imdb_id"))
    popularity = rec.get("popularity")
    return {
        "person_id": rec["id"], "profile_path": _text(rec.get("profile_path")), "biography": _text(rec.get("biography")),
        "birthday": born.isoformat() if born else None, "deathday": died.isoformat() if died else None,
        "place_of_birth": _text(rec.get("place_of_birth")), "known_for_department": _text(rec.get("known_for_department")),
        "imdb_id": imdb_id if imdb_id and re.fullmatch(r"nm\d+", imdb_id) else None,
        "homepage": homepage if homepage and re.match(r"https?://", homepage, re.I) else None,  # never javascript: and the like
        "tmdb_popularity": float(popularity) if isinstance(popularity, (int, float)) else None,
        "fetched_at": rec.get("fetched_at"),
    }


def truncate_bio(text: str | None, max_chars: int) -> str | None:
    if text is None or len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = cut.rfind(".")
    return cut[:end + 1] if end > 0 else cut[:max_chars - 1].rstrip() + "…"


def person_ids(con: sqlite3.Connection, min_films: int = MIN_FILMS, crew: bool = True) -> list[int]:
    """Cast members with min_films+ films and (Day 14.7) every crew member, most credits first, each once."""
    crew_sql = "UNION ALL SELECT person_id, movie_id, 1 FROM movie_crew" if crew else ""
    rows = con.execute(f"""SELECT person_id FROM (SELECT person_id, movie_id, 0 AS is_crew FROM movie_cast {crew_sql})
                           GROUP BY person_id
                           HAVING MAX(is_crew) = 1 OR COUNT(DISTINCT CASE WHEN is_crew = 0 THEN movie_id END) >= ?
                           ORDER BY COUNT(DISTINCT movie_id) DESC, person_id""", (min_films,))
    return [r[0] for r in rows]


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def drop_older_than(path: Path, days: int, now: datetime) -> int:
    """Keep the newest record per id, minus those fetched more than `days` ago; returns how many were dropped."""
    repair_jsonl(path)
    newest: dict[int, dict[str, Any]] = {}
    for rec in _records(path):
        if rec["id"] not in newest or rec["fetched_at"] > newest[rec["id"]]["fetched_at"]:
            newest[rec["id"]] = rec
    cutoff = now - timedelta(days=days)
    keep = [r for r in newest.values() if datetime.fromisoformat(r["fetched_at"]) >= cutoff]
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in keep)
    os.replace(tmp, path)
    return len(newest) - len(keep)


def summarize(path: Path) -> dict[str, Any]:
    recs = {r["id"]: r for r in _records(path)}.values()
    n = len(recs)
    out: dict[str, Any] = {"people": n}
    for name, field in (("with_photo", "profile_path"), ("with_biography", "biography"), ("with_birthday", "birthday")):
        k = sum(1 for r in recs if _text(r.get(field)))
        out[name], out[f"{name}_pct"] = k, round(100 * k / n, 1) if n else 0.0
    return out


TABLE = """CREATE TABLE IF NOT EXISTS person_details (
    person_id INTEGER PRIMARY KEY REFERENCES people(id), profile_path TEXT, biography TEXT, birthday TEXT,
    deathday TEXT, place_of_birth TEXT, known_for_department TEXT, imdb_id TEXT, homepage TEXT, tmdb_popularity REAL,
    fetched_at TEXT)"""


def load(con: sqlite3.Connection, path: Path = PEOPLE_FILE, today: date | None = None,
         bio_max_chars: int | None = None) -> dict[str, Any]:
    """Replace person_details with the pull's records (rerunnable). Ids missing from `people` are skipped and
    counted. The stats go to meta['people_details']; built_at and the films are never touched."""
    today = today or date.today()
    known = {r[0] for r in con.execute("SELECT id FROM people")}
    newest: dict[int, dict[str, Any]] = {}
    for rec in _records(path):
        if rec["id"] not in newest or rec["fetched_at"] > newest[rec["id"]]["fetched_at"]:
            newest[rec["id"]] = rec
    rows, skipped = [], 0
    for rec in newest.values():
        if rec["id"] not in known:
            skipped += 1
            continue
        row = clean_person(rec, today)
        if bio_max_chars:
            row["biography"] = truncate_bio(row["biography"], bio_max_chars)
        rows.append(tuple(row[c] for c in COLUMNS))
    con.execute(TABLE)
    con.execute("DELETE FROM person_details")
    con.executemany(f"INSERT INTO person_details ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})", rows)
    n = len(rows)
    pct = lambda col: round(100 * con.execute(f"SELECT COUNT(*) FROM person_details WHERE {col} IS NOT NULL")
                            .fetchone()[0] / n, 1) if n else 0.0
    stats = {"people_with_details": n, "pct_photo": pct("profile_path"), "pct_biography": pct("biography"),
             "pct_birthday": pct("birthday"), "skipped_unknown_id": skipped, "bio_max_chars": bio_max_chars}
    con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('people_details', ?)", (json.dumps(stats),))
    con.commit()
    return stats


# ---------------------------------------------------------------- CLI


async def _pull(args: argparse.Namespace) -> None:
    with closing(sqlite3.connect(f"file:{Path(args.db).resolve().as_posix()}?mode=ro", uri=True)) as con:
        ids = person_ids(con, args.min_films)
    out = Path(args.out)
    if args.refresh_older_than is not None and out.exists():
        dropped = drop_older_than(out, args.refresh_older_than, datetime.now(timezone.utc))
        print(f"people: {dropped} records older than {args.refresh_older_than} days will be pulled again")
    print(f"people: {len(ids):,} cast members with {args.min_films}+ films and crew members")
    async with TMDBClient.from_env(rate=args.rate, max_concurrency=args.workers) as client:
        stats = await run_details(client, ids, out, out.with_name(MISSING_FILE.name), limit=args.limit,
                                  workers=args.workers, endpoint="/person/{}", params={"language": "en-US"},
                                  trim=slim_person)
    if stats["failed"]:
        print(f"{stats['failed']} people failed; run again to retry them.", file=sys.stderr)
    print(json.dumps(summarize(out)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="TMDB person details for the actor pages.")
    sub = parser.add_subparsers(dest="command", required=True)
    pull = sub.add_parser("pull", help="fetch /person/{id} for cast members and crew (resumable)")
    pull.add_argument("--db", default=str(DB_FILE))
    pull.add_argument("--out", default=str(PEOPLE_FILE))
    pull.add_argument("--min-films", type=int, default=MIN_FILMS)
    pull.add_argument("--limit", type=int, default=None, help="fetch at most N new people")
    pull.add_argument("--rate", type=float, default=20.0, help="requests per second")
    pull.add_argument("--workers", type=int, default=10, help="requests in flight")
    pull.add_argument("--refresh-older-than", type=int, default=None, metavar="DAYS")
    ld = sub.add_parser("load", help="fill person_details in the movie database from the pull")
    ld.add_argument("--db", default=str(DB_FILE))
    ld.add_argument("--people", default=str(PEOPLE_FILE))
    ld.add_argument("--bio-max-chars", type=int, default=None)
    sm = sub.add_parser("summary", help="coverage of the pull")
    sm.add_argument("--people", default=str(PEOPLE_FILE))
    args = parser.parse_args(argv)
    if args.command == "pull":
        asyncio.run(_pull(args))
    elif args.command == "load":
        with closing(sqlite3.connect(args.db)) as con:
            stats = load(con, Path(args.people), bio_max_chars=args.bio_max_chars)
        print(json.dumps(stats))
        print(f"Database size: {Path(args.db).stat().st_size / 1e6:.0f} MB")
    else:
        print(json.dumps(summarize(Path(args.people))))


if __name__ == "__main__":
    main()
