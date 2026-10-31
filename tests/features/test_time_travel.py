"""Time travel: the strongest leakage test. A database cut off at a date must give the same features as the full one.

For a cut date C (1 January of a year), copy the database and delete every film released on or after C,
with all its links. Build a FeatureContext from each database and judge films at C: every feature
(track records, franchise, budget track record, themes, synopsis numbers, timing) must be identical,
because a film judged at C may only see films released strictly before C, and those are in both
databases. Any difference means a feature looked at the future.

Films judged are the deleted ones, from C onwards, written as forms from the full database: exactly the
films whose data the cut removed. The form is built once, from the full database: film_to_form picks a
film's most experienced director at the film's own release date, which is after C, so it may rightly
differ between the databases (an anthology like Scare Package, 2019, has 8 directors). The fixture's cut (2017) has a film released on the cut day itself, so
counting same-day films would show up too.

- fixture version (tests/fixtures/mini_raw.jsonl): always runs, a few seconds;
- real version (data/movies.db, cut 2010, 300 films from 2010 on): marked slow and real_data. Its copy is
  made in a temp folder with SQLite's backup API; data/movies.db is opened read-only and never changed.
  It also refits the parts fitted on train years (vocab, theme keywords, synopsis PCA) and checks they
  match the committed files, so no later film shaped them.
"""

import json
import sqlite3
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.data import build_db
from ml.data.build_db import DB_FILE
from ml.features.build import FeatureContext, FilmForms, build_features, film_to_form
from ml.features.history import day_number
from tests.fixtures import mini_raw
from tests.features.test_features import FakeEmbedder

LINKS = ("movie_genres", "movie_companies", "movie_keywords", "movie_cast", "movie_crew", "movie_countries",
         "movie_languages")
CPI = {y: 100.0 + 2 * (y - 2000) for y in range(2000, 2027)}


def truncate(src: Path, dst: Path, cut: date) -> int:
    """Copy src to dst without the films released on or after `cut`; returns how many were deleted."""
    with sqlite3.connect(f"file:{src.resolve().as_posix()}?mode=ro", uri=True) as source, sqlite3.connect(dst) as out:
        source.backup(out)
    con = sqlite3.connect(dst)
    with con:
        later = "SELECT id FROM movies WHERE release_date >= ?"
        for table in LINKS:
            con.execute(f"DELETE FROM {table} WHERE movie_id IN ({later})", (cut.isoformat(),))
        con.execute("DROP TABLE IF EXISTS features")
        con.execute("DROP TABLE IF EXISTS movies_fts")  # its content table is about to change; not used here
        deleted = con.execute("DELETE FROM movies WHERE release_date >= ?", (cut.isoformat(),)).rowcount
    con.close()
    return deleted


def compare(full_db: Path, cut_db: Path, cut: date, sample: int | None = None, seed: int = 0) -> dict:
    """Features of the cut-off films at `cut`, from both databases; returns {"films", "differences"}."""
    embedder = FakeEmbedder()  # the synopsis numbers depend on the text only, so a fake text model is enough
    with sqlite3.connect(f"file:{full_db.resolve().as_posix()}?mode=ro", uri=True) as con:
        full, films = FeatureContext.load(con, embedder=embedder), FilmForms.from_db(con)
    with sqlite3.connect(cut_db) as con:
        cut_ctx = FeatureContext.load(con, embedder=embedder)
    ids = films.movies.index[films.movies["release_date"] >= cut.isoformat()].to_series()
    if sample is not None and len(ids) > sample:
        ids = ids.sample(sample, random_state=seed)
    as_of = day_number(cut)
    differences = {}
    for movie_id in ids:
        form = film_to_form(movie_id, films, full)  # once, from the full database (see the module docstring)
        a, b = build_features(form, as_of, full), build_features(form, as_of, cut_ctx)
        diff = [k for k in a if not (a[k] == b[k] or (pd.isna(a[k]) and pd.isna(b[k])))]
        if diff:
            differences[int(movie_id)] = {k: (a[k], b[k]) for k in diff}
    return {"films": len(ids), "differences": differences}


# ---------------------------------------------------------------- the fixture


FIXTURE_CUT = date(2017, 1, 1)


@pytest.fixture(scope="module")
def mini_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("time_travel")
    cpi = tmp / "cpi.csv"
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in CPI.items()), encoding="utf-8")
    build_db.build(mini_raw.FILE, cpi, tmp / "full.db")
    deleted = truncate(tmp / "full.db", tmp / "cut.db", FIXTURE_CUT)
    return tmp / "full.db", tmp / "cut.db", deleted


def test_the_cut_removes_exactly_the_later_films(mini_db):
    full, cut, deleted = mini_db
    with sqlite3.connect(full) as a, sqlite3.connect(cut) as b:
        later = a.execute("SELECT COUNT(*) FROM movies WHERE release_date >= ?", (FIXTURE_CUT.isoformat(),)).fetchone()[0]
        assert deleted == later > 0
        assert b.execute("SELECT MAX(release_date) FROM movies").fetchone()[0] < FIXTURE_CUT.isoformat()
        assert b.execute("SELECT COUNT(*) FROM movie_cast WHERE movie_id NOT IN (SELECT id FROM movies)").fetchone()[0] == 0
        on_the_day = a.execute("SELECT COUNT(*) FROM movies WHERE release_date = ?", (FIXTURE_CUT.isoformat(),)).fetchone()[0]
        assert on_the_day >= 1  # a film released on the cut day: same-day leaks would show


def test_no_feature_changes_when_the_future_is_deleted(mini_db):
    full, cut, _ = mini_db
    result = compare(full, cut, FIXTURE_CUT)
    assert result["films"] >= 40
    assert result["differences"] == {}


def test_the_test_would_see_a_leak(mini_db, monkeypatch):
    """Sanity of the test itself: a history that counts films released on the judging day must be caught."""
    from ml.features import history

    original = history.History.person

    def leaky(self, person_id, role, as_of):
        return original(self, person_id, role, as_of + 1)  # sees the judging day's own films

    monkeypatch.setattr(history.History, "person", leaky)
    full, cut, _ = mini_db
    assert compare(full, cut, FIXTURE_CUT)["differences"]


# ---------------------------------------------------------------- the real database

REAL_CUT = date(2010, 1, 1)


@pytest.fixture(scope="module")
def real_cut(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("time_travel_real")
    before = DB_FILE.stat().st_mtime_ns
    deleted = truncate(DB_FILE, tmp / "cut.db", REAL_CUT)
    yield tmp / "cut.db", deleted
    assert DB_FILE.stat().st_mtime_ns == before  # the real database was never written


@pytest.mark.slow
@pytest.mark.real_data
@pytest.mark.skipif(not DB_FILE.exists(), reason="needs data/movies.db")
def test_the_real_database_cut_at_2010_changes_no_feature(real_cut):
    cut_db, deleted = real_cut
    assert deleted > 15_000  # 2010-2025: 16 years of about 1,200 films
    result = compare(DB_FILE, cut_db, REAL_CUT, sample=300)
    assert result["films"] == 300 and result["differences"] == {}


@pytest.mark.slow
@pytest.mark.real_data
@pytest.mark.skipif(not DB_FILE.exists(), reason="needs data/movies.db")
def test_the_vocab_and_theme_keywords_come_from_train_films_only():
    from ml.features.basic import fit_vocab, load_vocab
    from ml.features.themes import N_KEYWORDS, load_themes, top_keywords

    with sqlite3.connect(f"file:{DB_FILE.resolve().as_posix()}?mode=ro", uri=True) as con:
        assert fit_vocab(con) == load_vocab()  # refitted on split = 'train' (<=2015): the same lists
        common = set(top_keywords(con, N_KEYWORDS)["id"])  # the 300 most common keywords in train films
    themed = {k for ids in load_themes().values() for k in ids}
    assert themed <= common


@pytest.mark.slow
@pytest.mark.real_data
@pytest.mark.skipif(not (DB_FILE.exists() and Path("data/overview_embeddings.npz").exists()),
                    reason="needs data/movies.db and the overview embedding cache")
def test_the_synopsis_pca_is_fitted_on_train_films_only():
    from ml.features.synopsis import EMBEDDINGS_FILE, PCA_FILE, fit_pca

    with sqlite3.connect(f"file:{DB_FILE.resolve().as_posix()}?mode=ro", uri=True) as con:
        train = set(pd.read_sql_query("SELECT id FROM movies WHERE split = 'train'", con)["id"])
    with np.load(EMBEDDINGS_FILE) as z:
        vectors = z["vectors"][np.isin(z["ids"], list(train))]
    saved = json.loads(PCA_FILE.read_text(encoding="utf-8"))
    refit = fit_pca(vectors)
    assert np.allclose(refit["mean"], saved["mean"], atol=1e-6)
    cosines = np.abs(np.sum(np.array(refit["components"]) * np.array(saved["components"]), axis=1))
    assert np.all(cosines > 0.999)  # the same 16 directions (a sign flip is the same component)
    assert f"{len(vectors):,} train films" in saved["about"]
