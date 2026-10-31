"""Films after MODEL_DATA_MAX_YEAR (2025) are in the database for the app only (V1.2): no model, track record or
comparable may see them, and adding them must not change whether an earlier film is flagged."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import ml.data.build_db as build_db
from ml.data.clean import MODEL_DATA_MAX_YEAR, clean, currency_caps, split_for_year
from ml.features.basic import Franchises
from ml.features.build import FilmForms
from ml.features.history import History, load_films
from tests.factories import TEST_CPI, film
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db, films 1-300)

TRAIN_VIEWS = ("v_train_revenue", "v_train_budget", "v_train_score")
SNAPSHOT = Path("tests/fixtures/pre_v12_snapshot.json")


def pull(movie_id: int, year: int, **over):
    base = {"release_date": f"{year}-03-10", "original_language": "en", "collection": None, **over}
    base["belongs_to_collection"] = over.get("belongs_to_collection")
    return film(movie_id, **{k: v for k, v in base.items() if k != "collection"})


def french(movie_id: int, year: int, budget: int):
    return pull(movie_id, year, original_language="fr", budget=budget, revenue=budget * 2)


YEARS = [2015, 2016, 2018, 2019, 2020, 2021, 2022, 2023]  # the years TEST_CPI has
# 40 French films 2015-2023 (budgets 5-25 M), so French has its own cap: 3 x the 99th percentile of the others
EARLIER = [french(1000 + i, YEARS[i % 8], 5_000_000 * (1 + i % 5)) for i in range(40)]
LATER = [french(2000, 2026, 900_000_000), french(2001, 2026, 12_000_000)]  # a currency slip and a normal budget


@pytest.fixture
def db_with_2026(tmp_path):
    raw, cpi = tmp_path / "raw.jsonl", tmp_path / "cpi.csv"
    films = [pull(1, 2019), pull(2, 2025), pull(3, 2026), *EARLIER, *LATER]
    raw.write_text("".join(json.dumps(r) + "\n" for r in films), encoding="utf-8")
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},t\n" for y, c in TEST_CPI.items()), encoding="utf-8")
    out = tmp_path / "movies.db"
    build_db.build(raw, cpi, out)
    con = sqlite3.connect(out)
    yield con
    con.close()


def test_the_split_of_a_2026_film_is_later_not_test():
    split = split_for_year(pd.Series([2015, 2018, 2019, 2025, 2026]))
    assert list(split) == ["train", "validation", "test", "test", "later"]


def test_no_training_view_returns_a_film_after_2025(db_with_2026):
    for view in TRAIN_VIEWS:
        assert db_with_2026.execute(f"SELECT COUNT(*) FROM {view} WHERE year > ?", (MODEL_DATA_MAX_YEAR,)).fetchone()[0] == 0
    assert db_with_2026.execute("SELECT COUNT(*) FROM movies WHERE year = 2026").fetchone()[0] == 3  # but they are in the database
    assert db_with_2026.execute("SELECT DISTINCT split FROM movies WHERE year = 2026").fetchall() == [("later",)]


def test_a_later_film_does_not_change_the_flags_or_caps_of_earlier_films():
    cpi = TEST_CPI
    without, report_a = clean([*EARLIER], cpi)
    with_later, report_b = clean([*EARLIER, *LATER], cpi)
    cols = ["id", "money_suspect", "money_suspect_reason", "budget_2025"]
    a = without["movies"][cols].set_index("id")
    b = with_later["movies"][cols].set_index("id").loc[a.index]
    pd.testing.assert_frame_equal(a, b)
    assert report_a["currency_caps_2025_usd"] == report_b["currency_caps_2025_usd"]


def test_a_later_film_is_flagged_against_the_earlier_films_cap():
    tables, _ = clean([*EARLIER, *LATER], TEST_CPI)
    m = tables["movies"].set_index("id")
    assert bool(m.loc[2000, "money_suspect"]) and m.loc[2000, "money_suspect_reason"] == "currency"
    assert not bool(m.loc[2001, "money_suspect"])


def test_currency_caps_have_no_later_film_in_their_summary():
    tables, _ = clean([*EARLIER, *LATER], TEST_CPI)
    cap, summary = currency_caps(tables["movies"])
    big = tables["movies"]
    assert summary["fr"] == pytest.approx(3 * big[(big["original_language"] == "fr") & (big["year"] <= 2025)]["budget_2025"].quantile(0.99))
    assert cap.notna().sum() == 42 and summary["fr"] > 0


def test_track_records_franchises_and_features_never_see_a_later_film(db_with_2026):
    films = load_films(db_with_2026)
    assert pd.to_datetime(films["release_date"]).dt.year.max() <= MODEL_DATA_MAX_YEAR and 3 not in set(films["id"])
    assert FilmForms.from_db(db_with_2026).movies["year"].max() <= MODEL_DATA_MAX_YEAR
    db_with_2026.execute("UPDATE movies SET collection_id = 10 WHERE id IN (2, 3)")
    db_with_2026.execute("INSERT OR IGNORE INTO collections (id, name) VALUES (10, 'C')")
    assert len(Franchises.from_db(db_with_2026).films.ids) == 1  # film 2 only
    History.from_db(db_with_2026)  # credits of a later film are simply unmatched


@pytest.mark.real_data
@pytest.mark.skipif(not (build_db.DB_FILE.exists() and SNAPSHOT.exists()), reason="needs data/movies.db")
def test_the_real_database_gives_the_models_the_same_data_as_before_2026_was_added():
    from scripts.snapshot_models import snapshot

    before, now = json.loads(SNAPSHOT.read_text(encoding="utf-8")), snapshot()
    assert now == before


@pytest.mark.real_data
@pytest.mark.skipif(not build_db.DB_FILE.exists(), reason="needs data/movies.db")
def test_the_career_forecast_backtest_on_the_real_database_gives_the_committed_artifact():
    from contextlib import closing

    from ml.career.backtest import MIN_VOTES, OUT_FILE, build_artifact

    with closing(sqlite3.connect(f"file:{build_db.DB_FILE.resolve().as_posix()}?mode=ro", uri=True)) as con:
        built = build_artifact(con, MIN_VOTES, "now")
    assert built["roles"] == json.loads(OUT_FILE.read_text(encoding="utf-8"))["roles"]


def test_a_merge_of_new_films_changes_nothing_the_models_or_the_career_section_read(db, tmp_path):  # noqa: F811
    """V1.3: the refresher writes into movies.db itself. A merge with new films, upcoming ones and a 2025 one must
    leave the track records, franchises, features' forms, the stamp and a career answer as they were."""
    import shutil
    from contextlib import closing

    from backend.app.repo import career
    from backend.app.services.fresh import merge_into, open_for_writing
    from ml.features.build import database_stamp

    path = tmp_path / "movies.db"
    shutil.copyfile(db / "movies.db", path)

    def read() -> tuple:
        with closing(sqlite3.connect(path)) as con:
            con.row_factory = sqlite3.Row
            return (load_films(con).to_json(), FilmForms.from_db(con).movies.to_json(), len(Franchises.from_db(con).films.ids),
                    database_stamp(con), career.latest_year(con),
                    career.career_films(con, 1000, "directing", 50), career.roles_available(con, 2001, 50))

    before = read()
    credits = {"cast": [{"id": 2001, "name": "Actor 1", "character": "Hero", "order": 0}],
               "crew": [{"id": 1000, "name": "Director 0", "job": "Director"}]}  # people of the build's films
    with closing(open_for_writing(path)) as con:
        out = merge_into(con, [film(900_001, release_date="2026-10-25", credits=credits, vote_count=900),
                               film(900_002, status="Planned", release_date="2027-02-01", credits=credits),
                               film(900_003, release_date="2025-11-01", credits=credits)], TEST_CPI, "now")
    assert out["films"] == 2 and out["skipped"] == 1
    assert read() == before
