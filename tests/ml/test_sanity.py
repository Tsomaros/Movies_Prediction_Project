"""Logic checks on the app's real models: predict() must stay within the bounds of common sense.

Skipped, like tests/ml/test_golden.py, when the gitignored database, models or comparables index are
missing. Unlike the golden snapshot these tests check rules, not numbers:
- bounds: ordered, finite, positive ranges; score within 0-10; JSON-ready output (also on 60 real films);
- a higher given budget never lowers any part of the revenue range;
- the synopsis, which no model uses, changes nothing but the comparables, and the order of genres,
  themes and actors changes nothing;
- the two revenue modes agree: "estimated" equals "given" at the estimated budget, only wider;
- edge-of-form inputs work, and out-of-form inputs raise InvalidForm;
- matched pairs move the way film-economics studies report (budget, franchise, track record, studio);
- the creator's date (1st of the month) changes the training features very little.
"""

import json
import math
import sqlite3
from contextlib import closing

import numpy as np
import pandas as pd
import pytest

from ml.data.build_db import DB_FILE
from ml.features.build import FilmForms, api_as_of, build_features, film_to_form
from ml.features.contract import GENRES
from ml.features.history import day_number
from ml.models.train import ARTIFACTS_DIR, QUANTILE_KEYS, TARGETS, load_model
from ml.predict import InvalidForm, Predictor
from tests.ml.test_golden import FORMS, NEEDED

pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not all(p.exists() for p in NEEDED),
                                 reason="needs data/movies.db, the all-data models and the comparables index")]
BUDGETS = np.geomspace(100_000, 500_000_000, 12)
N_FILMS = 60  # real 2016-18 films run through predict() for the bounds check


@pytest.fixture(scope="module")
def predictor():
    return Predictor.load()


@pytest.fixture(scope="module")
def films(predictor):
    with closing(sqlite3.connect(DB_FILE)) as con:
        return FilmForms.from_db(con)


def ranges(out):
    return {t: (out[t]["low"], out[t]["middle"], out[t]["high"]) for t in TARGETS}


def without(form, *keys):
    return {k: v for k, v in form.items() if k not in keys}


def check_bounds(out):
    assert json.loads(json.dumps(out)) == out
    for t, (low, middle, high) in ranges(out).items():
        assert all(math.isfinite(v) for v in (low, middle, high)), t
        assert low <= middle <= high, t
        assert low > 0 if t != "score" else 0 <= low and high <= 10, t


# ---------------------------------------------------------------- bounds


@pytest.mark.parametrize("name", FORMS)
def test_golden_forms_stay_within_bounds(predictor, name):
    check_bounds(predictor.predict(FORMS[name]))


def test_real_films_stay_within_bounds(predictor, films):
    """60 real 2016-18 films written as forms; some have no budget, so both revenue modes are covered."""
    ids = films.movies.index[films.movies["split"] == "validation"].to_series().sample(N_FILMS, random_state=1)
    modes = set()
    for movie_id in ids:
        form = film_to_form(movie_id, films, predictor.ctx)
        form["actors"] = (form["actors"] + [f"Newcomer {i}" for i in range(5)])[:10]  # the form needs 5-10
        form["themes"] = form["themes"][:5] or ["family"]
        form["genres"] = form["genres"][:5] or ["Drama"]
        form["companies"], form["countries"] = form["companies"][:5], form["countries"][:5]
        form["runtime"] = min(max(form["runtime"] or 100, 40), 300)
        form["language"] = form["language"] or "en"
        form["director"] = form["director"] or "Unknown Director"
        if form["budget"] is not None and not 1_000 <= form["budget"] <= 1e9:
            form["budget"] = None
        out = predictor.predict(form)
        check_bounds(out)
        modes.add(out["revenue"]["mode"])
    assert modes == {"given", "estimated"}


@pytest.mark.parametrize("target", ["budget", "score"])
def test_no_range_is_narrower_than_its_correction(predictor, target):
    """Every app range is at least 2q wide, even where the quantile models cross (about 3% of budget
    films): the crossed values are sorted first, then widened by q on both sides."""
    from ml.eval.splits import load
    model = predictor.chain.budget if target == "budget" else predictor.score
    p = model.predict(load(target, "validation"))
    if target == "score":  # the 0-10 clip may cut a range at either end
        p = p[(p["p10"] > 0) & (p["p90"] < 10)]
    assert (p["p90"] - p["p10"] >= 2 * model.q - 1e-9).all()


# ---------------------------------------------------------------- monotone budget


@pytest.mark.parametrize("name", FORMS)
def test_a_higher_budget_never_lowers_the_revenue_range(predictor, name):
    rows = np.array([ranges(predictor.predict(dict(FORMS[name], budget=float(b))))["revenue"] for b in BUDGETS])
    assert (np.diff(rows, axis=0) >= -1e-6 * rows[1:]).all()
    assert rows[-1, 1] > 10 * rows[0, 1]  # and it does rise over the grid


# ---------------------------------------------------------------- invariance


@pytest.mark.parametrize("name", FORMS)
def test_the_synopsis_changes_only_the_comparables(predictor, name):
    form = FORMS[name]
    base = predictor.predict(form)
    other = predictor.predict(dict(form, synopsis="Robots fight a galactic empire with lasers in a space opera."))
    none = predictor.predict(without(form, "synopsis"))
    assert ranges(base) == ranges(other) == ranges(none)
    assert base["drivers"] == other["drivers"] == none["drivers"]


@pytest.mark.parametrize("name", FORMS)
def test_the_order_of_genres_themes_and_actors_does_not_matter(predictor, name):
    form = FORMS[name]
    shuffled = dict(form, genres=form["genres"][::-1], themes=form["themes"][::-1], actors=form["actors"][::-1])
    assert ranges(predictor.predict(shuffled)) == ranges(predictor.predict(form))


# ---------------------------------------------------------------- the two revenue modes


@pytest.mark.parametrize("name", FORMS)
def test_estimated_mode_is_given_mode_at_the_estimated_budget_but_wider(predictor, name):
    estimated = predictor.predict(without(FORMS[name], "budget"))
    given = predictor.predict(dict(FORMS[name], budget=estimated["revenue"]["budget_used"]))
    assert estimated["revenue"]["mode"] == "estimated" and given["revenue"]["mode"] == "given"
    assert estimated["revenue"]["middle"] == pytest.approx(given["revenue"]["middle"], rel=1e-9)
    assert estimated["revenue"]["low"] < given["revenue"]["low"]  # its correction is larger (0.50 vs 0.40 log)
    assert estimated["revenue"]["high"] > given["revenue"]["high"]
    assert ranges(estimated)["score"] == ranges(given)["score"]  # score never sees the budget


# ---------------------------------------------------------------- edges of the form


EDGES = {
    "budget $1K": dict(FORMS["unknown_cast"], budget=1_000),
    "budget $1B": dict(FORMS["franchise_blockbuster"], budget=1_000_000_000),
    "runtime 40": dict(FORMS["small_drama"], runtime=40),
    "runtime 300": dict(FORMS["small_drama"], runtime=300),
    "year 1960": dict(FORMS["small_drama"], release_year=1960),
    "year 2035": dict(FORMS["small_drama"], release_year=2035),
    "five genres": dict(FORMS["small_drama"], genres=["Drama", "Comedy", "Horror", "Western", "Animation"]),
    "ten actors": dict(FORMS["small_drama"], actors=FORMS["small_drama"]["actors"] + ["A", "B", "C", "D", "E"]),
    "unknown language": dict(FORMS["small_drama"], language="xx"),
    "unrated": dict(FORMS["small_drama"], certification="unrated/unknown"),
}
OUTSIDE = {
    "every genre": ("genres", dict(FORMS["small_drama"], genres=list(GENRES))),
    "runtime 1": ("runtime", dict(FORMS["small_drama"], runtime=1)),
    "budget $10B": ("budget", dict(FORMS["small_drama"], budget=1e10)),
    "negative budget": ("budget", dict(FORMS["small_drama"], budget=-5)),
    "year 2040": ("release_year", dict(FORMS["small_drama"], release_year=2040)),
    "four actors": ("actors", dict(FORMS["small_drama"], actors=FORMS["small_drama"]["actors"][:4])),
    "no themes": ("themes", without(FORMS["small_drama"], "themes")),
}


@pytest.mark.parametrize("name", EDGES)
def test_edge_of_form_inputs_still_give_sensible_ranges(predictor, name):
    out = predictor.predict(EDGES[name])
    check_bounds(out)
    codes = {w["code"] for w in out["warnings"]}
    assert ("future_release" in codes) == (EDGES[name]["release_year"] > 2025)
    assert ("big_budget" in codes) == (out["revenue"]["budget_used"] >= 150_000_000)


@pytest.mark.parametrize("name", OUTSIDE)
def test_out_of_form_inputs_are_rejected_with_the_field_named(predictor, name):
    field, form = OUTSIDE[name]
    with pytest.raises(InvalidForm) as e:
        predictor.predict(form)
    assert field in e.value.errors


# ---------------------------------------------------------------- directions found in film-economics studies


def middle(predictor, form, target="revenue"):
    return predictor.predict(form)[target]["middle"]


def test_a_bigger_budget_means_more_revenue(predictor):
    form = dict(FORMS["small_drama"], budget=10_000_000)
    assert middle(predictor, dict(form, budget=100_000_000)) > 2 * middle(predictor, form)


def test_a_sequel_earns_more_than_the_same_film_without_its_franchise(predictor):
    form = FORMS["franchise_blockbuster"]
    assert middle(predictor, form) > middle(predictor, without(form, "franchise"))


def test_a_known_director_beats_a_first_time_director(predictor):
    form = dict(FORMS["small_drama"], budget=20_000_000)
    assert middle(predictor, form) > middle(predictor, dict(form, director="Nobody We Know"))


def test_a_major_studio_beats_a_small_one_and_a_small_one_beats_none(predictor):
    form = dict(FORMS["small_drama"], budget=20_000_000)  # A24
    assert middle(predictor, dict(form, companies=[33])) > middle(predictor, form)  # Universal
    assert middle(predictor, form) > middle(predictor, without(form, "companies"))


def test_summer_and_holiday_releases_earn_at_least_as_much_as_september(predictor):
    form = dict(FORMS["small_drama"], budget=20_000_000)
    september = middle(predictor, dict(form, release_month=9))
    assert middle(predictor, dict(form, release_month=7)) >= september
    assert middle(predictor, dict(form, release_month=12)) >= september


# ---------------------------------------------------------------- comparables


def test_a_film_judged_at_its_own_release_never_finds_itself(predictor, films):
    ids = films.movies.index[(films.movies["split"] == "validation")].to_series().sample(30, random_state=2)
    for movie_id in ids:
        m = films.movies.loc[movie_id]
        found = predictor.index.query(films.genres.get(movie_id, []), [], m["original_language"], None,
                                      int(m["year"]), None, day_number(m["release_date"]))
        assert movie_id not in [f["id"] for f in found]
        days = dict(zip(predictor.index.ids.tolist(), predictor.index.days.tolist()))
        assert all(days[f["id"]] < day_number(m["release_date"]) for f in found)


# ---------------------------------------------------------------- training date vs the creator's date


@pytest.mark.skipif(not all((ARTIFACTS_DIR / f"{t}_{k}.joblib").exists() for t in TARGETS for k in QUANTILE_KEYS),
                    reason="needs the <=2015 models from make train")
def test_judging_at_the_first_of_the_month_barely_moves_the_middle(predictor, films):
    """Training judges a film at its release day, the app at the 1st of its month: the few days between
    may only change the track record a little."""
    models = {t: load_model(t) for t in TARGETS}
    ids = films.movies.index[(films.movies["split"] == "validation")].to_series().sample(200, random_state=3)
    shift = {t: [] for t in TARGETS}
    for movie_id in ids:
        form = film_to_form(movie_id, films, predictor.ctx)
        day = day_number(films.movies.at[movie_id, "release_date"])
        rows = [pd.DataFrame([build_features(form, d, predictor.ctx)], dtype=float) for d in (day, api_as_of(form))]
        for t, m in models.items():
            shift[t].append(abs(float(m.predict(rows[1])["p50"].iloc[0] - m.predict(rows[0])["p50"].iloc[0])))
    for t, s in shift.items():
        assert np.median(s) < 0.01 and np.quantile(s, 0.9) < 0.1, t
