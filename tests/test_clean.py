"""Tests for the cleaning rules in ml/data/clean.py, on small fake records."""

import math

import numpy as np
import pandas as pd
import pytest

from ml.data.clean import POOLED_LANGUAGE, clean, flatten, leave_one_out_quantile, select_records
from tests.factories import TEST_CPI, film


def cleaned(records: list[dict]) -> pd.DataFrame:
    tables, _ = clean(records, TEST_CPI)
    return tables["movies"].set_index("id")


# ---------------------------------------------------------------- money


def test_placeholder_money_nulled_but_micro_budget_kept():
    m = cleaned([
        film(1, budget=7, revenue=999),               # "7" meaning $7M
        film(2, budget=15_000, revenue=2_000_000),    # a real micro-budget
        film(3, budget=0, revenue=0),                 # unknown
    ])
    assert pd.isna(m.loc[1, "budget"]) and pd.isna(m.loc[1, "revenue"])
    assert m.loc[2, "budget"] == 15_000 and m.loc[2, "revenue"] == 2_000_000
    assert pd.isna(m.loc[3, "budget"]) and pd.isna(m.loc[3, "budget_2025"])


def test_inflation_to_2025_dollars():
    m = cleaned([film(1, release_date="2019-07-12", budget=50_000_000, revenue=180_000_000)])
    assert m.loc[1, "budget"] == 50_000_000  # nominal kept
    assert m.loc[1, "budget_2025"] == round(50_000_000 * 130 / 110)
    assert m.loc[1, "revenue_2025"] == round(180_000_000 * 130 / 110)


def test_token_box_office_is_suspect():
    m = cleaned([film(1, budget=65_500_000, revenue=1_281)])
    assert m.loc[1, "money_suspect"]
    assert m.loc[1, "money_suspect_reason"] == "low_ratio"


def test_micro_budget_hit_is_not_suspect():
    # Blair Witch: about 4,000x its budget, and real.
    m = cleaned([film(1, budget=60_000, revenue=248_600_000)])
    assert not m.loc[1, "money_suspect"]
    assert pd.isna(m.loc[1, "money_suspect_reason"])


def hindi_market(n: int = 150) -> list[dict]:
    """n Hindi films with budgets of $1M-$3M; enough for the language to get its own cap."""
    return [
        film(1000 + i, original_language="hi", budget=1_000_000 + i * 13_000, revenue=5_000_000)
        for i in range(n)
    ]


def test_budget_in_rupees_is_suspect():
    rupees = film(1, original_language="hi", budget=3_000_000_000, revenue=9_000_000_000)
    tables, report = clean([*hindi_market(), rupees], TEST_CPI)
    m = tables["movies"].set_index("id")
    assert m.loc[1, "money_suspect"] and m.loc[1, "money_suspect_reason"] == "currency"
    assert m["money_suspect"].sum() == 1
    assert "hi" in report["currency_caps_2025_usd"]


def test_small_language_uses_pooled_cap_and_english_is_never_capped():
    tamil = film(1, original_language="ta", budget=3_000_000_000, revenue=9_000_000_000)
    english = film(2, original_language="en", budget=3_000_000_000, revenue=9_000_000_000)
    tables, report = clean([*hindi_market(), tamil, english], TEST_CPI)
    m = tables["movies"].set_index("id")
    assert "ta" not in report["currency_caps_2025_usd"] and POOLED_LANGUAGE in report["currency_caps_2025_usd"]
    assert m.loc[1, "money_suspect_reason"] == "currency"
    assert not m.loc[2, "money_suspect"]


def test_outlier_in_a_small_market_does_not_raise_its_own_cap():
    # 40 budgets: with the outlier included, the 99th percentile would sit close to the outlier itself.
    market = [film(2000 + i, original_language="pt", budget=1_000_000 + i * 50_000, revenue=5_000_000) for i in range(40)]
    outlier = film(1, original_language="pt", budget=3_000_000_000, revenue=9_000_000_000)
    m = cleaned([*market, outlier])
    assert m.loc[1, "money_suspect_reason"] == "currency"
    assert m["money_suspect"].sum() == 1


@pytest.mark.parametrize("n", [2, 3, 5, 31, 100, 237])
def test_leave_one_out_quantile_matches_brute_force(n):
    rng = np.random.default_rng(n)
    values = pd.Series(rng.integers(1, 20, size=n) * 1e6, index=rng.permutation(n) + 100)  # with ties
    expected = [values.drop(i).quantile(0.99) for i in values.index]
    assert leave_one_out_quantile(values, 0.99).tolist() == pytest.approx(expected)


def test_still_earning_film_is_incomplete():
    m = cleaned([
        film(1, release_date="2026-06-01"),  # 142 days before the pull
        film(2, release_date="2026-03-01"),  # 234 days before the pull
    ])
    assert m.loc[1, "revenue_incomplete"]
    assert not m.loc[2, "revenue_incomplete"]


def test_covid_period():
    m = cleaned([film(y, release_date=f"{y}-05-01") for y in (2019, 2020, 2021, 2022)])
    assert m["covid_period"].to_dict() == {2019: False, 2020: True, 2021: True, 2022: False}


# ---------------------------------------------------------------- score


def test_zero_vote_film_has_no_score():
    m = cleaned([film(1, vote_count=0, vote_average=0.0)])
    assert pd.isna(m.loc[1, "vote_average"])
    assert not m.loc[1, "score_ok"]
    assert m.loc[1, "score_weight"] == 0


@pytest.mark.parametrize(("votes", "ok"), [(49, False), (50, True)])
def test_vote_threshold(votes, ok):
    m = cleaned([film(1, vote_count=votes, vote_average=7.1)])
    assert m.loc[1, "score_ok"] == ok
    assert m.loc[1, "score_weight"] == pytest.approx(math.log1p(votes))


# ---------------------------------------------------------------- basic cleaning


def test_duplicate_id_keeps_latest_pull_and_unreleased_are_dropped():
    records = [
        film(1, title="Old title", pulled_at="2026-04-01T00:00:00+00:00"),
        film(1, title="New title", pulled_at="2026-10-21T00:00:00+00:00"),
        film(2, status="Post Production"),
    ]
    kept, report = select_records(records)
    assert [(r["id"], r["title"]) for r in kept] == [(1, "New title")]
    assert report == {"duplicate_ids_dropped": 1, "not_released_dropped": 1}


@pytest.mark.parametrize(("runtime", "expected"), [(0, None), (601, None), (600, 600), (118, 118), (None, None)])
def test_runtime_rule(runtime, expected):
    m = cleaned([film(1, runtime=runtime)])
    assert (pd.isna(m.loc[1, "runtime"]) and expected is None) or m.loc[1, "runtime"] == expected


def test_text_is_trimmed_and_title_falls_back():
    m = cleaned([film(1, title="  ", original_title="La Haine ", overview="", tagline="  Tagline ")])
    assert m.loc[1, "title"] == "La Haine"
    assert pd.isna(m.loc[1, "overview"])
    assert m.loc[1, "tagline"] == "Tagline"


@pytest.mark.parametrize(
    ("date", "split"),
    [("2015-12-31", "train"), ("2016-01-01", "validation"), ("2018-12-31", "validation"), ("2019-01-01", "test")],
)
def test_split_by_release_year(date, split):
    m = cleaned([film(1, release_date=date)])
    assert m.loc[1, "split"] == split
    assert m.loc[1, "year"] == int(date[:4]) and m.loc[1, "month"] == int(date[5:7])


def test_missing_release_date_gets_no_year_or_split():
    tables, report = clean([film(1, release_date="")], TEST_CPI)
    m = tables["movies"].set_index("id")
    assert pd.isna(m.loc[1, "year"]) and pd.isna(m.loc[1, "split"])
    assert report["no_split_missing_year"] == 1


# ---------------------------------------------------------------- flatten


def test_flatten_keeps_most_common_spelling_and_one_cast_row_per_actor():
    def credits(name: str, cast: list[dict]) -> dict:
        return {"cast": cast, "crew": [{"id": 1, "name": name, "job": "Director"}]}

    actor = {"id": 50, "name": "A", "character": "Twin 1", "order": 3}
    records = [
        film(1, credits=credits("Jesús Franco", [actor, {**actor, "character": "Twin 2", "order": 0}])),
        film(2, credits=credits("Jesús Franco", [])),
        film(3, credits=credits("Jesus Franco", [])),
    ]
    tables = flatten(records)
    people = tables["people"].set_index("id")
    assert people.loc[1, "name"] == "Jesús Franco"
    cast = tables["movie_cast"]
    assert cast[cast["movie_id"] == 1][["person_id", "character", "ord"]].values.tolist() == [[50, "Twin 2", 0]]


def test_flatten_keeps_tmdb_genre_order():
    genres = [{"id": 80, "name": "Crime"}, {"id": 53, "name": "Thriller"}, {"id": 18, "name": "Drama"},
              {"id": 53, "name": "Thriller"}]  # listed twice: keeps its first position
    links = flatten([film(1, genres=genres)])["movie_genres"]
    assert links.sort_values("ord")[["genre_id", "ord"]].values.tolist() == [[80, 0], [53, 1], [18, 2]]


def test_report_counts_every_rule():
    _, report = clean([film(1, budget=7), film(2, runtime=0), film(3, vote_count=10)], TEST_CPI)
    assert report["films"] == 3
    assert report["budget_placeholder_nulled"] == 1
    assert report["runtime_nulled"] == 1
    assert report["score_ok"] == 2 and report["score_below_min_votes"] == 1
