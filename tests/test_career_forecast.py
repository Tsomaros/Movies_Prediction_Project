"""The track-record forecast maths (Day 14.8): weights, shrinkage toward the role's average, the range and the
career line."""

from __future__ import annotations

import math

import pytest

from ml.career.forecast import RoleSettings, rolling_line, track_record

S = RoleSettings(h=8, k=3, q=1.3)


def test_needs_five_rated_films():
    assert track_record([(2000, 7.0)] * 4, S, mu=6.3, sigma_pop=0.9) is None


def test_weights_halve_every_h_years():
    f = track_record([(2000, 5.0)] + [(2016, 8.0)] * 4, RoleSettings(8, 0.0001, 1.0), 6.3, 0.9)
    assert f.own_avg == pytest.approx((0.25 * 5 + 4 * 8) / 4.25)  # a film 16 years older counts 1/4


def test_short_career_leans_to_average_long_career_to_own():
    short = track_record([(2010 + i, 8.0) for i in range(5)], S, 6.0, 0.9)
    long_ = track_record([(1980 + i, 8.0) for i in range(40)], S, 6.0, 0.9)
    assert 6.0 < short.mid < long_.mid < 8.0 and long_.own_share > short.own_share


def test_few_effective_films_sit_near_the_average_and_many_near_their_own():
    few = track_record([(1950, 9.0)] * 4 + [(2020, 9.0)], RoleSettings(3, 13, 1.0), 6.0, 0.9)
    many = track_record([(2020, 9.0)] * 40, RoleSettings(math.inf, 1, 1.0), 6.0, 0.9)
    assert few.mid - 6.0 < 0.5 and 9.0 - many.mid < 0.1


def test_identical_scores_still_give_a_range():
    f = track_record([(2000 + i, 7.0) for i in range(10)], S, 6.3, 0.9)
    assert f.low < f.mid < f.high and not math.isnan(f.low)


def test_infinite_h_and_huge_gap_are_stable():
    for s in (RoleSettings(math.inf, 3, 1.3), RoleSettings(3, 3, 1.3)):
        f = track_record([(1950, 6.0)] + [(2020, 7.0)] * 5, s, 6.3, 0.9)
        assert all(map(math.isfinite, (f.low, f.mid, f.high)))


def test_the_effective_film_count_stays_between_one_and_n():
    k = 3
    f = track_record([(1950, 6.0)] + [(2010, 7.0)] * 4, RoleSettings(3, k, 1.3), 6.3, 0.9)
    n_eff = k * f.own_share / (1 - f.own_share)
    assert 1 <= n_eff <= 5


def test_range_clipped_to_scale():
    f = track_record([(2000 + i, 9.9) for i in range(30)], RoleSettings(8, 1, 5.0), 6.3, 2.0)
    assert 1.0 <= f.low and f.high <= 10.0


def test_rolling_line_centred_window():
    pts = [(2000 + i, float(i)) for i in range(7)]
    assert rolling_line(pts) == [(2000, 1.0), (2001, 1.5), (2002, 2.0), (2003, 3.0), (2004, 4.0), (2005, 4.5),
                                 (2006, 5.0)]
