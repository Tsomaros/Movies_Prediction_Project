"""What the models see, as a small JSON, so a database rebuild can be shown to leave it unchanged (V1.2 Part A).

    uv run python -m scripts.snapshot_models > tests/fixtures/pre_v12_snapshot.json
    uv run python -m scripts.snapshot_models --check tests/fixtures/pre_v12_snapshot.json

For films released up to MODEL_DATA_MAX_YEAR (2025) it records: the rows of each training view, a hash of every
film's cleaning flags (money_suspect, revenue_incomplete, score_ok, split), the currency caps of the cleaning report
and a hash of the features table. A rebuild with the 2026 films added must give the same numbers.
Without --check the JSON is printed; with it the script compares and exits 1 on any difference.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing

import pandas as pd

from ml.data.build_db import DB_FILE

MAX_YEAR = 2025  # MODEL_DATA_MAX_YEAR in ml/data/clean.py; written out here so the script also runs on the old code
VIEWS = ("v_train_revenue", "v_train_budget", "v_train_score")


def _hash(df: pd.DataFrame) -> str:
    return str(int(pd.util.hash_pandas_object(df, index=True).sum()))


def snapshot() -> dict:
    with closing(sqlite3.connect(f"file:{DB_FILE.resolve().as_posix()}?mode=ro", uri=True)) as con:
        counts = {v: con.execute(f"SELECT COUNT(*) FROM {v} WHERE year <= ?", (MAX_YEAR,)).fetchone()[0] for v in VIEWS}
        flags = pd.read_sql_query(
            "SELECT id, money_suspect, revenue_incomplete, score_ok, "
            "CASE WHEN year <= 2018 THEN split END AS split, budget_2025, revenue_2025 "
            "FROM movies WHERE year <= ? ORDER BY id", con, params=(MAX_YEAR,))
        caps = json.loads(con.execute("SELECT value FROM meta WHERE key = 'cleaning_report'").fetchone()[0])["currency_caps_2025_usd"]
        features = pd.read_sql_query(
            "SELECT * FROM features WHERE movie_id IN (SELECT id FROM movies WHERE year <= ?) ORDER BY movie_id", con,
            params=(MAX_YEAR,))
    return {"max_year": MAX_YEAR, "films": len(flags), "train_view_rows": counts, "flags_hash": _hash(flags),
            "currency_caps_2025_usd": caps, "features_rows": len(features), "features_hash": _hash(features)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", metavar="FILE", help="compare with a saved snapshot")
    args = parser.parse_args()
    now = snapshot()
    if not args.check:
        print(json.dumps(now, indent=2, sort_keys=True))
        return
    before = json.load(open(args.check, encoding="utf-8"))
    same = True
    for key in before:
        if before[key] != now.get(key):
            same = False
            print(f"DIFFERENT {key}: {before[key]!r} -> {now.get(key)!r}", file=sys.stderr)
    print("the models' data is unchanged" if same else "the models' data CHANGED")
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
