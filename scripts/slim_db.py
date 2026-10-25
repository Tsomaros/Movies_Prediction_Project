"""Make the database copy the Docker image ships: data/movies.db without what only training needs.

    uv run python scripts/slim_db.py [--src data/movies.db] [--out build/movies.db]

Drops the `features` table (training and the comparables build read it; the app computes features from
the films themselves) and VACUUMs the copy. Everything the API and predict() read stays: films, people,
companies, keywords, collections, the link tables, the FTS index, the views and `meta`. The source is
opened read-only and never changed; the copy is checked to have the same films and an intact FTS index.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

TRAINING_ONLY = ("features",)
APP_TABLES = ("movies", "people", "companies", "keywords", "collections", "genres", "movie_genres", "movie_companies",
              "movie_keywords", "movie_cast", "movie_crew", "movie_countries", "movie_languages", "meta", "movies_fts",
              "person_details")


def slim(src: Path, out: Path) -> dict[str, float]:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    source_uri = f"file:{src.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(sqlite3.connect(tmp)) as copy:
        source.backup(copy)
    con = sqlite3.connect(tmp)
    for table in TRAINING_ONLY:
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.commit()
    con.execute("VACUUM")
    films = con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    missing = [t for t in APP_TABLES if not con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (t,)).fetchone()]
    con.execute("INSERT INTO movies_fts(movies_fts) VALUES ('integrity-check')")  # raises if the index is broken
    con.close()
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        if missing or films != source.execute("SELECT COUNT(*) FROM movies").fetchone()[0]:
            tmp.unlink()
            raise RuntimeError(f"slim copy is wrong: missing {missing}, {films} films")
    tmp.replace(out)
    return {"films": films, "source_mb": src.stat().st_size / 1e6, "slim_mb": out.stat().st_size / 1e6}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=Path("data/movies.db"))
    parser.add_argument("--out", type=Path, default=Path("build/movies.db"))
    args = parser.parse_args()
    start = time.perf_counter()
    r = slim(args.src, args.out)
    print(f"{args.out}: {r['films']:,} films, {r['source_mb']:.0f} MB -> {r['slim_mb']:.0f} MB "
          f"({time.perf_counter() - start:.0f} s)", file=sys.stderr)


if __name__ == "__main__":
    main()
