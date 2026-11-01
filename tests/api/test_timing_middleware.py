"""The Server-Timing middleware (backend/app/services/platform/timing.py, V1.5), offline."""

import logging
import re

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.platform import timing
from backend.app.settings import API_PREFIX, Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

HEADER = re.compile(r"^app;dur=\d+(\.\d+)?$")


@pytest.fixture
def client(db):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object())) as c:
        yield c


def test_every_response_has_a_server_timing_header(client):
    for path in (f"{API_PREFIX}/health", f"{API_PREFIX}/no-such-path"):
        assert HEADER.match(client.get(path).headers["server-timing"]), path


def test_a_slow_request_is_logged_and_a_fast_one_is_not(client, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        client.get(f"{API_PREFIX}/health")
    assert not [r for r in caplog.records if "slow request" in r.message]
    monkeypatch.setattr(timing, "SLOW_MS", -1.0)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        client.get(f"{API_PREFIX}/health")
    assert [r for r in caplog.records if "slow request" in r.message and "/health" in r.message]
