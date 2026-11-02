"""Save the model outputs the speed pass must not change (V1.5, gate G9).

    uv run python scripts/perf_snapshot.py            # rewrites tests/fixtures/perf_snapshot.json
    from perf_snapshot import build_snapshot           # what perf_check.py compares with

The three golden forms (tests/golden/forms.json: franchise_blockbuster = the superhero sequel, small_drama =
the small indie drama, unknown_cast = the film with no known cast) go through POST /predict; the small drama
through POST /predict/compare with three one-field variants (budget, runtime, release month) and through
POST /predict/sweep over the 12 release months. They run on the real models and database, through the real app
(TestClient on create_app), so the JSON is what the API sends. Fields that are not model outputs are stripped
(`cached` flags, which depend on the cache's state). Nothing else in these answers depends on the clock: a
creator's film is judged at the 1st of its release month. JSON is written with sorted keys.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from dataclasses import replace
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # run as a script: the repository root is not on the path yet

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import create_app  # noqa: E402
from backend.app.settings import API_PREFIX, Settings  # noqa: E402

SNAPSHOT = ROOT / "tests/fixtures/perf_snapshot.json"
FORMS = ROOT / "tests/golden/forms.json"
VOLATILE = {"cached"}  # not model output: whether the cache already held the answer
VARIANTS = [{"budget": 20_000_000}, {"runtime": 130}, {"release_month": 6}]


def strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def build_snapshot() -> dict[str, Any]:
    forms = json.loads(FORMS.read_text(encoding="utf-8"))["forms"]
    out: dict[str, Any] = {"predict": {}}
    settings = replace(Settings.from_env(), user_database_url=None)  # no accounts database, so no pool or worker thread
    with TestClient(create_app(settings)) as client:
        def post(path: str, body: Any) -> Any:
            r = client.post(API_PREFIX + path, json=body)
            r.raise_for_status()
            return strip(r.json())

        for name, form in forms.items():
            out["predict"][name] = post("/predict", form)
        out["compare"] = post("/predict/compare", {"base": forms["small_drama"], "variants": VARIANTS})
        out["sweep"] = post("/predict/sweep", {"form": forms["small_drama"], "field": "release_month",
                                               "values": list(range(1, 13))})
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    snapshot = build_snapshot()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)} ({SNAPSHOT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
