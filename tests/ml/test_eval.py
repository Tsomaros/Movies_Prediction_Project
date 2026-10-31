"""Tests for ml/eval and ml/models/baselines: metrics on hand-computed examples, the test-set lock,
COVID exclusion, backtest folds, baselines and the per-fold synopsis PCA."""

import json
import math
import sqlite3

import numpy as np
import pandas as pd
import pytest

import ml.data.build_db as build_db
from ml.eval import metrics
from ml.eval.backtest import SYNOPSIS_COLUMNS, refit_synopsis
from ml.eval.evaluate import breakdown_groups, write_reports
from ml.eval.splits import FOLDS, fold_data, load
from ml.eval.splits import TestSetLocked as Locked  # renamed so pytest doesn't collect it as a test class
from ml.features.build import build_table, write_table
from ml.features.synopsis import embed_overviews
from ml.models.baselines import BASELINES, MIN_GENRE_FILMS, BudgetSequel, RevenueMultiple, ScoreDirector
from tests.factories import film
from tests.features.test_features import FakeEmbedder, context, credits

# ---------------------------------------------------------------- metrics (hand-computed)

LOG = math.log


def test_money_metrics_match_hand_computed_values():
    # Actual $10M, $20M, $40M; predicted exactly, 2x too high (counts as within 2x), 4x too low.
    y = [LOG(10e6), LOG(20e6), LOG(40e6)]
    p50 = [LOG(10e6), LOG(40e6), LOG(10e6)]
    p10 = [LOG(5e6), LOG(10e6), LOG(20e6)]
    p90 = [LOG(10e6), LOG(80e6), LOG(40e6)]  # ranges 2x, 8x, 2x wide; every actual inside (edges count)
    m = metrics.money_metrics(y, p10, p50, p90)
    assert m["n"] == 3
    assert m["mae_log"] == pytest.approx((0 + LOG(2) + LOG(4)) / 3)
    assert m["median_pct_error"] == pytest.approx(75.0)  # errors 0%, 100%, 75%
    assert m["within_2x"] == pytest.approx(2 / 3)
    assert m["coverage"] == pytest.approx(1.0)
    assert m["width"] == pytest.approx(2.0)  # median of 2, 8, 2
    assert m["spearman"] == pytest.approx(0.0)


def test_score_metrics_match_hand_computed_values():
    m = metrics.score_metrics(y=[6.0, 7.0, 8.0], p10=[5.0, 6.5, 8.5], p50=[6.5, 7.0, 7.0], p90=[7.0, 7.5, 9.0],
                              weight=[1, 1, 2])
    assert m["mae"] == pytest.approx(0.5)  # 0.5, 0, 1
    assert m["weighted_mae"] == pytest.approx((0.5 + 0 + 2) / 4)
    assert m["coverage"] == pytest.approx(2 / 3)  # 8.0 is below its range
    assert m["width"] == pytest.approx((2 + 1 + 0.5) / 3)
    assert m["spearman"] == pytest.approx(math.sqrt(3) / 2)


def test_within_2x_edges_and_constant_predictions():
    assert metrics.within_2x([LOG(100)], [LOG(200)]) == 1.0
    assert metrics.within_2x([LOG(100)], [LOG(201)]) == 0.0
    assert metrics.within_2x([LOG(100)], [LOG(50)]) == 1.0
    assert math.isnan(metrics.spearman([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]))


# ---------------------------------------------------------------- a small database: 2008-2022

CPI = {y: 100.0 + y - 2000 for y in range(2000, 2027)}


def _record(movie_id: int, year: int, genre: str, **overrides) -> dict:
    genre_ids = {"Action": 28, "Drama": 18, "Comedy": 35}
    return film(movie_id, release_date=f"{year}-06-01", genres=[{"id": genre_ids[genre], "name": genre}],
                belongs_to_collection=None, overview=f"Story number {movie_id}.",
                credits=credits(1000 + movie_id % 7, f"Director {movie_id % 7}", [(2000 + movie_id, f"Actor {movie_id}")]),
                **overrides)


RECORDS = [_record(i, 2008 + i % 15, ["Action", "Drama", "Comedy"][i % 3], budget=10_000_000 * (1 + i % 5),
                   revenue=25_000_000 * (1 + i % 4), vote_average=5.0 + (i % 5) / 2) for i in range(1, 301)]
# 300 films, 20 per year: fold 1 trains on 40 films (2008-09), enough for the 16-number synopsis PCA.


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    """movies.db with a features table, plus the embedding cache, for 300 films from 2008-2022."""
    tmp = tmp_path_factory.mktemp("eval")
    raw, cpi = tmp / "raw.jsonl", tmp / "cpi.csv"
    raw.write_text("".join(json.dumps(r) + "\n" for r in RECORDS), encoding="utf-8")
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in CPI.items()), encoding="utf-8")
    build_db.build(raw, cpi, tmp / "movies.db")
    con = sqlite3.connect(tmp / "movies.db")
    write_table(con, build_table(con, context(con), cache=tmp / "emb.npz"))
    con.close()
    return tmp


def test_test_split_is_locked(db):
    with pytest.raises(Locked):
        load("revenue", "test", db_path=db / "movies.db")
    assert len(load("revenue", "test", final=True, db_path=db / "movies.db")) > 0


def test_exclude_covid_drops_exactly_2020_and_2021(db):
    full = load("revenue", "test", final=True, db_path=db / "movies.db")
    no_covid = load("revenue", "test", final=True, exclude_covid=True, db_path=db / "movies.db")
    assert set(full["year"]) - set(no_covid["year"]) == {2020, 2021}
    assert len(full) - len(no_covid) == full["year"].isin([2020, 2021]).sum()


def test_splits_follow_the_years(db):
    for split, (low, high) in {"train": (0, 2015), "validation": (2016, 2018)}.items():
        years = load("score", split, db_path=db / "movies.db")["year"]
        assert years.between(low, high).all() and len(years)


@pytest.mark.parametrize("fold", FOLDS, ids=[f.name for f in FOLDS])
def test_backtest_folds_never_train_on_or_after_their_test_years(db, fold):
    train, test = fold_data("revenue", fold, db_path=db / "movies.db")
    assert train["year"].max() < fold.test_first
    assert test["year"].between(fold.test_first, fold.test_last).all()
    assert (train["year"].max() <= 2018) and (test["year"].max() <= 2018)  # never 2019+
    assert len(train) and len(test)


def test_every_row_has_main_genre_target_and_typical_score(db):
    df = load("score", "train", db_path=db / "movies.db")
    assert set(df["main_genre"]) <= {"Action", "Drama", "Comedy"}
    assert df["target"].between(0, 10).all()
    assert {"typical_score", "typical_revenue", "score_weight", "budget_2025"} <= set(df.columns)


# ---------------------------------------------------------------- baselines


def frame(n_per_genre: dict[str, int], **columns) -> pd.DataFrame:
    genres = [g for g, n in n_per_genre.items() for _ in range(n)]
    return pd.DataFrame({"main_genre": genres, **{k: v(len(genres)) if callable(v) else v for k, v in columns.items()}})


def test_b0_b1_medians_and_small_genre_fallback():
    # Drama has enough films for its own median; Western doesn't and uses the global median.
    train = frame({"Drama": MIN_GENRE_FILMS, "Western": 3}, target=lambda n: np.r_[np.full(MIN_GENRE_FILMS, 2.0), [9.0] * 3])
    test = frame({"Drama": 1, "Western": 1, "Horror": 1})  # Horror never seen
    b0, b1 = BASELINES["budget"][0]().fit(train), BASELINES["budget"][1]().fit(train)
    assert b0.predict(test)["p50"].tolist() == [2.0, 2.0, 2.0]
    assert b1.predict(test)["p50"].tolist() == [2.0, 2.0, 2.0]  # Western and Horror fall back to the global 2.0


def test_ranges_come_from_train_residuals_and_are_ordered():
    rng = np.random.default_rng(0)
    train = frame({"Drama": 200}, target=lambda n: rng.normal(6, 1, n))
    m = BASELINES["score"][0]().fit(train)
    p = m.predict(train)
    assert (p["p10"] <= p["p50"]).all() and (p["p50"] <= p["p90"]).all()
    covered = ((train["target"] >= p["p10"]) & (train["target"] <= p["p90"])).mean()
    assert covered == pytest.approx(0.8, abs=0.01)


def test_b2_revenue_is_budget_times_the_genre_multiple():
    log_budget = lambda n: np.full(n, LOG(10e6))
    train = frame({"Action": 40}, log_budget=log_budget, target=lambda n: np.full(n, LOG(30e6)))
    test = frame({"Action": 1}, log_budget=[LOG(50e6)])
    assert math.exp(RevenueMultiple().fit(train).predict(test)["p50"].iloc[0]) == pytest.approx(150e6)


def test_b2_budget_applies_the_sequel_factor():
    sequel = np.r_[np.zeros(30), np.ones(10)]
    target = np.r_[np.full(30, LOG(10e6)), np.full(10, LOG(20e6))]  # sequels cost 2x
    train = frame({"Drama": 40}, target=target, is_franchise=sequel)
    # The genre median over all 40 films is the originals' $10M, so the sequel factor is 2x.
    m = BudgetSequel().fit(train)
    assert math.exp(m.sequel_factor) == pytest.approx(2.0)
    p = m.predict(frame({"Drama": 2}, is_franchise=[0, 1]))["p50"]
    assert [math.exp(v) for v in p] == pytest.approx([10e6, 20e6])


def test_b2_score_fits_the_director_weight():
    gap = np.r_[np.zeros(20), np.full(20, 0.5)]  # director's earlier score above typical by 0.5
    train = frame({"Drama": 40}, target=np.r_[np.full(20, 6.0), np.full(20, 6.75)],
                  director_score=6.0 + gap, typical_score=6.0)
    m = ScoreDirector().fit(train)
    # Genre median = (6.0 + 6.75) / 2 = 6.375; residuals -0.375 / +0.375; least squares w = 0.375 / 0.5 = 0.75.
    assert m.weight == pytest.approx(0.75)
    new = frame({"Drama": 1}, director_score=[np.nan], typical_score=[np.nan])  # no history: no adjustment
    assert m.predict(new)["p50"].iloc[0] == pytest.approx(6.375)


def test_score_ranges_stay_within_0_and_10():
    train = frame({"Drama": 40}, target=np.r_[np.full(20, 0.5), np.full(20, 9.8)])
    p = BASELINES["score"][0]().fit(train).predict(train)
    assert p.min().min() >= 0.0 and p.max().max() <= 10.0


# ---------------------------------------------------------------- breakdowns and reports


def test_breakdown_groups_split_every_film_once():
    df = pd.DataFrame({"budget_2025": [5e6, 20e6, 100e6, 300e6], "original_language": ["en", "fr", "en", "en"],
                       "director_is_new": [1, 0, 0, 1], "is_franchise": [0, 0, 1, 0]})
    groups = breakdown_groups("revenue", df)
    assert set(groups) == {"budget size", "language", "director", "franchise"}
    for masks in groups.values():
        assert sum(m.astype(int) for m in masks.values()).tolist() == [1, 1, 1, 1]
    assert "budget size" not in breakdown_groups("score", df)


def test_reports_are_written_with_valid_json(tmp_path):
    m = {"n": 3, "mae": 0.5, "weighted_mae": 0.6, "spearman": float("nan"), "coverage": 0.8, "width": 2.0}
    fold = {"fold": "fold 1", "train_years": "<=2009", "test_years": "2010-2012", "train_n": 10, "metrics": m}
    result = {"name": "B0", "target": "score", "validation": m, "breakdowns": {"language": {"English": m}},
              "backtest": {"folds": [fold], "mean": m, "std": m}}
    write_reports({"score": [result]}, tmp_path)
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))["score"][0]["validation"]["spearman"] is None
    assert "| B0 | 3 | 0.500 | 0.600 | — | 80.0% | 2.00 pts |" in (tmp_path / "metrics.md").read_text(encoding="utf-8")
    assert {p.name for p in tmp_path.iterdir()} == {"metrics.json", "metrics.md", "breakdowns.md", "backtest.md"}


# ---------------------------------------------------------------- per-fold synopsis PCA


def test_fold_pca_is_fitted_on_the_folds_train_years_only(db, tmp_path):
    fold = FOLDS[0]  # train <= 2009
    train, test = fold_data("score", fold, db_path=db / "movies.db")
    base_train, base_test = refit_synopsis(train, test, fold.train_last, cache=db / "emb.npz", db_path=db / "movies.db")

    # Replace every post-2009 film's vector with something wild: the fold's PCA must not move.
    con = sqlite3.connect(db / "movies.db")
    later = {r[0] for r in con.execute("SELECT id FROM movies WHERE year > ?", (fold.train_last,))}
    con.close()
    with np.load(db / "emb.npz") as d:
        data = {k: d[k] for k in d.files}
    for i, movie_id in enumerate(data["ids"]):
        if int(movie_id) in later:
            data["vectors"][i] = 100.0
    np.savez(tmp_path / "wild.npz", **data)
    wild_train, _ = refit_synopsis(train, test, fold.train_last, cache=tmp_path / "wild.npz", db_path=db / "movies.db")
    assert np.allclose(wild_train[SYNOPSIS_COLUMNS].to_numpy(), base_train[SYNOPSIS_COLUMNS].to_numpy())
    assert not np.allclose(base_test[SYNOPSIS_COLUMNS].to_numpy(), 0)  # test rows do get fold numbers


def test_fold_pca_leaves_other_columns_alone(db):
    train, test = fold_data("score", FOLDS[1], db_path=db / "movies.db")
    new_train, _ = refit_synopsis(train, test, FOLDS[1].train_last, cache=db / "emb.npz", db_path=db / "movies.db")
    assert new_train.drop(columns=SYNOPSIS_COLUMNS).equals(train.drop(columns=SYNOPSIS_COLUMNS))
