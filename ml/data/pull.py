"""Pull films from TMDB into data/raw/.

Phase A (discover): the most-voted films per release year -> data/raw/discover_ids.csv
Phase B (details):  one details request per film       -> data/raw/tmdb_movies.jsonl

Both phases resume: discover skips finished years, details skips films already
saved (and 404s already recorded in data/raw/missing_ids.txt).

    uv run python -m ml.data.pull                    # full pull, 1960-2025
    uv run python -m ml.data.pull --limit 20         # smoke test: first 20 films
    uv run python -m ml.data.pull --years 2019-2019 --phase discover
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.data.tmdb_client import TMDBClient, TMDBError

RAW_DIR = Path("data/raw")
IDS_FILE = "discover_ids.csv"
MOVIES_FILE = "tmdb_movies.jsonl"
MISSING_FILE = "missing_ids.txt"

FIRST_YEAR, LAST_YEAR = 1960, 2025
PAGES_PER_YEAR = 60  # 20 films per page -> 1,200 most-voted films per year
TOP_CAST = 15
KEY_CREW_JOBS = {
    "Director",
    "Screenplay",
    "Writer",
    "Producer",
    "Original Music Composer",
    "Director of Photography",
    "Editor",
}
THEATRICAL_RELEASE = 3  # TMDB release_dates type


# ---------------------------------------------------------------- trimming


def us_certification(release_dates: dict[str, Any] | None) -> str | None:
    """US certification, preferring the theatrical release's."""
    for country in (release_dates or {}).get("results", []):
        if country.get("iso_3166_1") != "US":
            continue
        dates = [d for d in country.get("release_dates", []) if d.get("certification")]
        theatrical = [d for d in dates if d.get("type") == THEATRICAL_RELEASE]
        chosen = theatrical or dates
        return chosen[0]["certification"].strip() if chosen else None
    return None


def trim_movie(raw: dict[str, Any], pulled_at: str | None = None) -> dict[str, Any]:
    """Keep only the fields we use from a /movie/{id} response with credits, keywords and release_dates."""
    credits = raw.get("credits") or {}
    collection = raw.get("belongs_to_collection")
    cast = sorted(credits.get("cast", []), key=lambda c: c.get("order", 10_000))[:TOP_CAST]

    return {
        "id": raw["id"],
        "title": raw.get("title"),
        "original_title": raw.get("original_title"),
        "original_language": raw.get("original_language"),
        "release_date": raw.get("release_date"),
        "status": raw.get("status"),
        "runtime": raw.get("runtime"),
        "genres": [{"id": g["id"], "name": g["name"]} for g in raw.get("genres", [])],
        "overview": raw.get("overview"),
        "tagline": raw.get("tagline"),
        "budget": raw.get("budget"),
        "revenue": raw.get("revenue"),
        "poster_path": raw.get("poster_path"),
        # Post-release fields: targets and display only, never model features.
        "popularity": raw.get("popularity"),
        "vote_count": raw.get("vote_count"),
        "vote_average": raw.get("vote_average"),
        "collection": {"id": collection["id"], "name": collection.get("name")} if collection else None,
        "production_companies": [
            {"id": c["id"], "name": c.get("name"), "origin_country": c.get("origin_country")}
            for c in raw.get("production_companies", [])
        ],
        "production_countries": [c["iso_3166_1"] for c in raw.get("production_countries", [])],
        "spoken_languages": [lang["iso_639_1"] for lang in raw.get("spoken_languages", [])],
        "keywords": [{"id": k["id"], "name": k["name"]} for k in (raw.get("keywords") or {}).get("keywords", [])],
        "us_certification": us_certification(raw.get("release_dates")),
        "cast": [
            {"id": c["id"], "name": c.get("name"), "character": c.get("character"), "order": c.get("order")}
            for c in cast
        ],
        "crew": [
            {"id": c["id"], "name": c.get("name"), "job": c["job"]}
            for c in credits.get("crew", [])
            if c.get("job") in KEY_CREW_JOBS
        ],
        "pulled_at": pulled_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------- phase A: discover


def discover_params(year: int, page: int) -> dict[str, Any]:
    return {
        "primary_release_year": year,
        "sort_by": "vote_count.desc",
        "include_adult": "false",
        "include_video": "false",
        "page": page,
    }


def finished_years(ids_path: Path) -> set[int]:
    if not ids_path.exists():
        return set()
    with ids_path.open(newline="", encoding="utf-8") as f:
        return {int(row["year"]) for row in csv.DictReader(f)}


async def discover_year(client: TMDBClient, year: int, pages: int) -> list[tuple[int, int, int]]:
    """(year, page, id) rows for the most-voted films released in `year`."""
    first = await client.get("/discover/movie", discover_params(year, 1))
    if first is None:
        return []
    last_page = min(pages, first.get("total_pages", 1))
    rest = await asyncio.gather(
        *(client.get("/discover/movie", discover_params(year, p)) for p in range(2, last_page + 1))
    )

    rows, seen = [], set()
    for page_no, body in enumerate([first, *rest], start=1):
        for movie in (body or {}).get("results", []):
            if movie["id"] not in seen:
                seen.add(movie["id"])
                rows.append((year, page_no, movie["id"]))
    return rows


async def run_discover(client: TMDBClient, years: range, pages: int, ids_path: Path) -> int:
    """Discover every unfinished year; a year is written only once all its pages are in."""
    done = finished_years(ids_path)
    todo = [y for y in years if y not in done]
    print(f"discover: {len(done & set(years))} years already done, {len(todo)} to go")

    ids_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not ids_path.exists()
    added = 0
    with ids_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["year", "page", "id"])
        for year in todo:
            rows = await discover_year(client, year, pages)
            writer.writerows(rows)
            f.flush()
            added += len(rows)
            print(f"discover: {year} -> {len(rows)} films")
    return added


# ---------------------------------------------------------------- phase B: details


def load_discover_ids(ids_path: Path, years: range) -> list[int]:
    """Unique film ids from the discover file, in file order, for the given years."""
    ids, seen = [], set()
    with ids_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            movie_id = int(row["id"])
            if int(row["year"]) in years and movie_id not in seen:
                seen.add(movie_id)
                ids.append(movie_id)
    return ids


def repair_jsonl(path: Path) -> None:
    """Drop a half-written last line left by an interrupted run."""
    if not path.exists():
        return
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        path.write_bytes(data[: data.rfind(b"\n") + 1])


def saved_ids(movies_path: Path, missing_path: Path) -> set[int]:
    ids: set[int] = set()
    if movies_path.exists():
        with movies_path.open(encoding="utf-8") as f:
            for line in f:
                ids.add(json.loads(line)["id"])
    if missing_path.exists():
        ids.update(int(line) for line in missing_path.read_text(encoding="utf-8").split())
    return ids


DETAILS_PARAMS = {"append_to_response": "credits,keywords,release_dates"}


async def run_details(
    client: TMDBClient,
    ids: list[int],
    movies_path: Path,
    missing_path: Path,
    *,
    limit: int | None = None,
    workers: int = 10,
    progress_every: float = 15.0,
) -> dict[str, int]:
    """Fetch details for every id not yet saved, appending one JSON line per film."""
    repair_jsonl(movies_path)
    done = saved_ids(movies_path, missing_path)
    todo = [i for i in ids if i not in done]
    print(f"details: {len(ids) - len(todo)} already saved, {len(todo)} to go", end="")
    if limit is not None:
        todo = todo[:limit]
        print(f" (limited to {len(todo)})", end="")
    print()

    stats = {"saved": 0, "missing": 0, "failed": 0}
    if not todo:
        return stats

    queue: asyncio.Queue[int] = asyncio.Queue()
    for movie_id in todo:
        queue.put_nowait(movie_id)

    movies_path.parent.mkdir(parents=True, exist_ok=True)
    started = last_report = time.monotonic()

    with movies_path.open("a", encoding="utf-8") as movies_out, missing_path.open("a", encoding="utf-8") as missing_out:

        def report() -> None:
            finished = stats["saved"] + stats["missing"] + stats["failed"]
            elapsed = time.monotonic() - started
            rate = finished / elapsed if elapsed else 0.0
            eta = (len(todo) - finished) / rate if rate else 0.0
            print(
                f"details: {finished}/{len(todo)} ({rate:.1f}/s, ~{eta / 60:.1f} min left) "
                f"saved={stats['saved']} missing={stats['missing']} failed={stats['failed']}",
                flush=True,
            )

        async def worker() -> None:
            nonlocal last_report
            while True:
                try:
                    movie_id = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    raw = await client.get(f"/movie/{movie_id}", DETAILS_PARAMS)
                except TMDBError as exc:
                    stats["failed"] += 1  # left unsaved, so the next run retries it
                    print(f"details: {movie_id} failed: {exc}", file=sys.stderr)
                    continue
                # Writes happen between awaits, so lines from different workers never interleave.
                if raw is None:
                    missing_out.write(f"{movie_id}\n")
                    missing_out.flush()
                    stats["missing"] += 1
                else:
                    movies_out.write(json.dumps(trim_movie(raw), ensure_ascii=False) + "\n")
                    movies_out.flush()
                    stats["saved"] += 1
                if time.monotonic() - last_report >= progress_every:
                    last_report = time.monotonic()
                    report()

        await asyncio.gather(*(worker() for _ in range(workers)))
        report()
    return stats


# ---------------------------------------------------------------- CLI


def parse_years(text: str) -> range:
    first, _, last = text.partition("-")
    return range(int(first), int(last or first) + 1)


async def run(args: argparse.Namespace) -> None:
    raw_dir = Path(args.out_dir)
    years = parse_years(args.years)
    async with TMDBClient.from_env(rate=args.rate, max_concurrency=args.workers) as client:
        if args.phase in ("discover", "all"):
            await run_discover(client, years, args.pages, raw_dir / IDS_FILE)
        if args.phase in ("details", "all"):
            ids = load_discover_ids(raw_dir / IDS_FILE, years)
            stats = await run_details(
                client, ids, raw_dir / MOVIES_FILE, raw_dir / MISSING_FILE, limit=args.limit, workers=args.workers
            )
            if stats["failed"]:
                print(f"{stats['failed']} films failed; run again to retry them.", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pull films from TMDB into data/raw/.")
    parser.add_argument("--years", default=f"{FIRST_YEAR}-{LAST_YEAR}", help="e.g. 1960-2025 or 2019")
    parser.add_argument("--pages", type=int, default=PAGES_PER_YEAR, help="discover pages per year (20 films each)")
    parser.add_argument("--phase", choices=["discover", "details", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="fetch details for at most N new films")
    parser.add_argument("--rate", type=float, default=20.0, help="requests per second")
    parser.add_argument("--workers", type=int, default=10, help="requests in flight")
    parser.add_argument("--out-dir", default=str(RAW_DIR))
    asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    main()
