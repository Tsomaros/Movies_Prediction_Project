"""services/career_model.py (Day 14.8): "Their usual film" and "Something new" recipes, chips and the form."""

from __future__ import annotations

import sqlite3

import pytest

from backend.app.services.career_model import (
    GenreAlreadyDone, UnknownGenre, chips, never_done_genres, new_recipe, recent_genre_counts, recipe_to_form,
    repeat_collaborators, usual_recipe,
)
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES
from ml.features.contract import MIN_ACTORS, validate

GENRES = [(12, "Adventure"), (14, "Fantasy"), (16, "Animation"), (18, "Drama"), (27, "Horror"), (28, "Action"),
          (35, "Comedy"), (36, "History"), (37, "Western"), (53, "Thriller"), (80, "Crime"), (99, "Documentary"),
          (878, "Science Fiction"), (9648, "Mystery"), (10402, "Music"), (10749, "Romance"), (10751, "Family"),
          (10752, "War"), (10770, "TV Movie")]
NAMES = dict(GENRES)
ACTION, ANIMATION, DRAMA, HORROR, COMEDY, WESTERN, MUSIC = 28, 16, 18, 27, 35, 37, 10402
THRILLER, CRIME, DOCUMENTARY, SCIFI, MYSTERY, FAMILY = 53, 80, 99, 878, 9648, 10751
THEMES = {"love": {1, 2}, "revenge": {3}, "heist": {4}, "ghosts": {5}, "space": {6}, "school": {7}}

ACTOR, REPEAT_DIRECTOR, COSTAR, ONCE_STAR, DIRECTOR, FAVOURITE_ACTOR = 1, 2, 3, 4, 5, 6
SPARSE_ACTOR, DID_EVERYTHING, ONCE_DIRECTOR, UNRATED_ACTOR = 7, 8, 9, 10
PEOPLE = {ACTOR: "Actor A", REPEAT_DIRECTOR: "Repeat Director", COSTAR: "Co Star", ONCE_STAR: "Once Star",
          DIRECTOR: "Director D", FAVOURITE_ACTOR: "Favourite Actor", SPARSE_ACTOR: "Sparse Actor",
          DID_EVERYTHING: "Did Everything", ONCE_DIRECTOR: "Once Director", UNRATED_ACTOR: "Unrated Actor"}


def _film(i, date, votes=100, *, genres=(), kw=(), lang="en", cert="R", countries=("US",), runtime=100,
          budget=None, suspect=0, year=None):
    year = year or (int(date[:4]) if date else None)
    return dict(id=i, date=date, year=year, month=int(date[5:7]) if date else None, votes=votes, genres=genres,
                kw=kw, lang=lang, cert=cert, countries=countries, runtime=runtime, budget=budget, suspect=suspect)


FILMS = [
    # Actor A: 12 rated films 2010-21 (only the last 10 count), a low-vote 2022 film and an undated one.
    _film(201, "2010-05-01", genres=(COMEDY, ACTION)),
    _film(202, "2011-05-01", genres=(COMEDY, ACTION)),
    *[_film(203 + k, f"{2012 + k}-{(10 if k < 6 else 4):02d}-01",
            genres=(DRAMA, *((COMEDY,) if k < 3 else ()), *((CRIME,) if k < 4 else (THRILLER,) if k < 8 else ())),
            kw=(*((3,) if k < 6 else (4,)), *((1,) if k in (2, 3) else ()), *((2,) if k == 9 else ())),
            lang="fr" if k in (0, 1) else "en", cert=None if k in (0, 1, 2) else "R",
            countries=("US", "FR") if k in (0, 1) else ("US",), runtime=[90, 95, 100, 105, 110, 116, 120, 125, 130, 135][k],
            budget=([None] * 5 + [1_000_000, 20_000_000, 30_000_000, 40_000_000, None])[k],
            suspect=int(k == 5))
      for k in range(10)],  # 203..212; Crime 203-206 ties Thriller 207-210, Thriller is more recent
    _film(213, "2022-01-01", votes=10, genres=(WESTERN,)),
    _film(214, None, genres=(MUSIC,)),
    # Director D: five rated Crime/Drama films 2019-23.
    *[_film(301 + k, f"{2019 + k}-02-01", genres=(CRIME, DRAMA), kw=(4,), cert="PG-13", countries=("GB",))
      for k in range(5)],
    # Sparse actor: films without keywords, certification, country, runtime, language or month.
    _film(601, None, year=2015, genres=(HORROR,), lang=None, cert=None, countries=(), runtime=None),
    _film(602, None, year=2016, genres=(HORROR,), lang=None, cert=None, countries=(), runtime=None),
    # Did everything: a low-vote film with every genre, one rated Drama.
    _film(501, "2020-01-01", votes=10, genres=tuple(NAMES)),
    _film(502, "2019-07-01", genres=(DRAMA,), kw=(3,)),
    # The recent pool, 2021-25.
    *[_film(401 + k, f"{2021 + k}-10-01", genres=(HORROR, MYSTERY), kw=(5, 7) if k < 3 else (5,)) for k in range(5)],
    _film(406, "2023-03-01", genres=(HORROR,), kw=(5,), cert="PG-13"),
    _film(407, "2024-03-01", genres=(HORROR,), kw=(5,), cert="PG-13"),
    *[_film(408 + k, f"{2021 + k % 5}-06-01", genres=(SCIFI, ACTION), kw=(6,)) for k in range(6)],
    _film(414, "2022-06-01", genres=(SCIFI, HORROR), kw=(6,)),
    _film(415, "2022-06-01", genres=(FAMILY,), kw=(7,), cert="G"),
    _film(416, "2023-06-01", genres=(FAMILY,), kw=(7,), cert="G"),
    _film(417, "2024-06-01", genres=(ANIMATION, FAMILY), kw=(7,), cert="G"),
    _film(418, "2025-06-01", genres=(DOCUMENTARY,), kw=(1,), cert="NR"),
]
CAST = [(m, ACTOR, 0) for m in range(201, 215)] + [
    (209, COSTAR, 1), (213, COSTAR, 1), (212, ONCE_STAR, 1),
    (301, DIRECTOR, 5), (302, DIRECTOR, 5), (301, FAVOURITE_ACTOR, 0), (302, FAVOURITE_ACTOR, 0),
    (303, FAVOURITE_ACTOR, 0), (301, ONCE_STAR, 1), (302, ONCE_STAR, 1), (304, COSTAR, 0), (305, COSTAR, 0),
    (601, SPARSE_ACTOR, 0), (602, SPARSE_ACTOR, 0), (501, DID_EVERYTHING, 0), (502, DID_EVERYTHING, 0),
    (213, UNRATED_ACTOR, 2),
]
CREW = [(210, REPEAT_DIRECTOR, "Director"), (211, REPEAT_DIRECTOR, "Director"), (212, ONCE_DIRECTOR, "Director"),
        *[(301 + k, DIRECTOR, "Director") for k in range(5)]]


@pytest.fixture
def con(tmp_path):
    c = sqlite3.connect(tmp_path / "movies.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.executemany("INSERT INTO genres VALUES (?, ?)", GENRES)
    c.executemany("INSERT INTO people VALUES (?, ?)", PEOPLE.items())
    for f in FILMS:
        c.execute("""INSERT INTO movies (id, title, release_date, year, month, runtime, original_language,
                                         us_certification, budget_2025, money_suspect, revenue_incomplete,
                                         covid_period, vote_count, vote_average, score_ok)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 6.5, ?)""",
                  (f["id"], f"Film {f['id']}", f["date"], f["year"], f["month"], f["runtime"], f["lang"], f["cert"],
                   f["budget"], f["suspect"], f["votes"], int(f["votes"] >= MIN_VOTES)))
        c.executemany("INSERT INTO movie_genres VALUES (?, ?, ?)", [(f["id"], g, o) for o, g in enumerate(f["genres"])])
        c.executemany("INSERT INTO movie_keywords VALUES (?, ?)", [(f["id"], k) for k in f["kw"]])
        c.executemany("INSERT INTO movie_countries VALUES (?, ?)", [(f["id"], x) for x in f["countries"]])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, 'Role', ?)", CAST)
    c.executemany("INSERT INTO movie_crew VALUES (?, ?, ?)", CREW)
    yield c
    c.close()


def usual(con, person=ACTOR, role="acting"):
    return usual_recipe(con, person, role, MIN_VOTES, 2027, THEMES)


def test_usual_recipe_is_deterministic_and_uses_last_ten(con):
    a = usual(con)
    assert a == usual(con)
    assert a["genres"] == [DRAMA, THRILLER]  # Comedy has 5 films overall but only 3 of the last 10; Thriller ties Crime
    assert a["themes"] == ["revenge", "heist", "love"]
    assert (a["language"], a["runtime"], a["release_month"], a["certification"], a["country"]) == ("en", 113, 10, "R", "US")
    assert a["budget_2025"] == 30_000_000  # the suspect 1M is left out
    assert a["release_year"] == 2027
    assert a["actors"][0] == {"id": ACTOR, "name": "Actor A"}
    assert a["labels"] == {"genres": ["Drama", "Thriller"], "themes": ["revenge", "heist", "love"],
                           "collaborators": ["Repeat Director", "Co Star"]}


def test_collaborators_need_two_shared_films(con):
    r = usual(con)
    assert r["director"] == {"id": REPEAT_DIRECTOR, "name": "Repeat Director"}  # Once Director has one film
    assert r["actors"] == [{"id": ACTOR, "name": "Actor A"}, {"id": COSTAR, "name": "Co Star"}, "new"]


def test_repeat_collaborators_count_low_vote_films_and_never_the_person(con):
    assert repeat_collaborators(con, ACTOR, "acting", "actor", 5) == [{"id": COSTAR, "name": "Co Star"}]
    # Director D acts in two of their own films; Co Star ties Once Star on 2 but has the more recent shared film.
    assert repeat_collaborators(con, DIRECTOR, "directing", "actor", 5) == [
        {"id": FAVOURITE_ACTOR, "name": "Favourite Actor"}, {"id": COSTAR, "name": "Co Star"},
        {"id": ONCE_STAR, "name": "Once Star"}]


def test_a_director_who_is_also_a_co_star_is_named_once(con):
    r = usual(con, FAVOURITE_ACTOR)
    assert r["director"]["id"] == DIRECTOR and r["actors"][1]["id"] == DIRECTOR  # both slots: a real setup
    assert r["labels"]["collaborators"] == ["Director D", "Once Star"]


def test_director_page_flips_roles(con):
    r = usual(con, DIRECTOR, "directing")
    assert r["director"] == {"id": DIRECTOR, "name": "Director D"}
    assert [a["id"] for a in r["actors"]] == [FAVOURITE_ACTOR, COSTAR, ONCE_STAR]
    assert r["genres"] == [CRIME, DRAMA] and r["country"] == "GB" and r["certification"] == "PG-13"


def test_gaps_are_filled_from_recent_films_of_those_genres(con):
    r = usual(con, SPARSE_ACTOR)
    assert r["genres"] == [HORROR]
    assert r["themes"] == ["ghosts", "school", "space"]  # recent Horror films: ghosts 7, school 3, space 1
    assert r["certification"] == "R" and r["release_month"] == 10
    assert (r["runtime"], r["language"], r["country"], r["budget_2025"]) == (110, "en", None, None)
    assert r["director"] == "new" and r["actors"][1:] == ["new", "new"]


def test_no_rated_films_raises(con):
    with pytest.raises(ValueError):
        usual(con, UNRATED_ACTOR)


def test_never_done_counts_low_vote_and_undated_films(con):
    done = {COMEDY, ACTION, DRAMA, CRIME, THRILLER, WESTERN, MUSIC}
    assert never_done_genres(con, ACTOR, "acting") == set(NAMES) - done
    assert never_done_genres(con, DID_EVERYTHING, "acting") == set()


def test_recent_genre_counts(con):
    pairs, singles = recent_genre_counts(con, MIN_VOTES)
    assert pairs[frozenset({HORROR, MYSTERY})] == 5 and pairs[frozenset({SCIFI, ACTION})] == 6
    assert singles[HORROR] == 8 and singles[SCIFI] == 7 and DRAMA in singles and COMEDY not in singles


def test_new_recipe_uses_only_never_done_genres(con):
    u = usual(con)
    new, note = new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES)
    assert new["genres"] == [HORROR, MYSTERY] and note is None  # Sci-fi/Action is more common, but Action is done
    assert set(new["genres"]) <= never_done_genres(con, ACTOR, "acting")
    assert new["themes"] == ["ghosts", "school"]
    assert new["actors"] == [{"id": ACTOR, "name": "Actor A"}, "new", "new"] and new["director"] == "new"
    assert new["labels"] == {"genres": ["Horror", "Mystery"], "themes": ["ghosts", "school"], "collaborators": []}
    for field in ("runtime", "language", "release_month", "release_year", "certification", "country", "budget_2025"):
        assert new[field] == u[field]


def test_new_recipe_on_a_director_page_keeps_them_directing(con):
    new, _ = new_recipe(con, DIRECTOR, "directing", usual(con, DIRECTOR, "directing"), MIN_VOTES, THEMES)
    assert new["director"] == {"id": DIRECTOR, "name": "Director D"} and new["actors"] == ["new"] * 3


def test_chip_genre_takes_its_most_common_never_done_partner(con):
    u = usual(con)
    assert new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES, genre_id=SCIFI)[0]["genres"] == [SCIFI, HORROR]
    assert new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES, genre_id=FAMILY)[0]["genres"] == [FAMILY, ANIMATION]
    assert new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES, genre_id=DOCUMENTARY)[0]["genres"] == [DOCUMENTARY]


def test_new_recipe_fallbacks(con):
    u = usual(con, DID_EVERYTHING)
    new, note = new_recipe(con, DID_EVERYTHING, "acting", u, MIN_VOTES, THEMES)
    assert new["genres"] == u["genres"] == [DRAMA] and note == "They've already worked in every genre."
    assert chips(con, DID_EVERYTHING, "acting", None, MIN_VOTES) == []


def test_chip_errors(con):
    u = usual(con)
    with pytest.raises(GenreAlreadyDone):
        new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES, genre_id=DRAMA)
    with pytest.raises(UnknownGenre):
        new_recipe(con, ACTOR, "acting", u, MIN_VOTES, THEMES, genre_id=999)


def test_chips_max_four_with_default_marked(con):
    c = chips(con, ACTOR, "acting", HORROR, MIN_VOTES)
    assert c == [{"genre_id": HORROR, "name": "Horror", "default": True},
                 {"genre_id": SCIFI, "name": "Science Fiction", "default": False},
                 {"genre_id": MYSTERY, "name": "Mystery", "default": False},
                 {"genre_id": FAMILY, "name": "Family", "default": False}]
    c = chips(con, ACTOR, "acting", ANIMATION, MIN_VOTES)  # 1 recent film: it replaces the 4th chip
    assert [x["genre_id"] for x in c] == [HORROR, SCIFI, MYSTERY, ANIMATION]
    assert [x["genre_id"] for x in c if x["default"]] == [ANIMATION]


def test_recipe_to_form(con):
    form = recipe_to_form(usual(con), NAMES)
    assert form["genres"] == ["Drama", "Thriller"] and form["countries"] == ["US"]
    assert form["director"] == {"id": REPEAT_DIRECTOR, "name": "Repeat Director"}
    assert form["actors"] == [{"id": ACTOR, "name": "Actor A"}, {"id": COSTAR, "name": "Co Star"},
                              {"name": "New actor 3"}, {"name": "New actor 4"}, {"name": "New actor 5"}]
    assert len(form["actors"]) == MIN_ACTORS
    assert not {"budget", "franchise", "companies"} & set(form)
    assert recipe_to_form(usual(con, SPARSE_ACTOR), NAMES)["director"] == {"name": "New director"}


@pytest.mark.parametrize("person,role", [(ACTOR, "acting"), (DIRECTOR, "directing"), (SPARSE_ACTOR, "acting"),
                                         (DID_EVERYTHING, "acting"), (COSTAR, "acting"), (FAVOURITE_ACTOR, "acting")])
def test_both_recipes_pass_the_contract(con, person, role):
    u = usual(con, person, role)
    recipes = [u, new_recipe(con, person, role, u, MIN_VOTES, THEMES)[0]]
    recipes += [new_recipe(con, person, role, u, MIN_VOTES, THEMES, genre_id=c["genre_id"])[0]
                for c in chips(con, person, role, None, MIN_VOTES)]
    for r in recipes:
        _, errors = validate(recipe_to_form(r, NAMES), themes=list(THEMES))
        assert errors == {}


def test_a_short_film_career_gets_the_shortest_runtime_the_form_allows(con):
    con.execute("UPDATE movies SET runtime = 7 WHERE id IN (601, 602)")  # 2,360 real people have a median under 40
    assert usual(con, SPARSE_ACTOR)["runtime"] == 40
