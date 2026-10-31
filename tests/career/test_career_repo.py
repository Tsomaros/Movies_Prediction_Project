"""repo/career.py (Day 14.8): career films per role, roles available, year averages and population stats."""

from __future__ import annotations

import sqlite3
import statistics

import pytest

from backend.app.repo.career import career_films, counted, latest_year, population_stats, roles_available
from ml.data.build_db import SCHEMA
from ml.data.clean import MIN_VOTES

ACTOR, WRITER, OTHER, SETTLER = 1, 2, 3, 4
LEAD_ID, CAMEO_ID, NO_DATE_ID, LOW_VOTE_ID, NO_ORD_ID, UNDATED_ID = 101, 103, 102, 106, 107, 109
EXPECTED_ORDER = [101, 103, 102, 104, 105, 106, 107, 108]  # 102 has only a year: 1 July, after 103; 104/105 same date
POP_2015 = [7.0, 6.5, 7.5, 6.5, 8.0, 5.5]  # rated acting films 2006-15: 102, 103, 104, 105, 107, 108

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
# SETTLER's films: release 2018-01-01 and the pull date; 181 days apart is settling, 182 is settled
YOUNG_181, OLD_182, NO_PULL_ID = 113, 114, 115
SETTLE_MOVIES = [(YOUNG_181, "2018-01-01", "2018-07-01T10:00:00+00:00"), (OLD_182, "2018-01-01", "2018-07-02T10:00:00+00:00"),
                 (NO_PULL_ID, "2018-01-01", None)]
CREW = [(110, ACTOR, "Director"), (111, ACTOR, "Director"), (110, WRITER, "Screenplay"), (110, WRITER, "Writer")]


@pytest.fixture
def con(tmp_path):
    c = sqlite3.connect(tmp_path / "movies.db")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.executemany("INSERT INTO people VALUES (?, ?)", [(p, f"Person {p}") for p in (ACTOR, WRITER, OTHER, SETTLER)])
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, money_suspect, revenue_incomplete, covid_period)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
                  [(i, f"Film {i}", d, y, v, s, int(v >= MIN_VOTES), f"/f{i}.jpg") for i, d, y, v, s in MOVIES])
    c.execute("UPDATE movies SET pulled_at = '2026-10-30T13:42:39+00:00'")
    c.executemany("""INSERT INTO movies (id, title, release_date, year, vote_count, vote_average, score_ok,
                                         poster_path, money_suspect, revenue_incomplete, covid_period, pulled_at)
                     VALUES (?, ?, ?, 2018, 100, 7.0, 1, NULL, 0, 0, 0, ?)""",
                  [(i, f"Film {i}", d, pulled) for i, d, pulled in SETTLE_MOVIES])
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, ?, ?)", CAST)
    c.executemany("INSERT INTO movie_cast VALUES (?, ?, 'Role', 0)", [(i, SETTLER) for i, _, _ in SETTLE_MOVIES])
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
                             "vote_count": 200, "rated": True, "settling": False, "lead": True, "character": "Friend",
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


def test_population_stats_without_films_raises(con):
    with pytest.raises(ValueError, match="writing"):
        population_stats(con, "writing", MIN_VOTES, end_year=2000)


def test_latest_year(con):
    assert latest_year(con) == 2018


def test_shorts_are_left_out_of_the_films_and_the_population(con):
    before = population_stats(con, "acting", MIN_VOTES, 2015)
    con.execute("""INSERT INTO movies (id, title, release_date, year, runtime, vote_count, vote_average, score_ok,
                                       money_suspect, revenue_incomplete, covid_period)
                   VALUES (120, 'Short', '2012-05-05', 2012, 8, 900, 9.5, 1, 0, 0, 0)""")
    con.execute("INSERT INTO movie_cast VALUES (120, ?, 'Himself', 0)", (ACTOR,))
    assert 120 not in {f["movie_id"] for f in career_films(con, ACTOR, "acting", MIN_VOTES)}
    assert population_stats(con, "acting", MIN_VOTES, 2015) == before
    con.execute("UPDATE movies SET runtime = 40 WHERE id = 120")  # the form's minimum is a feature film
    assert 120 in {f["movie_id"] for f in career_films(con, ACTOR, "acting", MIN_VOTES)}


def test_settled_boundary_uses_the_pull_date(con):  # released 181 vs 182 days before the pull
    f = {x["movie_id"]: x for x in career_films(con, SETTLER, "acting", MIN_VOTES)}
    assert f[YOUNG_181]["settling"] is True and f[OLD_182]["settling"] is False
    assert counted(f[YOUNG_181]) is False and counted(f[OLD_182]) is True


def test_no_release_date_or_pull_date_counts_as_settled(con):
    f = {x["movie_id"]: x for x in career_films(con, ACTOR, "acting", MIN_VOTES)}
    g = {x["movie_id"]: x for x in career_films(con, SETTLER, "acting", MIN_VOTES)}
    assert f[NO_DATE_ID]["settling"] is False and g[NO_PULL_ID]["settling"] is False
