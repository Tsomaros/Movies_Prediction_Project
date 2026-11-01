"""GET /health is cheap (V1.5): the build's numbers are read once at startup, a request only checks the database opens."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.repo import meta
from backend.app.settings import API_PREFIX, Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

HEALTH = f"{API_PREFIX}/health"


def make(db, **kw):
    return TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object()), **kw)


def test_a_request_does_not_count_the_films_again(db, monkeypatch):
    with make(db) as client:
        first = client.get(HEALTH).json()["database"]
        monkeypatch.setattr(meta, "build_info", lambda con: pytest.fail("health ran build_info per request"))
        r = client.get(HEALTH)
    assert r.status_code == 200 and r.json()["database"] == first and first["films"] > 0
    assert r.headers["cache-control"] == "no-store"


def test_an_unreadable_database_still_fails_the_check(db):
    with make(db, raise_server_exceptions=False) as client:
        assert client.get(HEALTH).status_code == 200
        (db / "movies.db").rename(db / "gone.db")
        assert client.get(HEALTH).status_code == 500
