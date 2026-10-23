"""ml/eval/model_card.py: the committed model card is current and copies the reports' numbers exactly.

Offline: it reads only committed files (reports/*.json, including metrics.json, and ml/artifacts/final/manifest.json)."""

import json
import math

from ml.eval.model_card import CARD_FILE, FINAL_DIR, REPORTS, TARGETS, UNCERTAINTY_FRACTION, build


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fresh():
    return build(read(REPORTS / "final_test.json"), read(REPORTS / "audit_metrics.json"), read(FINAL_DIR / "manifest.json"),
                 read(REPORTS / "metrics.json"))


def test_the_committed_card_is_current():
    """Fails after the reports or the models change: rerun `uv run python -m ml.eval.model_card`."""
    assert read(FINAL_DIR / CARD_FILE) == fresh()


def test_the_card_belongs_to_the_served_models():
    manifest = read(FINAL_DIR / "manifest.json")
    card = read(FINAL_DIR / CARD_FILE)
    assert card["model_version"] == manifest["version"]
    assert card["training"]["years"] == "1960-2025"
    assert card["training"]["films"] == {t: m["train_films"] for t, m in manifest["models"].items()}


def test_the_numbers_are_the_reports_numbers():
    card = fresh()
    test = {m["name"]: m["test"] for m in read(REPORTS / "final_test.json")["results"]["revenue"]}
    revenue = card["test"]["targets"]["revenue"]
    assert revenue["model"]["coverage"] == round(test["LightGBM (tuned, calibrated)"]["coverage"], 4)
    assert revenue["baseline"]["mae_log"] == round(test["B2 budget x genre multiple"]["mae_log"], 4)
    assert revenue["model"]["typical_factor"] == round(math.exp(test["LightGBM (tuned, calibrated)"]["mae_log"]), 2)
    holdout = read(REPORTS / "audit_metrics.json")["holdout"]
    assert card["holdout"]["targets"]["score"]["model"]["coverage"] == round(holdout["score"]["models"]["LightGBM app"]["coverage"], 4)
    assert card["holdout"]["targets"]["budget"]["films"] == holdout["budget"]["models"]["LightGBM app"]["n"]
    assert set(card["test"]["targets"]) == set(card["holdout"]["targets"]) == set(TARGETS)


def test_the_uncertainty_thresholds_come_from_the_validation_ranges():
    card = fresh()
    u = card["uncertainty"]
    validation = {t: {m["name"]: m["validation"] for m in ms} for t, ms in read(REPORTS / "metrics.json").items()}
    revenue = validation["revenue"]["LightGBM (tuned, calibrated)"]["width"]
    assert u["revenue"]["ratio"] == round(revenue ** UNCERTAINTY_FRACTION, 4)
    assert u["score"]["points"] == round(UNCERTAINTY_FRACTION * validation["score"]["LightGBM (tuned, calibrated)"]["width"], 4)
    assert set(u) == {"fraction", "years", *TARGETS}
    assert 1.1 < u["budget"]["ratio"] < u["revenue"]["ratio"] < u["revenue_estimated"]["ratio"] < 1.6  # a tenth of a wide range
    assert 0.1 < u["score"]["points"] < 0.3
