"""Predictions for the API: an LRU cache in front of Predictor.predict, and compare.

    PredictionService(predictor, size)         -> one per app, shared by the thread pool
    service.predict(form)                      -> (output, cached); InvalidForm for a bad form
    service.compare(base, variants)            -> {"base", "variants": [{"prediction", "differences"}]};
                                                  InvalidForm with keys like "base.runtime", "variants.1.budget"
    service.sweep(form, field, values)         -> ({"model_version", "field", "base_value", "points": [{"value",
                                                  "budget", "revenue", "score", "revenue_mode"}]}, all cached);
                                                  InvalidForm with keys like "form.runtime", "values.3"
    merge(base, changes)                       -> a variant's form: base with the changes, null clearing a field

The cache key is the validated form (ml.features.contract.validate) as canonical JSON, so the same film
written two ways ("budget": 5e7 vs 50000000, a name with extra spaces) is one entry. Outputs are the
JSON-ready dicts predict() returns plus poster URLs for the comparables; they are never changed in place.
Compare and the sweep predict the forms the cache lacks in one Predictor.predict_many call (V1.5). The sweep
shows only the ranges, so it skips drivers and comparables; its points are cached as ranges-only entries
(key prefix RANGES) in the same LRU, and a full answer already cached serves a point too.
"""

from __future__ import annotations

import copy
import json
import threading
from collections import OrderedDict
from typing import Any

from backend.app.services.movies.posters import poster
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


RANGES = "ranges:"  # cache keys of the sweep's ranges-only answers


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

    def _lookup(self, key: str) -> dict[str, Any] | None:
        """The cached answer, marked most recently used (call with the lock held)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _run(self, cleans: list[dict[str, Any]], full: bool = True) -> list[tuple[dict[str, Any], bool]]:
        """(answer, cached) per validated form; the forms the cache lacks are predicted together, one call per
        model. full=False (the sweep) needs only the ranges: a full answer in the cache serves it, else the
        ranges are cached on their own (RANGES + the form's key). A form repeated in one call counts as cached
        after its first time, as when the forms were sent one by one."""
        keys = [json.dumps(clean, sort_keys=True, ensure_ascii=False) for clean in cleans]
        found: dict[str, dict[str, Any]] = {}
        todo: dict[str, dict[str, Any]] = {}
        with self._lock:
            for key, clean in zip(keys, cleans):
                if key in found or key in todo:
                    continue
                out = self._lookup(key) if full else self._lookup(key) or self._lookup(RANGES + key)
                if out is None:
                    todo[key] = clean
                else:
                    found[key] = out
        if todo:  # outside the lock: about 120 ms a form with explanations
            forms = list(todo.values())
            if full and len(forms) == 1:
                computed = [self.predictor.predict(forms[0])]
            else:
                computed = self.predictor.predict_many(forms, full=full)
            computed = [copy.deepcopy(out) for out in computed]
            for out in computed:
                for film in out.get("comparables", ()):
                    film["poster"] = poster(film.get("poster_path"))
            with self._lock:
                for key, out in zip(todo, computed):
                    self._cache[key if full else RANGES + key] = out
                    self._cache.move_to_end(key if full else RANGES + key)
                    found.setdefault(key, out)
                while len(self._cache) > self.size:
                    self._cache.popitem(last=False)
        results, seen = [], set()
        for key in keys:
            cached = key in seen or key not in todo
            seen.add(key)
            results.append((found[key], cached))
        with self._lock:
            self.hits += sum(cached for _, cached in results)
            self.misses += len(todo)
        return results

    def _predict_clean(self, clean: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return self._run([clean])[0]

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
        (base_out, base_cached), *rest = self._run([base_clean, *cleaned.values()])
        out = {"base": {**base_out, "cached": base_cached}, "variants": []}
        for clean, (prediction, cached) in zip(cleaned.values(), rest):
            out["variants"].append({
                "prediction": {**prediction, "cached": cached},
                "differences": {
                    "changed_fields": [k for k in clean if clean[k] != base_clean[k]],
                    **{t: _shift(t, base_out, prediction) for t in TARGETS},
                    "mode_changed": prediction["revenue"]["mode"] != base_out["revenue"]["mode"],
                },
            })
        return out

    def sweep(self, form: dict[str, Any], field: str, values: list[float]) -> tuple[dict[str, Any], bool]:
        """The same film with `field` set to each value, ranges only, the uncached points predicted together.
        -> (answer, whether the cache held every point)."""
        errors: dict[str, str] = {}
        try:
            self.clean(form)
        except InvalidForm as e:
            errors.update({f"form.{k}": message for k, message in e.errors.items()})
        for i, value in enumerate(values):  # only the swept field: the rest is the form's, reported once above
            problem = validate({field: value})[1].get(field)
            if problem:
                errors[f"values.{i}"] = problem
        if errors:
            raise InvalidForm(errors)

        results = self._run([self.clean(merge(form, {field: value})) for value in values], full=False)
        points = [{"value": value, **{t: out[t] for t in TARGETS}, "revenue_mode": out["revenue"]["mode"]}
                  for value, (out, _) in zip(values, results)]
        return ({"model_version": results[0][0]["model_version"], "field": field, "base_value": form.get(field),
                 "points": points}, all(cached for _, cached in results))

    def __len__(self) -> int:
        return len(self._cache)
