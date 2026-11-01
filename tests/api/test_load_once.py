"""The models are loaded once, at startup (V1.5): later requests never call the loader again."""

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from ml.predict import Predictor
from tests.api.test_api import PREDICT
from tests.ml.test_eval import db  # noqa: F401 (fixture)
from tests.ml.test_models import (budget_model, budget_rows, revenue_model, revenue_rows,  # noqa: F401 (fixtures)
                                  score_model, score_rows)
from tests.ml.test_predict import form as film_form
from tests.ml.test_predict import predictor  # noqa: F401 (fixture)


def test_predictions_do_not_reload_the_models(db, predictor, monkeypatch):  # noqa: F811
    calls = []

    def load(*args, **kwargs):
        calls.append(args)
        return predictor

    monkeypatch.setattr(Predictor, "load", load)
    with TestClient(create_app(Settings(db_path=db / "movies.db"))) as client:
        assert len(calls) == 1  # at startup
        for runtime in (100, 110):
            assert client.post(PREDICT, json=film_form(runtime=runtime)).status_code == 200
        assert client.app.state.predictor is predictor
    assert len(calls) == 1
