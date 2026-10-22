"""Predictions for the API: an LRU cache in front of Predictor.predict, and compare.

    PredictionService(predictor, size)         -> one per app, shared by the thread pool
    service.predict(form)                      -> (output, cached); InvalidForm for a bad form
    service.compare(base, variants)            -> {"base", "variants": [{"prediction", "differences"}]};
                                                  InvalidForm with keys like "base.runtime", "variants.1.budget"
    merge(base, changes)                       -> a variant's form: base with the changes, null clearing a field

The cache key is the validated form (ml.features.contract.validate) as canonical JSON, so the same film
written two ways ("budget": 5e7 vs 50000000, a name with extra spaces) is one entry. Outputs are the
JSON-ready dicts predict() returns plus poster URLs for the comparables; they are never changed in place.
"""

from __future__ import annotations

import copy
import json
import threading
from collections import OrderedDict
from typing import Any

from backend.app.services.posters import poster
from ml.features.contract import validate
from ml.models.train import TARGETS
from ml.predict import InvalidForm, Predictor


def merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in changes.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def _shift(target: str, base: dict[str, Any], other: dict[str, Any]) -> dict[str, float | None]:
    b, o = base[target]["middle"], other[target]["middle"]
    if target == "score":
        return {"ratio": None, "points": round(o - b, 4)}
    return {"ratio": round(o / b, 4), "points": None}


class PredictionService:
    def __init__(self, predictor: Predictor, size: int = 1000):
        self.predictor = predictor
        self.size = size
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def clean(self, form: dict[str, Any]) -> dict[str, Any]:
        clean, errors = validate(form, themes=list(self.predictor.ctx.themes))
        if errors:
            raise InvalidForm(errors)
        return clean

    def _predict_clean(self, clean: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        key = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self.hits += 1
                return self._cache[key], True
        out = copy.deepcopy(self.predictor.predict(clean))  # outside the lock: about 150 ms
        for film in out["comparables"]:
            film["poster"] = poster(film.get("poster_path"))
        with self._lock:
            self.misses += 1
            self._cache[key] = out
            self._cache.move_to_end(key)
            while len(self._cache) > self.size:
                self._cache.popitem(last=False)
        return out, False

    def predict(self, form: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return self._predict_clean(self.clean(form))

    def compare(self, base: dict[str, Any], variants: list[dict[str, Any]]) -> dict[str, Any]:
        forms = {"base": base, **{f"variants.{i}": merge(base, changes) for i, changes in enumerate(variants)}}
        cleaned, errors = {}, {}
        for where, form in forms.items():  # check every form first, so one response lists every problem
            try:
                cleaned[where] = self.clean(form)
            except InvalidForm as e:
                errors.update({f"{where}.{field}": message for field, message in e.errors.items()})
        if errors:
            raise InvalidForm(errors)

        base_clean = cleaned.pop("base")
        base_out, base_cached = self._predict_clean(base_clean)
        out = {"base": {**base_out, "cached": base_cached}, "variants": []}
        for clean in cleaned.values():
            prediction, cached = self._predict_clean(clean)
            out["variants"].append({
                "prediction": {**prediction, "cached": cached},
                "differences": {
                    "changed_fields": [k for k in clean if clean[k] != base_clean[k]],
                    **{t: _shift(t, base_out, prediction) for t in TARGETS},
                    "mode_changed": prediction["revenue"]["mode"] != base_out["revenue"]["mode"],
                },
            })
        return out

    def __len__(self) -> int:
        return len(self._cache)
