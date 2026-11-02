"""Autocomplete lookups read from a file written before the image is built (V1.5): the same answers as building them
at startup, and refused when the file came from another database."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.search.lookups import KINDS, Lookups, NameIndex, save_prebuilt
from backend.app.settings import Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture)


@pytest.fixture
def con(db):  # noqa: F811
    with closing(sqlite3.connect(db / "movies.db")) as c:
        yield c


def test_a_saved_file_loads_as_the_same_indexes(con, tmp_path):
    built = Lookups.from_db(con)
    path = tmp_path / "lookups.joblib"
    assert save_prebuilt(con, path)["films"] > 0
    loaded = Lookups.load(con, prebuilt=path)
    for kind in KINDS:
        a, b = built.indexes[kind], loaded.indexes[kind]
        assert isinstance(b, NameIndex) and a.names == b.names and a.keys == b.keys
        for field in ("ids", "n_films", "name_offsets", "key_offsets", "key_entry"):
            assert np.array_equal(getattr(a, field), getattr(b, field)), (kind, field)
    assert loaded.search("director", "director 3") == built.search("director", "director 3")


def test_without_a_file_it_builds_from_the_database(con):
    assert len(Lookups.load(con).indexes["actor"]) == len(Lookups.from_db(con).indexes["actor"])


def test_a_file_from_another_database_is_refused(con, tmp_path):
    path = tmp_path / "lookups.joblib"
    save_prebuilt(con, path)
    con.execute("UPDATE meta SET value = '\"another build\"' WHERE key = 'built_at'")
    with pytest.raises(ValueError, match="another database"):
        Lookups.load(con, prebuilt=path)


def test_startup_reads_the_file_and_does_not_build(db, tmp_path, monkeypatch):  # noqa: F811
    path = tmp_path / "lookups.joblib"
    with closing(sqlite3.connect(db / "movies.db")) as c:
        save_prebuilt(c, path)

    def refuse(*_):
        raise AssertionError("built the lookups at startup")

    monkeypatch.setattr(Lookups, "from_db", refuse)
    with TestClient(create_app(Settings(db_path=db / "movies.db", lookups_file=path), predictor=object())) as client:
        assert client.app.state.lookups.search("director", "director 3")[0]["name"] == "Director 3"


def test_the_setting_comes_from_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "lookups.joblib"
    monkeypatch.setenv("LOOKUPS_FILE", str(path))
    assert Settings.from_env().lookups_file == path
    monkeypatch.delenv("LOOKUPS_FILE")
    assert Settings.from_env().lookups_file is None
