"""The live new/upcoming films (V1.2): TMDB discover results mapped, filtered and sorted, and the title match for search."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.live import GENRES, map_results, match_live, sort_new, sort_upcoming, windows

TODAY = date(2026, 10, 30)


def raw_film(**over):
    film = {"id": 1, "title": "Night Train", "original_title": "Night Train", "release_date": "2026-10-20",
            "poster_path": "/p.jpg", "overview": "A story.", "adult": False, "popularity": 40.0, "genre_ids": [18, 53],
            "vote_average": 6.5, "vote_count": 120}
    return {**film, **over}


def live(title, movie_id=None, original=None, **over):
    return {"tmdb_id": 1, "movie_id": movie_id, "title": title, "original_title": original or title, **over}


def test_windows():
    w = windows(TODAY)
    assert w["new"] == (date(2026, 10, 16), TODAY)
    assert w["upcoming"] == (date(2026, 10, 31), date(2026, 12, 29))


@pytest.mark.parametrize("bad", [{"poster_path": None}, {"overview": ""}, {"overview": "  "}, {"adult": True},
                                 {"popularity": 1.0}, {"release_date": None}])
def test_films_that_fail_a_rule_are_dropped(bad):
    assert map_results([raw_film(**bad)], GENRES, TODAY, 5, 50) == []


def test_duplicates_go_and_genre_ids_become_names():
    out = map_results([raw_film(id=1), raw_film(id=1), raw_film(id=2)], GENRES, TODAY, 5, 50)
    assert [f["tmdb_id"] for f in out] == [1, 2] and out[0]["genres"] == ["Drama", "Thriller"]
    assert out[0]["poster"]["small"].endswith("/w342/p.jpg") and out[0]["movie_id"] is None


@pytest.mark.parametrize("release,status", [("2026-10-30", "out_today"), ("2026-10-20", "new"), ("2026-11-14", "upcoming")])
def test_status(release, status):
    assert map_results([raw_film(release_date=release)], GENRES, TODAY, 5, 50)[0]["status"] == status


def test_the_score_is_hidden_below_the_minimum_votes():
    out = map_results([raw_film(vote_count=12, vote_average=7.9), raw_film(id=2, vote_count=50, vote_average=7.9)],
                      GENRES, TODAY, 5, 50)
    assert out[0]["vote_average"] is None and out[0]["vote_count"] == 12
    assert out[1]["vote_average"] == 7.9


def test_sort_orders():
    a = {"tmdb_id": 1, "release_date": "2026-10-20", "popularity": 50}
    b = {"tmdb_id": 2, "release_date": "2026-10-28", "popularity": 10}
    c = {"tmdb_id": 3, "release_date": "2026-10-28", "popularity": 90}
    assert [f["tmdb_id"] for f in sort_new([a, b, c])] == [3, 2, 1]
    assert [f["tmdb_id"] for f in sort_upcoming([c, a, b])] == [1, 3, 2]


def test_match_ignores_accents_case_and_matches_word_prefixes():
    items = [live("Amélie Returns"), live("Amelia"), live("Amé"), live("Amen"), live("Other")]
    assert [f["title"] for f in match_live(items, "AME")] == ["Amélie Returns", "Amelia", "Amé"]  # limit 3
    assert match_live([live("The Long Night")], "lon")  # a later word counts
    assert match_live([live("Dune Three")], "dune thr") and not match_live([live("Dune Three")], "dune xyz")
    assert match_live([live("Titre", original="Amélie")], "amelie")  # the original title too


def test_films_in_the_database_and_empty_queries_never_match():
    assert match_live([live("Dune Three", movie_id=5)], "dune") == []
    assert match_live([live("Dune Three")], "  ") == [] and match_live([live("Dune Three")], "!!") == []
