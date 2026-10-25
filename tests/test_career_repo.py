"""repo/career.py (Day 14.8): career films per role, roles available, trusted revenue and population stats."""

from __future__ import annotations

import math
import sqlite3
import statistics

import pytest

from backend.app.repo.career import career_films, latest_year, population_stats, roles_available
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES

ACTOR, WRITER, OTHER = 1, 2, 3
LEAD_ID, CAMEO_ID, NO_DATE_ID, LOW_VOTE_ID, NO_ORD_ID, UNDATED_ID = 101, 103, 102, 106, 107, 109
EXPECTED_ORDER = [101, 103, 102, 104, 105, 106, 107, 108]  # 102 has only a year: 1 July, after 103; 104/105 same date
POP_2015 = [7.0, 6.5, 7.5, 6.5, 8.0, 5.5]  # rated acting films 2006-15: 102, 103, 104, 105, 107, 108
DOUBTED_ID, INCOMPLETE_ID = 103, 104
REVENUE = {  # id: (revenue_2025, money_suspect, revenue_incomplete)
    101: (50e6, 0, 0), 102: (200e6, 0, 0), DOUBTED_ID: (10e6, 1, 0), INCOMPLETE_ID: (30e6, 0, 1), 105: (80e6, 0, 0),
    107: (120e6, 0, 0), 109: (1e9, 0, 0), 112: (5e6, 0, 0),
}
REVENUE_POP_2015 = [200e6, 80e6, 120e6, 5e6]  # trusted acting films 2006-15, votes or not: 102, 105, 107, 112

MOVIES = [  # (id, release_date, year, vote_count, vote_average)
    (101, "2005-03-01", 2005, 100, 6.0),
    (102, None, 2008, 200, 7.0),
    (103, "2008-03-01", 2008, 80, 6.5),
    (104, "2010-05-05", 2010, 60, 7.5),
    (105, "2010-05-05", 2010, 70, 6.5),
    (106, "2012-01-01", 2012, 10, 9.0),
    (107, "2014-06-01", 2014, 300, 8.0),
    (108, "2015-02-02", 2015, 90, 5.5),
    (109, None, None, 500, 7.0),
    (110, "2016-04-04", 2016, 120, 7.2),
    (111, "2018-09-09", 2018, 150, 6.8),
    (112, "2010-08-08", 2010, 5, 9.9),
]
CAST = [  # (movie_id, person_id, character, ord)
    (101, ACTOR, "Hero", 0), (102, ACTOR, "Friend", 1), (103, ACTOR, "Himself", 7), (104, ACTOR, "Rival", 2),
    (105, ACTOR, "Cop", 3), (106, ACTOR, "Ghost", 4), (107, ACTOR, "Narrator", None), (108, ACTOR, "Dad", 5),
    (109, ACTOR, "Unknown", 0), (104, OTHER, "Lead", 0), (112, OTHER, "Lead", 0),
]
CREW = [(110, ACTOR, "Director"), (111, ACTOR, "Director"), (110, WRITER, "Screenplay"), (110, WRITER, "Writer")]


@pytest.fixture
def con(tmp_path):
    c = sqlite3.connect(tmp_path / "movies.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.executemany("INSERT INTO people VALUES (?, ?)", [(p, f"Person {p}") for p in (ACTOR, WRITER, OTHER)])
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, revenue_2025, money_suspect, revenue_incomplete, covid_period)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                  [(i, f"Film {i}", d, y, v, s, int(v >= MIN_VOTES), f"/f{i}.jpg", *REVENUE.get(i, (None, 0, 0)))
                   for i, d, y, v, s in MOVIES])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, ?, ?)", CAST)
    c.executemany("INSERT INTO movie_crew VALUES (?, ?, ?)", CREW)
    yield c
    c.close()


def test_films_dated_only_deduped_and_ordered(con):
    films = career_films(con, ACTOR, "acting", MIN_VOTES)
    assert [f["movie_id"] for f in films] == EXPECTED_ORDER
    assert len({f["movie_id"] for f in films}) == len(films)
    assert UNDATED_ID not in {f["movie_id"] for f in films}


def test_film_without_a_date_sorts_as_1_july_and_keeps_its_fields(con):
    f = {x["movie_id"]: x for x in career_films(con, ACTOR, "acting", MIN_VOTES)}
    assert f[NO_DATE_ID] == {"movie_id": 102, "title": "Film 102", "year": 2008, "release_date": None, "score": 7.0,
                             "revenue": 200e6, "vote_count": 200, "rated": True, "lead": True, "character": "Friend",
                             "poster_path": "/f102.jpg"}


def test_rated_and_lead_flags(con):
    f = {x["movie_id"]: x for x in career_films(con, ACTOR, "acting", MIN_VOTES)}
    assert f[LOW_VOTE_ID]["rated"] is False and f[LEAD_ID]["lead"] is True and f[CAMEO_ID]["lead"] is False
    assert f[NO_ORD_ID]["lead"] is False


def test_crew_role_has_no_lead_flag(con):
    films = career_films(con, ACTOR, "directing", MIN_VOTES)
    assert [f["movie_id"] for f in films] == [110, 111]
    assert all(f["lead"] is None and f["character"] is None for f in films)


def test_writer_credited_twice_on_one_film_counts_once(con):
    assert [f["movie_id"] for f in career_films(con, WRITER, "writing", MIN_VOTES)] == [110]
    assert roles_available(con, WRITER, MIN_VOTES) == [{"role": "writing", "film_count": 1, "rated_count": 1}]


def test_roles_available_counts(con):
    assert roles_available(con, ACTOR, MIN_VOTES) == [{"role": "acting", "film_count": 8, "rated_count": 7},
                                                      {"role": "directing", "film_count": 2, "rated_count": 2}]


def test_population_stats(con):
    mu, sd = population_stats(con, "acting", MIN_VOTES, end_year=2015)
    assert mu == pytest.approx(41 / 6) and sd == pytest.approx(statistics.pstdev(POP_2015)) and sd > 0


def test_revenue_is_trusted_only(con):
    f = {x["movie_id"]: x["revenue"] for x in career_films(con, ACTOR, "acting", MIN_VOTES)}
    assert f[101] == 50e6 and f[DOUBTED_ID] is None and f[INCOMPLETE_ID] is None and f[108] is None
    assert [x["revenue"] for x in career_films(con, ACTOR, "directing", MIN_VOTES)] == [None, None]


def test_revenue_population_stats_are_log_dollars_of_trusted_films(con):
    mu, sd = population_stats(con, "acting", MIN_VOTES, end_year=2015, metric="revenue")
    logs = [math.log(x) for x in REVENUE_POP_2015]  # the doubted, incomplete and undated films are left out
    assert mu == pytest.approx(statistics.fmean(logs)) and sd == pytest.approx(statistics.pstdev(logs))
    with pytest.raises(ValueError, match="trusted-revenue writing"):
        population_stats(con, "writing", MIN_VOTES, end_year=2018, metric="revenue")


def test_population_stats_without_films_raises(con):
    with pytest.raises(ValueError, match="writing"):
        population_stats(con, "writing", MIN_VOTES, end_year=2000)


def test_latest_year(con):
    assert latest_year(con) == 2018
