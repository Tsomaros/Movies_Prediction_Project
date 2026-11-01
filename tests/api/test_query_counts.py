"""V1.5: a browse page costs a fixed, small number of SQL statements (no query per film).

`repo.search` is count, page ids, cards (the fresh flag is read in the same statement), genres: 4 statements, however
many films the page holds. The same goes for the cards of a list (`summaries`: 2) and for autocomplete extras (1).
Counted by wrapping the connection's `execute`, because the trace callback also reports FTS5's own internal queries.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

import pytest

from backend.app.repo import movies as repo
from backend.app.repo import people
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

TODAY = date(2026, 11, 1)


class Counting:
    """A connection that counts the statements run through it."""

    def __init__(self, con: sqlite3.Connection):
        self.con, self.statements = con, []

    def execute(self, sql: str, *args: Any):
        self.statements.append(sql)
        return self.con.execute(sql, *args)


@pytest.fixture
def con(db):  # noqa: F811
    c = sqlite3.connect(db / "movies.db")
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.mark.parametrize("kw", [{}, {"page_size": 48}, {"sort": "score"}, {"sort": "title"}, {"q": "film"},
                                {"genre": "Drama", "year_from": 2010}])
def test_a_browse_page_issues_four_statements_whatever_its_size(con, kw):
    counting = Counting(con)
    rows, total = repo.search(counting, today=TODAY, **{"page_size": 24, **kw})
    assert rows and total >= len(rows)
    assert len(counting.statements) == 4, counting.statements
    assert all("fresh" in r for r in rows)


def test_a_page_of_cards_is_two_statements_for_one_film_or_forty(con):
    for ids in ([1], list(range(1, 41))):
        counting = Counting(con)
        assert repo.summaries(counting, ids)
        assert len(counting.statements) == 2


def test_autocomplete_extras_are_one_statement_for_any_number_of_people(con):
    ids = [r[0] for r in con.execute("SELECT id FROM people LIMIT 30")]
    counting = Counting(con)
    people.extras(counting, ids, "actor")
    assert len(counting.statements) == 1
