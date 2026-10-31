import json

import pandas as pd

from ml.data.wikidata_money import BUDGET_AMBIGUOUS, WORLDWIDE, load_statements, select_money

US = "Q30"
FX = {("EUR", 2005): 0.8, ("GBP", 2005): 0.5}


def st(prop="box_office", amount=100, currency="USD", rank="normal", region=None, pit=None, year=2005, tmdb_id=1):
    return {
        "statement": f"s{amount}{pit}{region}{rank}",
        "wikidata_id": "Q1",
        "tmdb_id": tmdb_id,
        "prop": prop,
        "amount": amount,
        "currency": currency,
        "rank": rank,
        "region": region,
        "point_in_time": pit,
        "year": year,
    }


def one(statements, fx=FX):
    df, rep = select_money(statements, fx)
    return df, rep


def test_worldwide_beats_us_only():
    df, rep = one([st(amount=50, region=US), st(amount=200, region=WORLDWIDE)])
    assert df.wd_revenue.tolist() == [200]
    assert rep["wikidata_region_dropped"] == 1


def test_single_untagged_kept():
    df, rep = one([st(amount=70)])
    assert df.wd_revenue.tolist() == [70]
    assert rep["wikidata_region_dropped"] == 0


def test_two_untagged_none_kept():
    df, rep = one([st(amount=70, pit="2000-01-01"), st(amount=90, pit="2001-01-01")])
    assert df.empty
    assert rep["wikidata_region_dropped"] == 2


def test_untagged_plus_us_none_kept():
    df, rep = one([st(amount=70), st(amount=90, region=US)])
    assert df.empty
    assert rep["wikidata_region_dropped"] == 2


def test_latest_worldwide_wins():
    df, _ = one([
        st(amount=10, region=WORLDWIDE, pit="2000-01-01"),
        st(amount=20, region=WORLDWIDE, pit="2002-01-01"),
        st(amount=5, region=WORLDWIDE),
    ])
    assert df.wd_revenue.tolist() == [20]


def test_preferred_beats_later_normal():
    df, _ = one([
        st(amount=10, region=WORLDWIDE, rank="preferred", pit="2000-01-01"),
        st(amount=20, region=WORLDWIDE, pit="2002-01-01"),
    ])
    assert df.wd_revenue.tolist() == [10]


def test_region_filter_before_preferred():
    df, _ = one([st(amount=50, region=US, rank="preferred"), st(amount=200, region=WORLDWIDE)])
    assert df.wd_revenue.tolist() == [200]


def test_budget_ambiguous_dropped():
    assert BUDGET_AMBIGUOUS == 2.0
    df, rep = one([
        st("budget", 10_000_000, pit="2000-01-01"),
        st("budget", 30_000_000, pit="2001-01-01"),
    ])
    assert df.empty
    assert rep["wikidata_budget_ambiguous"] == 1


def test_budget_close_takes_latest():
    df, rep = one([
        st("budget", 10_000_000, pit="2000-01-01"),
        st("budget", 15_000_000, pit="2001-01-01"),
    ])
    assert df.wd_budget.tolist() == [15_000_000]
    assert rep["wikidata_budget_ambiguous"] == 0


def test_unknown_currency_dropped():
    df, rep = one([st("budget", 100, currency="ZAR"), st("budget", 100, currency=None, tmdb_id=2)])
    assert df.empty
    assert rep["wikidata_currency_dropped"] == 2


def test_known_currency_missing_year():
    df, rep = one([st("budget", 100, currency="EUR", year=1995)])
    assert df.empty
    assert rep["wikidata_fx_missing"] == 1


def test_conversion_and_dtype():
    df, _ = one([st("budget", 80, currency="EUR"), st(amount=50, currency="GBP", region=WORLDWIDE)])
    assert df.wd_budget.tolist() == [100]
    assert df.wd_revenue.tolist() == [100]
    assert str(df.wd_budget.dtype) == "Int64"


def test_nonpositive_dropped_and_report_keys():
    df, rep = one([st(amount=0), st("budget", -5)])
    assert df.empty
    assert rep["wikidata_nonpositive_dropped"] == 2
    assert set(rep) == {
        "wikidata_region_dropped",
        "wikidata_currency_dropped",
        "wikidata_fx_missing",
        "wikidata_budget_ambiguous",
        "wikidata_nonpositive_dropped",
    }


def test_partial_row_has_null_and_smallest_year():
    df, _ = one([st("budget", 100, year=2006), st(amount=5, region=US, year=2004)])
    assert df.id.tolist() == [1]
    assert df.year.tolist() == [2004]
    assert df.wd_budget.tolist() == [100]
    assert pd.isna(df.wd_revenue.iloc[0])


def test_load_statements_skips_markers(tmp_path):
    p = tmp_path / "w.jsonl"
    p.write_text(json.dumps({"year": 1999, "empty": True}) + "\n" + json.dumps(st()) + "\n", encoding="utf-8")
    assert len(load_statements(p)) == 1
