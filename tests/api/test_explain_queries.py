"""V1.5: scripts/explain_queries.py runs every hot query on a database and reports its plans (a smoke test on the
small fixture database, whose tables are all under the 10,000-row line, so nothing can be reported)."""

from __future__ import annotations

import shutil
import sqlite3
import sys

from scripts import explain_queries
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)


def test_the_script_plans_every_hot_query(db, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr(sys, "argv", ["explain_queries", "--db", str(db / "movies.db")])
    assert explain_queries.main() == 0
    out = capsys.readouterr().out
    assert "browse q=the" in out and "person page (Hanks)" in out and "0 table scan(s)" in out


def test_a_big_table_scan_is_reported_and_fails(db, tmp_path, monkeypatch, capsys):  # noqa: F811
    shutil.copyfile(db / "movies.db", tmp_path / "movies.db")
    with sqlite3.connect(tmp_path / "movies.db") as con:
        con.execute("DROP INDEX idx_movies_title")  # the Title sort now scans and sorts the table
    monkeypatch.setattr(sys, "argv", ["explain_queries", "--db", str(tmp_path / "movies.db"), "--min-rows", "10"])
    assert explain_queries.main() == 1
    assert "TABLE SCAN" in capsys.readouterr().out
