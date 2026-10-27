"""Warm up the live app before a demo (Day 16): wake it, then fill its prediction cache with the demo's requests.

    uv run python scripts/warmup.py                                  # the live site (make warmup)
    uv run python scripts/warmup.py --base-url http://localhost:8000 # local docker compose

Run it about 3 minutes before the demo. On Render Free the service sleeps after 15 idle minutes (waking takes
about 84 s), a prediction takes about 2 s and the 12-month sweep about 25 s. The API caches each prediction by
its validated form (1,000 entries, kept until the service sleeps or restarts), so a click that sends a form
warmed here answers at once. The service then stays awake for 15 minutes after the demo's last click.

What it sends, for each of the three example forms (tests/golden/forms.json, which the form page's example
buttons send exactly):
- POST /predict, the results page;
- POST /predict/compare with the compare page's presets that apply to it (holiday release, double the budget,
  unknown cast, PG-13 instead of R; "make it a franchise" needs a picked name, so it isn't warmed), at most
  3 variants a call like the page;
- POST /predict/sweep over the 12 months.
Then the Career section of Christopher Nolan (directing) and Tom Hanks (acting), whose model films are
predictions too. That is 13 requests, under the 30-a-minute limit. """

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

LIVE = "https://movie-prediction-2f1b0265282c.onrender.com"
API = "/api/v1"
FORMS = Path(__file__).resolve().parents[1] / "tests" / "golden" / "forms.json"
CAREERS = ((525, "directing", "Christopher Nolan"), (31, "acting", "Tom Hanks"))
MAX_VARIANTS = 3  # frontend/src/compare/variants.ts
MAX_BUDGET = 1_000_000_000  # ml/features/contract.py; the compare page's "double the budget" checks it


def presets(form: dict[str, Any]) -> list[dict[str, Any]]:
    """The compare page's preset changes for this form, as frontend/src/compare/variants.ts makes them."""
    out = []
    if form["release_month"] != 12:
        out.append({"release_month": 12})
    if form.get("budget") is not None and form["budget"] * 2 <= MAX_BUDGET:
        out.append({"budget": form["budget"] * 2})
    if any(isinstance(a, int) for a in form["actors"]):
        out.append({"actors": [{"name": f"New actor {i + 1}"} for i in range(len(form["actors"]))]})
    if form["certification"] == "R":
        out.append({"certification": "PG-13"})
    return out


def wake(client: httpx.Client, wait: float) -> float:
    start = time.perf_counter()
    while True:
        try:
            if client.get(f"{API}/health", timeout=wait).status_code == 200:
                return time.perf_counter() - start
        except httpx.HTTPError:
            pass
        if time.perf_counter() - start > wait:
            raise SystemExit(f"No answer from /health after {wait:.0f} s.")
        time.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=LIVE)
    parser.add_argument("--wait", type=float, default=240, help="seconds to wait for the wake-up")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    client = httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120)
    print(f"Warming up {args.base_url}")
    print(f"  awake after {wake(client, args.wait):.0f} s")

    failed = 0

    def call(name: str, method: str, path: str, **kw: Any) -> None:
        nonlocal failed
        start = time.perf_counter()
        r = client.request(method, API + path, **kw)
        ok = r.status_code == 200
        failed += not ok
        print(f"  {'ok' if ok else 'FAIL'}  {name:<46} {time.perf_counter() - start:6.1f} s"
              + ("" if ok else f"  {r.status_code} {r.text[:120]}"))

    for name, form in json.loads(FORMS.read_text(encoding="utf-8"))["forms"].items():
        call(f"predict {name}", "POST", "/predict", json=form)
        changes = presets(form)
        for i in range(0, len(changes), MAX_VARIANTS):
            chunk = changes[i:i + MAX_VARIANTS]
            call(f"compare {name} ({', '.join(k for c in chunk for k in c)})", "POST", "/predict/compare",
                 json={"base": form, "variants": chunk})
        call(f"sweep {name} (12 months)", "POST", "/predict/sweep",
             json={"form": form, "field": "release_month", "values": list(range(1, 13))})
    for person, role, who in CAREERS:
        call(f"career {who}", "GET", f"/people/{person}/career", params={"role": role})
        call(f"career model {who}", "GET", f"/people/{person}/career/model", params={"role": role})

    cache = client.get(f"{API}/health").json()["prediction_cache"]
    print(f"Done: {cache['size']} predictions cached." + (f" {failed} request(s) FAILED." if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
