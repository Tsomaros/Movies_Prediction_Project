"""Explanations: drivers, feature groups, sentences and comparable films, on small synthetic models and data."""

import copy
import json
import math
import sqlite3

import numpy as np
import pandas as pd
import pytest

from ml.explain.comparables import Index, similarity
from ml.explain.drivers import (EXPECTED, contributions, effect, group_contributions, main_feature, strength,
                                top_drivers)
from ml.explain.groups import GROUPS, feature_groups, group_of
from ml.explain.sentences import explain, sentence
from ml.features.contract import GENRES as GENRE_NAMES
from ml.features.history import BUDGET_FEATURES
from ml.models.chain import with_budget
from ml.models.train import TARGETS, model_features
from tests.test_models import (budget_model, budget_rows, chain, chain_rows, revenue_model,  # noqa: F401 (fixtures)
                               revenue_rows, score_model, score_rows)
from tests.test_eval import db  # noqa: F401 (fixture: a small movies.db with a features table)


@pytest.mark.parametrize("model_name, rows", [
    ("revenue_model", revenue_rows), ("budget_model", budget_rows), ("score_model", score_rows)])
def test_contributions_add_up_to_the_middle(request, model_name, rows):
    model = request.getfixturevalue(model_name)
    df = rows(80, seed=3)
    c = contributions(model, df)
    assert list(c.columns) == [*model.features, EXPECTED]
    assert c[EXPECTED].nunique() == 1  # one starting point: the typical film
    assert np.allclose(c.sum(axis=1), model.predict(df)["p50"])
    assert np.allclose(c.sum(axis=1), model.predict(df, q=0.7)["p50"])  # the correction never moves the middle


def test_contributions_follow_the_middle_when_quantiles_cross(budget_model):
    crossed = copy.copy(budget_model)
    crossed.models = {**budget_model.models, "p10": budget_model.models["p90"]}  # p10 now above the middle
    df = budget_rows(80, seed=3)
    shown = crossed.predict(df)["p50"]
    own = budget_model.models["p50"].predict(df[budget_model.features])
    assert not np.allclose(shown, own)  # sorting moved the middle
    assert np.allclose(contributions(crossed, df).sum(axis=1), shown)


def test_estimated_mode_contributions_use_the_estimated_budget(chain, revenue_model, budget_model):
    rows = chain_rows(60)
    p = chain.predict_revenue(rows)
    c = contributions(revenue_model, with_budget(rows, p.attrs["log_budget"]))
    assert np.allclose(c.sum(axis=1), p["p50"])


def test_groups_sum_their_features_and_keep_the_total(revenue_model):
    df = revenue_rows(40, seed=4)
    c = contributions(revenue_model, df)
    groups = {"log_budget": "Budget", "director_revenue": "Director", "franchise_revenue": "Franchise",
              "runtime": "Runtime", "genre_action": "Genre"}
    g = group_contributions(c, groups)
    assert list(g.columns) == ["Budget", "Director", "Franchise", "Runtime", "Genre", EXPECTED]
    merged = group_contributions(c, {**groups, "franchise_revenue": "Director"})
    assert np.allclose(merged["Director"], c["director_revenue"] + c["franchise_revenue"])
    assert np.allclose(merged.sum(axis=1), c.sum(axis=1))


def test_a_feature_without_a_group_is_refused(revenue_model):
    c = contributions(revenue_model, revenue_rows(10))
    with pytest.raises(KeyError, match="genre_action"):
        group_contributions(c, {f: "Group" for f in revenue_model.features if f != "genre_action"})


@pytest.mark.parametrize("target, c, label", [
    ("revenue", math.log(1.5), "strong"),
    ("revenue", -math.log(1.5), "strong"),  # -33% is as strong as +50%
    ("revenue", math.log(1.49), "moderate"),
    ("budget", math.log(1.2), "moderate"),
    ("budget", -math.log(1.19), "slight"),
    ("score", 0.3, "strong"),
    ("score", -0.29, "moderate"),
    ("score", 0.1, "moderate"),
    ("score", 0.09, "slight"),
])
def test_strength_cutoffs(target, c, label):
    assert strength(target, c) == label


def test_effect_is_a_percentage_for_money_and_points_for_score():
    assert effect("revenue", math.log(1.25)) == pytest.approx(0.25)
    assert effect("budget", -math.log(1.25)) == pytest.approx(-0.20)
    assert effect("score", -0.4) == -0.4


def test_top_drivers_are_the_largest_groups_largest_first():
    row = pd.Series({"Budget": 0.9, "Genre": -0.4, "Cast": 0.05, "Studio": 0.0, "Timing": -1.2,
                     "Runtime": 0.2, "Director": 0.3, EXPECTED: 17.0})
    top = top_drivers("revenue", row, n=5, estimated=("Budget",))
    assert [d["group"] for d in top] == ["Timing", "Budget", "Genre", "Director", "Runtime"]
    assert [d["direction"] for d in top] == ["down", "up", "down", "up", "up"]
    assert [d["strength"] for d in top] == ["strong", "strong", "moderate", "moderate", "moderate"]
    assert [d["estimated"] for d in top] == [False, True, False, False, False]
    assert top[1]["effect"] == pytest.approx(math.expm1(0.9))
    everything = top_drivers("revenue", row, n=20)
    assert "Studio" not in [d["group"] for d in everything]  # zero contributions are not drivers
    assert EXPECTED not in [d["group"] for d in everything]


# ---------------------------------------------------------------- feature groups


@pytest.mark.parametrize("target", TARGETS)
def test_every_feature_the_app_models_use_has_a_group(target):
    groups = feature_groups()
    assert [f for f in model_features(target, ("synopsis",)) if f not in groups] == []
    assert set(groups.values()) <= set(GROUPS)


def test_every_group_is_used_and_labels_are_plain():
    assert set(feature_groups().values()) == set(GROUPS)
    assert all("_" not in label and label[0].isupper() for label in GROUPS.values())


def test_budget_track_record_joins_the_group_it_describes():
    groups = feature_groups()
    assert {f: groups[f] for f in BUDGET_FEATURES} == {
        "director_budget": "director", "actors_budget_max": "cast", "actors_budget_mean": "cast",
        "actors_budget_min": "cast", "company_budget": "studio", "franchise_budget": "franchise"}
    assert groups["director_is_new"] == "director" and groups["actors_score_min"] == "cast"
    assert groups["covid_period"] == "timing" and groups["log_budget"] == "budget"


def test_synopsis_numbers_have_no_group_so_a_synopsis_model_is_refused(revenue_model):
    groups = feature_groups()
    assert not [f for f in groups if f.startswith("synopsis_") or f == "has_synopsis"]
    assert group_of("synopsis_03", "synopsis (MiniLM + PCA)") is None
    with pytest.raises(ValueError, match="no group"):
        group_of("new_feature", "a source nobody mapped")
    c = contributions(revenue_model, revenue_rows(5)).assign(synopsis_00=0.1)
    with pytest.raises(KeyError, match="synopsis_00"):
        group_contributions(c, groups)


# ---------------------------------------------------------------- plain-English sentences

FORM = {
    "genres": ["Drama", "Romance"], "release_year": 2026, "release_month": 12, "runtime": 118, "language": "fr",
    "certification": "R", "director": {"id": 7, "name": None},
    "actors": [{"id": None, "name": "Ana Lead"}, {"id": 3, "name": None}],
    "themes": ["love and marriage", "family", "friendship", "coming of age and school"],
    "companies": [{"id": 33, "name": None}], "countries": ["FR", "BE"], "franchise": None,
    "synopsis": None, "budget": 12_000_000.0,
}
FEATURES = {"log_budget": math.log(12_000_000), "director_n_films": 1, "director_is_new": 0, "actors_is_new_min": 0,
            "is_franchise": 0, "franchise_earlier_films": 0, "holiday": 1, "summer": 0, "covid_period": 0}
NAMES = {"director": "Jo Director", "actors": [None, "Ben Second"], "companies": ["Universal Pictures"]}


def driver(group, direction="up", strength_="moderate", estimated=False):
    return {"group": group, "direction": direction, "strength": strength_, "estimated": estimated}


def test_every_group_has_a_sentence_without_raw_feature_names():
    raw_names = {n for n in feature_groups() if "_" in n}  # one-word names (runtime, holiday) are plain words
    for group in GROUPS:
        s = sentence("revenue", driver(group), FORM, FEATURES, NAMES)
        assert s["label"] == GROUPS[group] and s["value"] and s["text"].endswith(" the expected revenue.")
        assert "_" not in s["text"] and not [n for n in raw_names if n in s["text"]]


@pytest.mark.parametrize("group, direction, strength_, text", [
    ("timing", "up", "strong", "Releasing in December (holiday season) strongly raises the expected revenue."),
    ("budget", "down", "slight", "A budget of $12M slightly lowers the expected revenue."),
    ("director", "up", "moderate", "Jo Director's 1 earlier film raises the expected revenue."),
    ("cast", "down", "strong", "The cast's earlier films (led by Ana Lead) strongly lower the expected revenue."),
    ("genre", "up", "slight", "The genres Drama and Romance slightly raise the expected revenue."),
    ("themes", "up", "moderate",
     'The themes "love and marriage", "family" and 2 more raise the expected revenue.'),
    ("studio", "up", "moderate", "Universal Pictures as the studio raises the expected revenue."),
    ("certification", "down", "moderate", "An R rating lowers the expected revenue."),
    ("language", "down", "moderate", "French as the original language lowers the expected revenue."),
    ("country", "up", "slight", "Producing in France and BE slightly raises the expected revenue."),
    ("franchise", "down", "slight", "Not being part of a franchise slightly lowers the expected revenue."),
    ("runtime", "up", "moderate", "A runtime of 118 minutes raises the expected revenue."),
])
def test_sentences_use_the_creators_values(group, direction, strength_, text):
    assert sentence("revenue", driver(group, direction, strength_), FORM, FEATURES, NAMES)["text"] == text


def test_estimated_budget_and_other_targets_are_worded_as_such():
    s = sentence("revenue", driver("budget", estimated=True), FORM, FEATURES)
    assert s["text"] == "The estimated budget of about $12M raises the expected revenue." and s["estimated"]
    assert sentence("score", driver("runtime"), FORM, FEATURES)["text"].endswith("the expected audience score.")
    assert sentence("budget", driver("runtime"), FORM, FEATURES)["text"].endswith("the expected budget.")


def test_new_people_franchises_and_missing_values():
    new = {**FEATURES, "director_is_new": 1, "actors_is_new_min": 1, "is_franchise": 1, "franchise_earlier_films": 2}
    form = {**FORM, "director": {"id": None, "name": "New Person"}, "franchise": {"id": 9, "name": None},
            "companies": [], "countries": [], "certification": "unrated/unknown"}
    say = lambda group, f=new, n=None: sentence("budget", driver(group, "down"), form, f, n)["text"]
    assert say("director") == "New Person, with no earlier films as director in our data, lowers the expected budget."
    assert say("cast") == "A cast with no earlier films in our data lowers the expected budget."
    assert say("franchise", n={"franchise": "Space Saga"}) == \
        "Being part of Space Saga (2 earlier films) lowers the expected budget."
    assert say("franchise", f=FEATURES, n={"franchise": "Space Saga"}) == \
        "Starting Space Saga as a new franchise lowers the expected budget."
    assert say("studio") == "Having no named studio lowers the expected budget."
    assert say("country") == "Having no production country given lowers the expected budget."
    assert say("certification") == "Having no US rating lowers the expected budget."
    assert say("director", n=None).startswith("New Person")  # a typed name needs no lookup
    ids_only = {**FORM, "director": {"id": 7, "name": None}}
    assert sentence("budget", driver("director"), ids_only, FEATURES)["text"].startswith("The director's 1 earlier film")


def test_release_timing_is_worded_by_its_main_part():
    year = {**driver("timing", "down", "strong"), "main_feature": "year"}
    assert sentence("revenue", year, FORM, FEATURES)["text"] ==         "Releasing in 2026 (recent films earn less in our data) strongly lowers the expected revenue."
    assert sentence("score", year, FORM, FEATURES)["text"] == "Releasing in 2026 strongly lowers the expected audience score."
    month = {**driver("timing"), "main_feature": "month"}
    assert sentence("budget", month, FORM, FEATURES)["text"] ==         "Releasing in December (holiday season) raises the expected budget."


def test_main_feature_is_the_largest_inside_the_group():
    row = pd.Series({"year": -0.2, "month": 0.05, "holiday": 0.1, "runtime": 0.9, EXPECTED: 17.0})
    groups = {"year": "timing", "month": "timing", "holiday": "timing", "runtime": "runtime"}
    assert main_feature(row, "timing", groups) == "year"
    assert main_feature(row, "runtime", groups) == "runtime"
    assert main_feature(row, "studio", groups) is None


def test_explain_splits_up_and_down_keeping_the_order():
    drivers = [driver("budget", "up", "strong"), driver("genre", "down"), driver("runtime", "up", "slight")]
    e = explain("revenue", drivers, FORM, FEATURES, NAMES)
    assert [s["group"] for s in e["up"]] == ["budget", "runtime"] and [s["group"] for s in e["down"]] == ["genre"]


# ---------------------------------------------------------------- comparable films

DAY = 18_000  # the planned film's date (days since 1970-01-01)


def small_index(n=8, **overrides):
    """n films: film 0 is identical to QUERY; similarity falls with the film number."""
    rng = np.random.default_rng(0)
    vectors = np.zeros((n, 4), dtype=np.float32)
    vectors[:, 0] = np.linspace(1.0, 0.2, n)
    vectors[:, 1] = np.sqrt(1 - vectors[:, 0] ** 2)
    genres = np.zeros((n, len(GENRE_NAMES)), dtype=bool)
    genres[:, GENRE_NAMES.index("Drama")] = True
    genres[n // 2:, GENRE_NAMES.index("Horror")] = True
    themes = np.zeros((n, 2), dtype=bool)
    themes[:, 0] = True
    fields_ = dict(
        ids=np.arange(1, n + 1), titles=np.array([f"Film {i}" for i in range(n)]), years=np.full(n, 2015),
        days=np.full(n, DAY - 100), posters=np.array(["/p.jpg"] + [""] * (n - 1)),
        budget=np.full(n, 10_000_000.0), revenue=np.full(n, 30_000_000.0), score=rng.uniform(5, 8, n),
        languages=np.array(["en"] * (n - 1) + ["fr"]),
        genres=genres, themes=themes, theme_names=np.array(["family", "heist"]), vectors=vectors)
    return Index(**{**fields_, **overrides})


QUERY = dict(genres=["Drama"], themes=["family"], language="en", vector=np.array([1.0, 0, 0, 0]), year=2015,
             log_budget=math.log(10_000_000))


def test_an_identical_film_has_similarity_one_with_or_without_a_synopsis():
    index = small_index()
    assert similarity(index, **QUERY)[0] == pytest.approx(1.0)
    assert similarity(index, **{**QUERY, "vector": None})[0] == pytest.approx(1.0)
    sim = similarity(index, **QUERY)
    assert (np.diff(sim) <= 1e-9).all()  # built so that similarity falls with the film number


def test_comparables_never_come_from_the_future():
    days = np.full(8, DAY - 100)
    days[0], days[1], days[2] = DAY, DAY + 1, DAY - 1  # the planned date itself counts as the future
    got = small_index(days=days).query(**QUERY, as_of=DAY)
    assert [f["id"] for f in got] == [3, 4, 5, 6, 7]
    assert small_index(days=np.full(8, DAY)).query(**QUERY, as_of=DAY) == []


def test_films_with_money_come_first_and_others_only_fill_in():
    nan = np.nan
    budget = np.array([nan, 1e7, nan, 1e7, nan, nan, nan, nan])
    revenue = np.array([nan, nan, nan, nan, 5e7, nan, nan, nan])
    got = small_index(budget=budget, revenue=revenue).query(**QUERY, as_of=DAY)
    assert [f["id"] for f in got] == [2, 4, 5, 1, 3]  # three with money, then the two most similar without
    assert got[0]["budget"] == 1e7 and got[0]["revenue"] is None and got[3]["budget"] is None


def test_unknown_budget_counts_as_half_close():
    budget = np.full(8, 10_000_000.0)
    budget[0] = np.nan
    index = small_index(budget=budget)
    only_budget = {"genres": [], "themes": [], "language": None, "vector": None, "year": 1900,
                   "log_budget": math.log(1e7)}
    sim = similarity(index, **only_budget)  # genres and themes give 0, era almost 0
    era = math.exp(-115 / 10)
    weights = 0.3 + 0.2 + 0.1 + 0.2  # no synopsis and no language: genres, themes, era, budget
    assert sim[0] == pytest.approx((0.2 * 0.5 + 0.1 * era) / weights)
    assert sim[1] == pytest.approx((0.2 * 1.0 + 0.1 * era) / weights)


def test_the_same_language_counts():
    index = small_index()
    sim_en, sim_fr = similarity(index, **QUERY), similarity(index, **{**QUERY, "language": "fr"})
    assert sim_en[0] - sim_fr[0] == pytest.approx(0.1 / 1.2)  # all six parts: weights add up to 1.2
    assert sim_fr[-1] - sim_en[-1] == pytest.approx(0.1 / 1.2)  # the last film is French


def test_results_are_json_ready_and_the_index_round_trips(tmp_path):
    index = small_index()
    got = index.query(**QUERY, as_of=DAY, n=2)
    assert json.loads(json.dumps(got)) == got
    assert got[0] == {"id": 1, "title": "Film 0", "year": 2015, "poster_path": "/p.jpg", "budget": 1e7,
                      "revenue": 3e7, "score": pytest.approx(index.score[0]), "similarity": 1.0,
                      "why": ["Similar story", "Same genres", "Same themes"]}
    assert got[1]["poster_path"] is None
    index.save(tmp_path / "c.npz")
    back = Index.load(tmp_path / "c.npz")
    assert back.vectors.dtype == np.float32 and np.allclose(back.vectors, index.vectors, atol=1e-3)
    assert back.query(**QUERY, as_of=DAY) == index.query(**QUERY, as_of=DAY)


def test_why_names_the_shared_genres_and_themes_and_the_close_parts():
    index = small_index()
    first = index.query(**{**QUERY, "genres": ["Drama", "Comedy"], "themes": ["family", "heist"]}, as_of=DAY, n=1)[0]
    assert first["why"] == ["Similar story", "Similar budget", "Also Drama"]  # half the genres: 0.3 x 0.5 < 0.2
    # no synopsis, another era, a French film, an unknown budget: nothing close but the language
    nan_budget = small_index(budget=np.full(8, np.nan))
    got = nan_budget.query(genres=["Western"], themes=[], language="fr", vector=None, year=1960,
                           log_budget=math.log(1e7), as_of=DAY)
    assert {tuple(f["why"]) for f in got} <= {(), ("Same language",)} and ("Same language",) in {tuple(f["why"]) for f in got}
    assert all(len(f["why"]) <= 3 for f in index.query(**QUERY, as_of=DAY))


def test_index_builds_from_the_database(db):
    con = sqlite3.connect(db / "movies.db")
    index = Index.build(con, cache=db / "emb.npz", theme_names=["heist"])
    expected = con.execute("SELECT COUNT(*) FROM movies WHERE score_ok").fetchone()[0]
    assert len(index) == expected > 0
    assert index.genres.shape == (expected, len(GENRE_NAMES)) and index.themes.shape == (expected, 1)
    assert (np.abs(np.linalg.norm(index.vectors, axis=1) - 1) < 1e-2).all()  # every test film has an overview
    first = con.execute("SELECT title, year FROM movies WHERE id = ?", (int(index.ids[0]),)).fetchone()
    assert (str(index.titles[0]), int(index.years[0])) == first
