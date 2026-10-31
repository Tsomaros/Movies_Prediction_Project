"""Sentry on the backend (backend/app/services/platform/monitoring.py, Day 15), with events kept in memory, offline."""

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from backend.app import main
from backend.app.main import create_app
from backend.app.services.platform import monitoring
from backend.app.settings import API_PREFIX, Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

DSN = "https://public@o0.ingest.sentry.io/0"  # never contacted: the transport keeps the events


class Kept(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []

    def capture_envelope(self, envelope) -> None:  # type: ignore[no-untyped-def]
        self.events += [item.payload.json for item in envelope.items if item.type == "event"]


@pytest.fixture
def sentry(db, monkeypatch):
    kept = Kept()  # the real start_sentry, with the in-memory transport
    monkeypatch.setattr(main, "start_sentry", lambda dsn, release=None: monitoring.start_sentry(dsn, release, kept))
    app = create_app(Settings(db_path=db / "movies.db", sentry_dsn=DSN, release="abc123"), predictor=object())

    @app.get(f"{API_PREFIX}/boom")
    def boom() -> None:
        raise RuntimeError("test error")

    with TestClient(app, raise_server_exceptions=False) as c:
        c.kept = kept
        yield c
    sentry_sdk.init()  # off again for the other tests


def test_an_unhandled_error_is_reported_without_the_cookie_or_ip(sentry):
    r = sentry.get(f"{API_PREFIX}/boom", headers={"Cookie": "mp_session=secret-token",
                                                  "X-Forwarded-For": "1.2.3.4"})
    assert r.status_code == 500
    sentry_sdk.flush()
    [event] = sentry.kept.events
    assert event["exception"]["values"][-1]["value"] == "test error"
    assert event["release"] == "abc123"
    text = str(event)
    assert "secret-token" not in text and "1.2.3.4" not in text
    assert "cookies" not in event.get("request", {})


def test_4xx_answers_are_not_reported(sentry):
    assert sentry.get(f"{API_PREFIX}/nothing-here").status_code == 404
    sentry_sdk.flush()
    assert sentry.kept.events == []
