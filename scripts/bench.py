"""Latency benchmark for a running API, and the speed pass's gates G1-G4 (V1.5).

    uv run python scripts/bench.py --base-url http://localhost:8000 --out docs/perf/baseline-local.md
    uv run python scripts/bench.py --base-url http://localhost:8000 --throttled --out docs/perf/baseline-docker.md

Start the server with the per-IP limits raised (the defaults answer 429 after 30 predictions a minute):
    RATE_LIMIT=1000000 RATE_LIMIT_READ=1000000 uv run uvicorn backend.app.main:app
The limits are only raised for the benchmark's server, never in the code's defaults.

Requests (spec 3.1), each sent `--repeats` times (default 20) after 2 warm-up requests, one at a time:
- POST /predict for the three golden forms (tests/golden/forms.json), POST /predict/compare (the small drama
  and three one-field variants), POST /predict/sweep (the small drama over 12 release months);
- reads: /movies with filters, /movies/{id}, /movies?q= (search), /people autocomplete (actor and director),
  /companies autocomplete, /people/{id} for Tom Hanks (31) and Christopher Nolan (525).

The prediction cache turns identical repeats into hits, so each predict, compare and sweep row is measured twice:
- "miss": every request changes the form's runtime to a value not sent before in this run (random, 41-300 min, never a golden form's own).
  Runtime is a normal model input with the same cost whatever its value, and it does not depend on the clock;
  the compare variants change other fields (budget, month, studio) so they cannot overwrite it. The predict and
  compare answers carry `cached`: a miss row where any answer was cached is reported as an error.
- "hit": the same request again (what a repeated click costs).
The gates use the miss rows and the slowest endpoint of each group:
G1 POST /predict p95 <= 400 ms (local run), G2 the same <= 1.5 s, G3 compare and sweep <= 2.5 s, G4 every read
endpoint <= 300 ms (G2-G4 on a throttled run: `--throttled`, Docker with --cpus 0.1 --memory 512m).
A gate that does not apply to this kind of run is shown as "not measured".

The report is Markdown: p50, p95 and max in milliseconds, plus the median Server-Timing the server reported.
Only the standard library and httpx are needed. Exit status 1 if a request fails or a measured gate fails.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "/api/v1"
FORMS = ROOT / "tests/golden/forms.json"
WARMUP = 2
RUNTIMES = list(range(41, 301))
COMPARE_VARIANTS = [{"budget": 20_000_000}, {"release_month": 6}, {"companies": [33]}]
GATES = {"G1": 400, "G2": 1500, "G3": 2500, "G4": 300}  # p95 limits in ms

Request = tuple[str, str, dict[str, Any]]  # method, path, JSON body (POST) or query (GET)


@dataclass
class Row:
    name: str
    kind: str  # "predict", "compare", "sweep" or "read"
    mode: str  # "miss", "hit" or "-"
    ms: list[float] = field(default_factory=list)
    server_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def pct(self, p: float) -> float:
        xs = sorted(self.ms)
        return xs[min(len(xs) - 1, max(0, round(p * len(xs) + 0.5) - 1))] if xs else float("nan")


def timed(client: httpx.Client, request: Request) -> tuple[float, float | None, httpx.Response]:
    method, path, payload = request
    start = time.perf_counter()
    r = client.post(API + path, json=payload) if method == "POST" else client.get(API + path, params=payload)
    ms = (time.perf_counter() - start) * 1000
    header = r.headers.get("server-timing", "")
    return ms, float(header.split("=")[1]) if header.startswith("app;dur=") else None, r


def run_row(client: httpx.Client, row: Row, make: Callable[[], Request], repeats: int,
            check: Callable[[Any], str | None] | None = None) -> None:
    for i in range(WARMUP + repeats):
        ms, server, r = timed(client, make())
        problem = None if r.status_code == 200 else f"HTTP {r.status_code}: {r.text[:120]}"
        if problem is None and check is not None and i >= WARMUP:  # the warm-up may be answered either way
            problem = check(r.json())
        if problem:
            row.errors.append(problem)
            continue
        if i >= WARMUP:
            row.ms.append(ms)
            if server is not None:
                row.server_ms.append(server)
    print(f"  {row.name:42s} {row.mode:4s} p50 {row.pct(0.5):8.1f}  p95 {row.pct(0.95):8.1f}  "
          f"max {max(row.ms, default=float('nan')):8.1f}{'  ERRORS ' + str(len(row.errors)) if row.errors else ''}",
          flush=True)


def not_cached(body: Any) -> str | None:
    flags = [body["cached"]] if "cached" in body else [body["base"]["cached"],
                                                      *[v["prediction"]["cached"] for v in body["variants"]]]
    return None if not any(flags) else f"a miss row was answered from the cache: {flags}"


def measure(client: httpx.Client, repeats: int) -> list[Row]:
    forms = json.loads(FORMS.read_text(encoding="utf-8"))["forms"]
    total = WARMUP + repeats
    free = [r for r in RUNTIMES if r not in {f.get("runtime") for f in forms.values()}]  # a form's own runtime is a hit
    rows: list[Row] = []

    if 5 * total > len(free):  # one pool for the whole run, so no two miss rows ever send the same runtime
        raise SystemExit(f"--repeats is at most {len(free) // 5 - WARMUP}")
    pool = random.sample(free, 5 * total)

    def runtimes() -> Callable[[], int]:
        return pool.pop

    print("predict, compare, sweep (miss = a new runtime each time, hit = the same request)", flush=True)
    base = forms["small_drama"]
    months = list(range(1, 13))
    for name, form in forms.items():
        nxt = runtimes()
        row = Row(f"POST /predict ({name})", "predict", "miss")
        run_row(client, row, lambda f=form, n=nxt: ("POST", "/predict", {**f, "runtime": n()}), repeats, not_cached)
        rows.append(row)
        row = Row(f"POST /predict ({name})", "predict", "hit")
        run_row(client, row, lambda f=form: ("POST", "/predict", f), repeats)
        rows.append(row)

    nxt = runtimes()
    row = Row("POST /predict/compare (3 variants)", "compare", "miss")
    run_row(client, row, lambda n=nxt: ("POST", "/predict/compare", {"base": {**base, "runtime": n()},
                                                                      "variants": COMPARE_VARIANTS}), repeats, not_cached)
    rows.append(row)
    row = Row("POST /predict/compare (3 variants)", "compare", "hit")
    run_row(client, row, lambda: ("POST", "/predict/compare", {"base": base, "variants": COMPARE_VARIANTS}), repeats)
    rows.append(row)

    nxt = runtimes()
    row = Row("POST /predict/sweep (12 months)", "sweep", "miss")
    run_row(client, row, lambda n=nxt: ("POST", "/predict/sweep", {"form": {**base, "runtime": n()},
                                                                    "field": "release_month", "values": months}), repeats)
    rows.append(row)
    row = Row("POST /predict/sweep (12 months)", "sweep", "hit")
    run_row(client, row, lambda: ("POST", "/predict/sweep", {"form": base, "field": "release_month", "values": months}),
            repeats)
    rows.append(row)

    print("reads", flush=True)
    reads: list[tuple[str, str, dict[str, Any]]] = [
        ("GET /movies (genre, years, sort=score)", "/movies", {"genre": "Drama", "year_from": 2000, "year_to": 2020,
                                                               "sort": "score", "page_size": 24}),
        ("GET /movies (language, score_min, page 2)", "/movies", {"language": "fr", "score_min": 7, "sort": "newest",
                                                                  "page": 2}),
        ("GET /movies (home row: popularity)", "/movies", {"sort": "popularity", "page_size": 12}),
        ("GET /movies/299536 (detail)", "/movies/299536", {}),
        ("GET /movies?q=avengers infinity (search)", "/movies", {"q": "avengers infinity"}),
        ("GET /movies?q=the (search, common word)", "/movies", {"q": "the"}),
        ("GET /people?role=actor&q=tom ha", "/people", {"role": "actor", "q": "tom ha"}),
        ("GET /people?role=director&q=nol", "/people", {"role": "director", "q": "nol"}),
        ("GET /companies?q=univ", "/companies", {"q": "univ"}),
        ("GET /people/31 (Tom Hanks)", "/people/31", {}),
        ("GET /people/525 (Christopher Nolan)", "/people/525", {}),
    ]
    for name, path, params in reads:
        row = Row(name, "read", "-")
        run_row(client, row, lambda p=path, q=params: ("GET", p, q), repeats)
        rows.append(row)
    return rows


def gates(rows: list[Row], throttled: bool) -> list[tuple[str, str, float | None, bool | None]]:
    """(gate, target, the slowest p95 in ms or None, passed or None when not measured)."""
    def worst(kinds: tuple[str, ...], mode: str | None = None) -> float | None:
        picked = [r for r in rows if r.kind in kinds and (mode is None or r.mode == mode)]
        if not picked:
            return None
        if any(r.errors or not r.ms for r in picked):
            return float("inf")  # a failed request fails the gate
        return max(r.pct(0.95) for r in picked)

    def verdict(gate: str, what: str, value: float | None, applies: bool) -> tuple[str, str, float | None, bool | None]:
        if not applies or value is None:
            return gate, what, None, None
        return gate, what, value, value <= GATES[gate]

    return [
        verdict("G1", "POST /predict p95, miss, local <= 400 ms", worst(("predict",), "miss"), not throttled),
        verdict("G2", "POST /predict p95, miss, throttled <= 1.5 s", worst(("predict",), "miss"), throttled),
        verdict("G3", "compare and sweep p95, miss, throttled <= 2.5 s", worst(("compare", "sweep"), "miss"), throttled),
        verdict("G4", "read endpoints p95, throttled <= 300 ms", worst(("read",)), throttled),
    ]


def report(rows: list[Row], base_url: str, throttled: bool, repeats: int) -> str:
    kind = "Throttled run (Docker, --cpus 0.1 --memory 512m)" if throttled else "Local run (unthrottled)"
    lines = [f"# Benchmark of {base_url}", "",
             f"{kind}; {repeats} repeats after {WARMUP} warm-up requests each, one request at a time; "
             f"{time.strftime('%Y-%m-%d %H:%M')}.", "",
             "Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new "
             "runtime each time), `hit` = the same request again. The gates use the miss rows.", "",
             "| Endpoint | Cache | p50 | p95 | max | server p50 | errors |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        server = f"{statistics.median(r.server_ms):.1f}" if r.server_ms else "-"
        lines.append(f"| {r.name} | {r.mode} | {r.pct(0.5):.1f} | {r.pct(0.95):.1f} | "
                     f"{max(r.ms, default=float('nan')):.1f} | {server} | {len(r.errors)} |")
    lines += ["", "## Gates", "", "| Gate | Target | Slowest p95 | Result |", "|---|---|---:|---|"]
    for gate, what, value, ok in gates(rows, throttled):
        shown = "-" if value is None else "error" if value == float("inf") else f"{value:.0f} ms"
        lines.append(f"| {gate} | {what} | {shown} | "
                     f"{'not measured on this run' if ok is None else 'PASS' if ok else 'FAIL'} |")
    failed = [r for r in rows if r.errors]
    if failed:
        lines += ["", "## Errors", ""] + [f"- {r.name} ({r.mode}): {r.errors[0]}" for r in failed]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark a running movie prediction API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--out", help="write the Markdown report here (it is always printed too)")
    parser.add_argument("--throttled", action="store_true",
                        help="the server runs with Render-like limits: gates G2-G4 apply, not G1")
    parser.add_argument("--timeout", type=float, default=600, help="seconds per request")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    print(f"Benchmark of {args.base_url}", flush=True)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        rows = measure(client, args.repeats)
    text = report(rows, args.base_url, args.throttled, args.repeats)
    print("\n" + text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    bad = any(r.errors for r in rows) or any(ok is False for *_, ok in gates(rows, args.throttled))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
