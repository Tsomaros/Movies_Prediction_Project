"""Tests for ml/features: the form contract, leak-safe track record (people, companies, franchises,
budgets), forbidden inputs, and the training and API paths giving identical features."""

import hashlib
import json
import math
import sqlite3

import numpy as np
import pandas as pd
import pytest

import ml.data.build_db as build_db
from ml.features import contract
from ml.features.basic import Franchises, fit_vocab
from ml.features.build import FeatureContext, FilmForms, build_features, build_table, feature_list, film_to_form
from ml.features.history import SHRINK_FILMS, Companies, History, day_number
from ml.features.synopsis import FEATURE_NAMES as SYNOPSIS_FEATURES
from ml.features.synopsis import synopsis_features
from ml.features.text import EMBED_DIM, model_available
from tests.factories import TEST_CPI, film

POST_RELEASE = ("popularity", "vote_count", "vote_average", "revenue")


# ---------------------------------------------------------------- contract


def good_form(**overrides) -> dict:
    form = {
        "genres": ["Crime", "Thriller"], "release_year": 2027, "release_month": 7, "runtime": 118,
        "language": "en", "certification": "R", "director": "A Director",
        "actors": [f"Actor {i}" for i in range(5)], "themes": ["heist"],
    }
    return {**form, **overrides}


def test_validate_accepts_a_form_without_optional_fields():
    clean, errors = contract.validate(good_form(), themes=["heist"])
    assert errors == {}
    assert clean["companies"] == [] and clean["countries"] == []
    assert clean["franchise"] is None and clean["synopsis"] is None and clean["budget"] is None
    assert clean["director"] == {"id": None, "name": "A Director"}


@pytest.mark.parametrize("field, value", [
    ("genres", ["Cooking"]), ("release_year", 1950), ("release_month", 13), ("runtime", 118.5),
    ("language", "English"), ("certification", "NR"), ("director", {"name": "  "}),
    ("actors", ["Only", "Four", "Actors", "Here"]), ("actors", [f"A{i}" for i in range(11)]),
    ("themes", ["not a theme"]), ("countries", ["usa"]), ("budget", 50), ("synopsis", "x" * 2001),
])
def test_validate_rejects_bad_values(field, value):
    _, errors = contract.validate(good_form(**{field: value}), themes=["heist"])
    assert field in errors


def test_validate_rejects_post_release_fields_and_missing_required_ones():
    _, errors = contract.validate({"popularity": 99, "vote_count": 5000})
    assert errors["popularity"] == errors["vote_count"] == "unknown field"
    assert {f.name for f in contract.FIELDS if f.required} <= set(errors)


def test_contract_has_no_post_release_inputs():
    assert not {f.name for f in contract.FIELDS} & set(POST_RELEASE)


def test_certification_category_merges_nr_and_missing():
    assert [contract.certification_category(c) for c in ["PG-13", "NR", None, "TV-MA"]] == \
        ["PG-13", contract.UNRATED, contract.UNRATED, contract.UNRATED]


# ---------------------------------------------------------------- track record (hand-computed)


FILM_COLUMNS = ["id", "release_date", "log_revenue", "score", "collection_id", "log_budget"]


def film_frame(films: list[tuple]) -> pd.DataFrame:
    """(id, date, log_revenue, score, collection_id[, log_budget]) tuples; log_budget defaults to NaN."""
    return pd.DataFrame([t + (math.nan,) * (len(FILM_COLUMNS) - len(t)) for t in films], columns=FILM_COLUMNS)


def history(films: list[tuple], credits: list[tuple]) -> History:
    """films: (id, date, log_revenue, score, collection_id[, log_budget]); credits: (person_id, movie_id, role)."""
    f = film_frame(films)
    c = pd.DataFrame(credits, columns=["person_id", "movie_id", "role"])
    people = pd.DataFrame({"id": [1, 2], "name": ["Ann Director", "Bob Other"]})
    return History(f, c, people)


TARGET = day_number("2003-01-01")
BASE_FILMS = [
    (1, "2000-01-01", 10.0, 5.0, None),  # Ann
    (2, "2001-01-01", 12.0, 7.0, None),  # Ann
    (3, "2002-01-01", 20.0, 9.0, None),  # Bob
]
BASE_CREDITS = [(1, 1, "director"), (1, 2, "director"), (2, 3, "director")]


def test_shrinkage_matches_a_hand_computed_value():
    p = history(BASE_FILMS, BASE_CREDITS).person(1, "director", TARGET)
    # Typical film at the target date: median(10, 12, 20) = 12 and median(5, 7, 9) = 7.
    # Ann: 2 films, median 11 and 6 -> (2 x 11 + 4 x 12) / 6 and (2 x 6 + 4 x 7) / 6.
    assert SHRINK_FILMS == 4
    assert p["n_films"] == 2 and p["is_new"] == 0
    assert p["revenue"] == pytest.approx((2 * 11 + 4 * 12) / 6)
    assert p["score"] == pytest.approx((2 * 6 + 4 * 7) / 6)
    assert p["years_active"] == pytest.approx((TARGET - day_number("2000-01-01")) / 365.25)


def test_young_films_count_but_do_not_move_the_medians():
    young = (4, "2002-10-01", 30.0, 1.0, None)  # 92 days before the target: still earning
    base = history(BASE_FILMS, BASE_CREDITS).person(1, "director", TARGET)
    p = history(BASE_FILMS + [young], BASE_CREDITS + [(1, 4, "director")]).person(1, "director", TARGET)
    assert p["n_films"] == 3
    assert p["revenue"] == pytest.approx(base["revenue"]) and p["score"] == pytest.approx(base["score"])


def test_films_on_or_after_the_date_never_count():
    same_day = (5, "2003-01-01", 1000.0, 0.0, None)
    later = (6, "2005-01-01", -1000.0, 10.0, None)
    extra = [(1, 5, "director"), (1, 6, "director"), (2, 6, "director")]
    base = history(BASE_FILMS, BASE_CREDITS)
    more = history(BASE_FILMS + [same_day, later], BASE_CREDITS + extra)
    for pid in (1, 2):
        assert more.person(pid, "director", TARGET) == pytest.approx(base.person(pid, "director", TARGET), nan_ok=True)
    assert more.priors(TARGET) == base.priors(TARGET)


def test_unknown_people_get_neutral_values():
    h = history(BASE_FILMS, BASE_CREDITS)
    assert h.resolve({"id": None, "name": "Jane Newcomer"}, "director") is None
    assert h.resolve({"id": 999, "name": None}, "director") is None
    assert h.resolve({"id": None, "name": "  ann DIRECTOR "}, "director") == 1
    typical_revenue, typical_score = h.priors(TARGET)
    new = h.person(None, "director", TARGET)
    assert new == {"n_films": 0, "years_active": 0.0, "revenue": typical_revenue, "score": typical_score,
                   "budget": pytest.approx(math.nan, nan_ok=True), "franchise_films": 0, "is_new": 1}  # no budgets
    actors = h.actor_features([], TARGET)  # every slot empty -> five new actors
    assert actors["actors_is_new_min"] == 1 and actors["actors_n_films_max"] == 0


def test_franchise_experience_counts_only_earlier_sequels():
    films = [(1, "2000-01-01", 10.0, 5.0, 77), (2, "2002-01-01", 12.0, 7.0, 77)]  # first entry, then a sequel
    h = history(films, [(1, 1, "director"), (1, 2, "director")])
    assert h.person(1, "director", day_number("2001-06-01"))["franchise_films"] == 0  # first entry: no
    assert h.person(1, "director", TARGET)["franchise_films"] == 1


# ---------------------------------------------------------------- budget track record (hand-computed)

BUDGET_FILMS = [  # log budgets 16, 17 (Ann) and 19 (Bob)
    (1, "2000-01-01", 10.0, 5.0, None, 16.0),
    (2, "2002-10-01", 12.0, 7.0, None, 17.0),  # 92 days before the target: its budget already counts
    (3, "2002-01-01", 20.0, 9.0, None, 19.0),
]


def test_budget_shrinkage_matches_a_hand_computed_value():
    h = history(BUDGET_FILMS, BASE_CREDITS)
    # Typical budget at the target: median(16, 17, 19) = 17. Ann: 2 budgets, median 16.5.
    assert h.typical_budget(TARGET) == 17.0
    assert h.person(1, "director", TARGET)["budget"] == pytest.approx((2 * 16.5 + 4 * 17) / 6)
    assert h.person(None, "director", TARGET)["budget"] == 17.0  # a new person gets the typical budget
    f = h.budget_features([1], [2, None], TARGET)  # Bob has no actor credits, so all five actors are new
    assert f["director_budget"] == pytest.approx((2 * 16.5 + 4 * 17) / 6)
    assert f["actors_budget_max"] == f["actors_budget_min"] == 17.0


def test_budgets_on_or_after_the_date_never_count():
    same_day = (5, "2003-01-01", 1.0, 1.0, None, 30.0)
    later = (6, "2004-01-01", 1.0, 1.0, None, 1.0)
    base = history(BUDGET_FILMS, BASE_CREDITS)
    more = history(BUDGET_FILMS + [same_day, later], BASE_CREDITS + [(1, 5, "director"), (1, 6, "director")])
    assert more.typical_budget(TARGET) == base.typical_budget(TARGET)
    assert more.person(1, "director", TARGET)["budget"] == base.person(1, "director", TARGET)["budget"]
    assert more.typical_budget(TARGET + 1) == np.median([16, 17, 19, 30])  # the next day, it counts


def test_company_budget_takes_the_biggest_earlier_spender():
    films = film_frame(BUDGET_FILMS + [(4, "2003-01-01", 1.0, 1.0, None, 40.0)])  # same day as the target
    credits = pd.DataFrame({"company_id": [7, 7, 8, 7], "movie_id": [1, 2, 3, 4]})
    co = Companies(films, credits, pd.DataFrame({"id": [7, 8], "name": ["Small Films", "Big Studio"]}))
    small, big = (2 * 16.5 + 4 * 17) / 6, (1 * 19 + 4 * 17) / 5
    small_ref, big_by_name, unknown = {"id": 7, "name": None}, {"id": None, "name": " big STUDIO"},         {"id": None, "name": "Nobody Pictures"}
    assert co.features([small_ref], TARGET, 17.0) == {"company_budget": pytest.approx(small)}
    assert co.features([small_ref, big_by_name], TARGET, 17.0) == {"company_budget": pytest.approx(big)}
    # An unknown company is ignored next to a known one; alone, or with no companies, the typical budget.
    assert co.features([unknown, small_ref], TARGET, 17.0) == {"company_budget": pytest.approx(small)}
    assert co.features([unknown], TARGET, 17.0) == co.features([], TARGET, 17.0) == {"company_budget": 17.0}


def test_target_franchise_features_use_earlier_entries_only():
    films = pd.DataFrame({"collection_id": [77, 77, 77], "release_date": ["2000-01-01", "2002-01-01", "2010-01-01"],
                          "log_revenue": [10.0, 14.0, 99.0], "log_budget": [16.0, math.nan, 25.0]})
    fr = Franchises(films, pd.DataFrame({"id": [77], "name": ["Saga Collection"]}))
    assert fr.features(77, day_number("2000-01-01")) == {"is_franchise": 0, "franchise_earlier_films": 0,
                                                         "franchise_revenue": pytest.approx(math.nan, nan_ok=True)}
    assert fr.features(77, TARGET) == {"is_franchise": 1, "franchise_earlier_films": 2, "franchise_revenue": 12.0}
    assert fr.budget(77, TARGET) == {"franchise_budget": 16.0}  # the 2010 entry's budget is not known yet
    assert math.isnan(fr.budget(77, day_number("2000-01-01"))["franchise_budget"])
    assert math.isnan(fr.budget(None, TARGET)["franchise_budget"])
    assert fr.resolve({"id": None, "name": "saga collection"}) == 77
    assert fr.features(fr.resolve({"id": None, "name": "A Brand New Saga"}), TARGET)["is_franchise"] == 0


# ---------------------------------------------------------------- end to end on a small database


class FakeEmbedder:
    """Deterministic stand-in for MiniLM: the same text always gives the same unit vector."""

    def embed(self, texts):
        out = []
        for t in texts:
            seed = int(hashlib.sha1(t.encode("utf-8")).hexdigest()[:8], 16)
            v = np.random.default_rng(seed).normal(size=EMBED_DIM).astype(np.float32)
            out.append(v / np.linalg.norm(v))
        return np.array(out)


def credits(director_id: int, director_name: str, actors: list[tuple[int, str]]) -> dict:
    return {"cast": [{"id": i, "name": n, "character": "", "order": k} for k, (i, n) in enumerate(actors)],
            "crew": [{"id": director_id, "name": director_name, "job": "Director"}]}


CAST = [(100 + i, f"Actor {i}") for i in range(6)]
SAGA = {"id": 10, "name": "Heist Saga", "poster_path": None}
RECORDS = [
    film(1, release_date="2015-03-01", credits=credits(1, "Ann Director", CAST), belongs_to_collection=SAGA,
         budget=20_000_000),
    film(2, release_date="2017-05-01", credits=credits(1, "Ann Director", CAST[:3]), belongs_to_collection=None,
         revenue=400_000_000, budget=80_000_000),
    film(3, release_date="2019-07-12", credits=credits(1, "Ann Director", CAST), belongs_to_collection=SAGA,
         title="The Target"),
    film(4, release_date="2021-01-01", credits=credits(2, "Bob Other", CAST[2:]), belongs_to_collection=SAGA),
]


def make_db(tmp_path, records, name="movies.db") -> sqlite3.Connection:
    raw = tmp_path / f"{name}.jsonl"
    raw.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    cpi = tmp_path / "cpi.csv"
    cpi.write_text("year,cpi,note\n" + "".join(f"{y},{c},test\n" for y, c in TEST_CPI.items()), encoding="utf-8")
    build_db.build(raw, cpi, tmp_path / name)
    return sqlite3.connect(tmp_path / name)


def context(con) -> FeatureContext:
    pca = {"mean": np.zeros(EMBED_DIM, dtype=np.float32), "components": np.eye(16, EMBED_DIM, dtype=np.float32)}
    return FeatureContext(History.from_db(con), Franchises.from_db(con), Companies.from_db(con), fit_vocab(con),
                          {"heist": {5}}, pca, FakeEmbedder())


def target_row(con, tmp_path, movie_id=3) -> dict:
    ctx = context(con)
    table = build_table(con, ctx, cache=tmp_path / f"emb_{id(con)}.npz")
    return table.set_index("movie_id").loc[movie_id].to_dict()


def same(a: dict, b: dict) -> bool:
    return a.keys() == b.keys() and all(
        (pd.isna(a[k]) and pd.isna(b[k])) or a[k] == pytest.approx(b[k]) for k in a)


def test_training_and_api_paths_give_identical_features(tmp_path):
    con = make_db(tmp_path, RECORDS)
    ctx = context(con)
    train = target_row(con, tmp_path)
    m = con.execute("SELECT runtime, budget_2025, overview FROM movies WHERE id = 3").fetchone()
    typed = {  # what a creator would type for film 3: names, not ids
        "genres": ["Action"], "release_year": 2019, "release_month": 7, "runtime": m[0], "language": "en",
        "certification": "PG-13", "director": "ann director", "actors": [n for _, n in CAST], "themes": ["heist"],
        "companies": ["Studio"], "countries": ["US"], "franchise": "Heist Saga", "synopsis": m[2], "budget": m[1],
    }
    form, errors = contract.validate(typed, themes=ctx.themes)
    assert errors == {}
    api = {"split": "test", **build_features(form, day_number("2019-07-12"), ctx)}
    assert same(api, train)
    # The film itself and later films never count; film 1 (2015) is matured, film 2 (2017) is matured.
    assert train["director_n_films"] == 2 and train["is_franchise"] == 1 and train["franchise_earlier_films"] == 1
    # Budget track record: film 1 is the only earlier film with a 2025-dollar budget (the test CPI has no 2017).
    b1, b2 = (v for (v,) in con.execute("SELECT budget_2025 FROM movies WHERE id IN (1, 2) ORDER BY id"))
    assert b2 is None
    assert train["franchise_budget"] == train["director_budget"] == train["company_budget"] == \
        pytest.approx(math.log(b1))


def test_film_to_form_is_a_valid_creator_form(tmp_path):
    con = make_db(tmp_path, RECORDS)
    ctx = context(con)
    form = film_to_form(3, FilmForms.from_db(con), ctx)
    assert contract.validate(form, themes=ctx.themes)[1] == {}


def test_film_to_form_lists_genres_in_tmdb_order(tmp_path):
    genres = [{"id": 53, "name": "Thriller"}, {"id": 28, "name": "Action"}, {"id": 18, "name": "Drama"}]
    con = make_db(tmp_path, [film(1, genres=genres)])
    assert film_to_form(1, FilmForms.from_db(con), context(con))["genres"] == ["Thriller", "Action", "Drama"]


def test_later_films_and_the_films_own_results_do_not_change_its_features(tmp_path):
    base = target_row(make_db(tmp_path, RECORDS, "base.db"), tmp_path)
    changed = [dict(r) for r in RECORDS]
    # Film 3's own post-release numbers, and film 4 (released later) with very different results.
    changed[2].update(popularity=999.0, vote_count=50_000, vote_average=9.9, revenue=2_000_000_000)
    changed[2].update(budget=300_000_000)  # the film's own budget feeds log_budget only, not the track record
    changed[3].update(revenue=5_000_000_000, vote_average=1.0, budget=900_000_000)
    changed.append(film(5, release_date="2024-01-01", credits=credits(1, "Ann Director", CAST),
                        belongs_to_collection=SAGA))
    changed_row = target_row(make_db(tmp_path, changed, "changed.db"), tmp_path)
    assert changed_row.pop("log_budget") != pytest.approx(base.pop("log_budget"))
    assert same(changed_row, base)


def test_no_feature_uses_post_release_fields(tmp_path):
    row = target_row(make_db(tmp_path, RECORDS), tmp_path)
    names = [k for k in row if k != "split"]
    assert not [n for n in names if any(p in n for p in ("popularity", "vote_count", "vote_average"))]
    assert not [n for n in names if "revenue" in n and not n.startswith(("director_", "actors_", "franchise_"))]
    models = {f["name"]: f["models"] for f in feature_list(names)}
    assert "budget" not in models["log_budget"] and models["log_budget"] == ["revenue", "score"]
    assert all(set(m) == {"revenue", "budget", "score"} for n, m in models.items() if n != "log_budget")


# ---------------------------------------------------------------- synopsis and the real model


def test_missing_synopsis_is_neutral():
    pca = {"mean": np.full(EMBED_DIM, 0.1, dtype=np.float32), "components": np.eye(16, EMBED_DIM, dtype=np.float32)}
    assert synopsis_features(None, pca) == {**{n: 0.0 for n in SYNOPSIS_FEATURES[:-1]}, "has_synopsis": 0}
    mean = synopsis_features(pca["mean"], pca)  # the train mean is the neutral point
    assert all(mean[n] == 0.0 for n in SYNOPSIS_FEATURES[:-1]) and mean["has_synopsis"] == 1


needs_model = pytest.mark.skipif(not model_available(), reason="MiniLM not downloaded (run `make model`)")


@needs_model
def test_minilm_puts_similar_sentences_closer():
    from ml.features.text import Embedder

    a, b, c = Embedder().embed(["a bank heist", "robbers steal money", "a love story in Paris"])
    assert a @ b > a @ c
    assert np.linalg.norm(a) == pytest.approx(1.0, abs=1e-5)


@needs_model
def test_minilm_batching_does_not_change_vectors():
    from ml.features.text import Embedder

    e = Embedder()
    texts = ["short", "a much longer sentence about a detective chasing a killer through the rain", "mid length"]
    assert np.allclose(np.vstack([e.embed([t]) for t in texts]), e.embed(texts), atol=1e-5)
