"""The one-time final run: only ml/eval/final.py opens the test split, it runs once, and the all-data
artifacts match what was frozen (no database needed)."""

import ast
import json
from pathlib import Path

import pandas as pd
import pytest

import ml.eval.final as final
from ml.models.chain import Chain
from ml.models.train import TARGETS, load_model, save_model
from ml.models.tune import load_params
from tests.ml.test_models import budget_model, chain_rows, revenue_model  # noqa: F401 (fixtures)

ML_DIR = Path("ml")


def _passes_final_true(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(node, ast.Call) and any(
        k.arg == "final" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
        for node in ast.walk(tree))


def test_only_the_final_run_script_passes_final_true():
    users = sorted(str(p.as_posix()) for p in ML_DIR.rglob("*.py") if _passes_final_true(p))
    assert users == ["ml/eval/final.py"]


def test_the_test_run_refuses_to_run_twice(tmp_path, monkeypatch):
    report = tmp_path / "final_test.json"
    report.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(final, "REPORT_JSON", report)
    monkeypatch.setattr(final, "corrections", lambda: pytest.fail("the test split must not be touched again"))
    with pytest.raises(SystemExit, match="already been opened"):
        final.run_test()


def test_all_data_models_need_the_test_runs_corrections(tmp_path, monkeypatch):
    monkeypatch.setattr(final, "CORRECTIONS_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="run the test first"):
        final.run_all_data(tmp_path / "final")


def test_saved_chain_reloads_identically_with_its_estimated_correction(tmp_path, revenue_model, budget_model):
    rows = chain_rows()
    save_model(budget_model, rows, out_dir=tmp_path)
    save_model(revenue_model, rows, out_dir=tmp_path, extra={"q_estimated": 0.5})
    chain = Chain.load(tmp_path)
    assert chain.q == {"given": revenue_model.q, "estimated": 0.5}
    expected = Chain(revenue_model, budget_model, {"given": revenue_model.q, "estimated": 0.5})
    for budget in (None, 40e6):
        pd.testing.assert_frame_equal(chain.predict_revenue(rows, budget), expected.predict_revenue(rows, budget))


# ---------------------------------------------------------------- the committed all-data artifacts

FINAL_METAS = {t: final.FINAL_DIR / f"{t}_meta.json" for t in TARGETS}
needs_final = pytest.mark.skipif(not all(p.exists() for p in FINAL_METAS.values()),
                                 reason="no all-data models (run `uv run python -m ml.eval.final all-data`)")


@needs_final
@pytest.mark.parametrize("target", TARGETS)
def test_all_data_models_use_the_frozen_settings_and_final_corrections(target):
    meta = json.loads(FINAL_METAS[target].read_text(encoding="utf-8"))
    corr = json.loads(final.CORRECTIONS_FILE.read_text(encoding="utf-8"))
    params, n_trees = load_params(target)
    assert meta["params"] == {**meta["params"], **params} and meta["n_trees"] == n_trees
    assert meta["q"] == corr[target]["q"]
    assert meta["trained_on"] == "films released 1960-2025"
    saved = json.loads((final.ARTIFACTS_DIR / f"{target}_meta.json").read_text(encoding="utf-8"))
    assert meta["features"] == saved["features"]  # the same features as the evaluated models
    if target == "revenue":
        assert meta["q_estimated"] == corr["revenue_estimated"]["q_used"] >= meta["q"]


needs_final_models = pytest.mark.skipif(
    not all((final.FINAL_DIR / f"{t}_p50.joblib").exists() for t in TARGETS),
    reason="all-data .joblib files not present (gitignored; run `uv run python -m ml.eval.final all-data`)")


@needs_final_models
@pytest.mark.parametrize("target", TARGETS)
def test_all_data_models_reload_identically(target):
    a, b = load_model(target, final.FINAL_DIR), load_model(target, final.FINAL_DIR)
    rows = pd.DataFrame(0.0, index=range(20), columns=a.features)
    rows["log_budget"] = 17.0
    pd.testing.assert_frame_equal(a.predict(rows), b.predict(rows))
    assert a.q == json.loads((final.FINAL_DIR / f"{target}_meta.json").read_text(encoding="utf-8"))["q"]
