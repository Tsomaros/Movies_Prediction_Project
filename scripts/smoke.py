"""Smoke test for a running API: the same checks against local Docker and the live URL (Day 14).

    uv run python scripts/smoke.py                                   # http://localhost:8000 (make smoke)
    uv run python scripts/smoke.py --base-url https://example.onrender.com --wait 180
    uv run python scripts/smoke.py --web-url http://localhost:8080   # also the frontend (make smoke does this)

Checks, each printed as one line with its time:
- /health answers "ok" with the expected model version (from ml/artifacts/final/manifest.json when it is
  there, or --expect-version) and a database with films;
- the three golden forms (tests/golden/forms.json) through POST /predict: ordered ranges, the revenue mode,
  the warning codes and each middle equal to tests/golden/predictions.json to 6 significant figures;
- POST /predict/compare with two variants, the 12-month POST /predict/sweep, and a bad form that must get
  the readable 422;
- the /health `fresh` block and the New arrivals queries (V1.2: `when=released` and `when=upcoming`);
- search, the box-office sort and the score filter, a movie page, autocomplete and /meta/options on the real data;
- a person page (Day 14.6): the first actor found for "hanks", with films and a TMDB photo, and a director's
  page opening on directing (Day 14.7); his career forecast and model films, and Nolan's genre chips (Day 14.8);
- the header's people search (V1.1): /people/search?q=hanks finds Tom Hanks first, with counts per role;
- /model-card belongs to the served models and has the 2019+ test and the 2026 holdout;
- with --web-url, the frontend: the start page, its two poster collages, its script bundle (cached for a year), a deep link served
  as the app (/predict/..., /people/31 and /people?q=hanks), and /api/v1/health and /meta/options through the
  frontend's proxy.

It waits up to --wait seconds for /health first (a container starting, or a free host waking up), and
exits with status 1 if any check fails. Only the standard library and httpx are needed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx

GOLDEN = Path("tests/golden")
MANIFEST = Path("ml/artifacts/final/manifest.json")
API = "/api/v1"
TARGETS = ("budget", "revenue", "score")


# ---------------------------------------------------------------- checks


class Smoke:
    def __init__(self, base_url: str, timeout: float = 120.0):  # the live sweep takes about 25 s warm
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self.failures = 0

    def check(self, name: str, run: Callable[[], str | None]) -> None:
        start = time.perf_counter()
        try:
            note = run() or ""
            mark = "ok  "
        except Exception as e:  # noqa: BLE001 (any problem is a failed check, reported and counted)
            note, mark = f"{type(e).__name__}: {e}", "FAIL"
            self.failures += 1
        print(f"{mark} {name:42s} {(time.perf_counter() - start) * 1000:7.0f} ms  {note}", flush=True)

    def get(self, path: str, **params: Any) -> Any:
        r = self.client.get(API + path, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: Any, expect: int = 200) -> Any:
        r = self.client.post(API + path, json=body)
        assert r.status_code == expect, f"status {r.status_code}, expected {expect}: {r.text[:200]}"
        return r.json()

    def wait(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while True:
            try:
                if self.client.get(API + "/health").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                raise SystemExit(f"no healthy API at {self.client.base_url} after {seconds:.0f} s")
            time.sleep(2)


def web_checks(s: Smoke, web_url: str, expected_version: str | None) -> None:
    """The app: the server sends the app and its bundle, sends any route to the app, and answers /api on the same origin."""
    web = httpx.Client(base_url=web_url.rstrip("/"), timeout=30)
    page: dict[str, str] = {}

    def start() -> str:
        r = web.get("/")
        r.raise_for_status()
        assert "text/html" in r.headers["content-type"], r.headers["content-type"]
        assert '<div id="root">' in r.text and "<title>Movie Prediction</title>" in r.text, r.text[:200]
        page["html"] = r.text
        return f"{len(r.content):,} bytes, cache: {r.headers.get('cache-control')}"

    s.check(f"GET {web_url}/ (start page)", start)

    for name in ("movies", "series"):
        def collage(name: str = name) -> str:
            r = web.get(f"/collages/{name}.webp")
            r.raise_for_status()
            assert r.headers["content-type"] == "image/webp", r.headers["content-type"]
            assert 10_000 < len(r.content) < 300_000, len(r.content)
            return f"{len(r.content):,} bytes"

        s.check(f"GET /collages/{name}.webp (start page)", collage)

    def bundle() -> str:
        found = re.search(r'src="(/assets/[^"]+\.js)"', page.get("html", ""))
        assert found, "no script bundle in the start page"
        r = web.get(found.group(1))
        r.raise_for_status()
        assert "javascript" in r.headers["content-type"], r.headers["content-type"]
        assert "immutable" in r.headers.get("cache-control", ""), r.headers.get("cache-control")
        return f"{found.group(1)}: {len(r.content):,} bytes ({r.headers.get('content-encoding', 'not compressed')})"

    s.check("GET the script bundle", bundle)

    def deep_link() -> str:
        r = web.get("/predict/result")
        r.raise_for_status()
        assert '<div id="root">' in r.text, "a client-side route didn't get the app"
        return "served the app"

    s.check("GET /predict/result (client-side route)", deep_link)

    def person_page() -> str:
        r = web.get("/people/31")
        r.raise_for_status()
        assert '<div id="root">' in r.text, "the person route didn't get the app"
        return "served the app"

    s.check("GET /people/31 (client-side route)", person_page)

    def people_results() -> str:
        r = web.get("/people", params={"q": "hanks"})
        r.raise_for_status()
        assert '<div id="root">' in r.text, "the people results route didn't get the app"
        return "served the app"

    s.check("GET /people?q=hanks (client-side route)", people_results)

    def proxied() -> str:
        h = web.get(API + "/health").json()
        assert h["status"] == "ok" and (expected_version is None or h["model_version"] == expected_version), h
        o = web.get(API + "/meta/options").json()
        assert len(o["fields"]) == 14, len(o["fields"])
        return f"model {h['model_version']} through the proxy"

    s.check("GET /api/v1 through the frontend", proxied)


def six(x: float) -> float:
    return float(f"{x:.6g}")


# ---------------------------------------------------------------- the CLI


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a running movie prediction API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--wait", type=float, default=120, help="seconds to wait for /health first")
    parser.add_argument("--expect-version", help="model version /health must report (default: the local manifest's)")
    parser.add_argument("--web-url", help="also check the frontend served here (e.g. http://localhost:8080)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    expected_version = args.expect_version or (json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
                                               if MANIFEST.exists() else None)
    forms = json.loads((GOLDEN / "forms.json").read_text(encoding="utf-8"))["forms"]
    golden = json.loads((GOLDEN / "predictions.json").read_text(encoding="utf-8"))
    s = Smoke(args.base_url)
    print(f"Smoke test of {args.base_url}")
    s.wait(args.wait)

    def health() -> str:
        h = s.get("/health")
        assert h["status"] == "ok", h
        assert expected_version is None or h["model_version"] == expected_version, \
            f"model {h['model_version']}, expected {expected_version}"
        assert h["database"]["films"] > 0
        assert set(h["fresh"]) == {"refreshed_at", "films"}, h.get("fresh")  # V1.2: the refresh's block (null before the first one)
        fresh = f", fresh {h['fresh']['films']} films" if h["fresh"]["films"] is not None else ", fresh not built yet"
        return f"model {h['model_version']}, {h['database']['films']:,} films, loaded in {h['load_seconds']} s{fresh}"

    s.check("GET /health", health)

    for name, form in forms.items():
        def predict(name=name, form=form) -> str:
            out, want = s.post("/predict", form), golden[name]
            for t in TARGETS:
                assert out[t]["low"] <= out[t]["middle"] <= out[t]["high"], f"{t} range not ordered"
                assert six(out[t]["middle"]) == want["ranges"][t]["middle"], \
                    f"{t} middle {six(out[t]['middle'])}, golden {want['ranges'][t]['middle']}"
            assert out["revenue"]["mode"] == want["ranges"]["revenue"]["mode"]
            assert [w["code"] for w in out["warnings"]] == want["warnings"]
            return f"revenue {out['revenue']['text']}, score {out['score']['text']}"

        s.check(f"POST /predict ({name})", predict)

    def compare() -> str:
        out = s.post("/predict/compare", {"base": forms["small_drama"],
                                          "variants": [{"budget": 20_000_000}, {"companies": [33]}]})
        changed = [v["differences"]["changed_fields"] for v in out["variants"]]
        assert changed == [["budget"], ["companies"]], changed
        return f"revenue x{out['variants'][1]['differences']['revenue']['ratio']} with Universal"

    s.check("POST /predict/compare", compare)

    def sweep() -> str:
        out = s.post("/predict/sweep", {"form": forms["small_drama"], "field": "release_month",
                                        "values": list(range(1, 13))})
        assert [p["value"] for p in out["points"]] == list(range(1, 13)), out["points"][:1]
        best = max(out["points"], key=lambda p: p["revenue"]["middle"])
        return f"best month {best['value']:.0f}: revenue {best['revenue']['middle_text']}"

    s.check("POST /predict/sweep (12 months)", sweep)

    def bad_form() -> str:
        body = s.post("/predict", {**forms["small_drama"], "runtime": 5}, expect=422)
        assert body["errors"] == {"runtime": "must be between 40 and 300"}, body
        return "runtime: must be between 40 and 300"

    s.check("POST /predict (bad form -> 422)", bad_form)

    def search() -> str:
        found = s.get("/movies", q="avengers infinity")
        assert found["total"] > 0 and found["items"][0]["id"] == 299536, found["items"][:1]
        return f"{found['total']} found, first: {found['items'][0]['title']}"

    s.check("GET /movies?q=avengers infinity", search)

    def browse() -> str:
        biggest = s.get("/movies", sort="revenue", page_size=3)["items"]
        assert biggest[0]["revenue_2025"] >= biggest[1]["revenue_2025"] > 0, biggest[:2]
        top = s.get("/movies", score_min=9, page_size=1)
        assert top["total"] > 0 and top["items"][0]["score"] >= 9
        return f"biggest: {biggest[0]['title']}; {top['total']:,} films scored 9+ (any votes)"

    s.check("GET /movies?sort=revenue, ?score_min=9", browse)

    def movie() -> str:
        m = s.get("/movies/299536")
        assert m["title"] == "Avengers: Infinity War" and len(m["similar"]) == 6
        assert 299536 not in [f["id"] for f in m["similar"]]
        return f"similar: {', '.join(f['title'] for f in m['similar'][:3])}..."

    s.check("GET /movies/299536", movie)

    def new_arrivals() -> str:
        out = s.get("/movies", when="released", sort="newest", page_size=12)
        assert out["page_size"] == 12 and len(out["items"]) <= 12 and all(f["release_date"] for f in out["items"]), out["page_size"]
        dates = [f["release_date"] for f in out["items"]]
        assert dates == sorted(dates, reverse=True), dates  # newest first, and only the window's films
        soon = s.get("/movies", when="upcoming", sort="soonest", page_size=12)
        return f"{out['total']} just released, {soon['total']} coming soon"

    s.check("GET /movies?when=released|upcoming (V1.2)", new_arrivals)

    def people() -> str:
        found = s.get("/people", role="actor", q="tom ha")
        assert found[0]["name"] == "Tom Hanks", found[:1]
        return ", ".join(f"{p['name']} ({p['n_films']})" for p in found[:3])

    s.check("GET /people?role=actor&q=tom ha", people)

    def person() -> str:
        first = s.get("/people", role="actor", q="hanks")[0]
        p = s.get(f"/people/{first['id']}")
        acting = next(r for r in p["roles"] if r["role"] == "acting")
        assert p["name"] == "Tom Hanks" and p["main_role"] == "acting" and p["photo"], (p["name"], p["photo"])
        assert acting["films"] and acting["stats"]["film_count"] == len(acting["films"]), acting["stats"]
        nolan = s.get("/people/525")
        assert nolan["main_role"] == "directing" and nolan["photo"], (nolan["main_role"], nolan["photo"])
        return f"{p['name']}: {len(acting['films'])} films, known for {first['known_for']}; Nolan opens on directing"

    s.check("GET /people/{id} (the first actor for hanks)", person)

    def people_search() -> str:
        found = s.get("/people/search", q="hanks")
        assert found["total"] >= 1 and found["results"][0]["name"] == "Tom Hanks", found["results"][:1]
        assert found["role_counts"]["all"] == found["total"] >= found["role_counts"]["writer"], found["role_counts"]
        return f"{found['total']} people, first {found['results'][0]['name']}; counts {found['role_counts']}"

    s.check("GET /people/search?q=hanks (V1.1)", people_search)

    def career() -> str:
        first = s.get("/people", role="actor", q="hanks")[0]
        c = s.get(f"/people/{first['id']}/career")
        f = c["forecast"]
        assert c["role"] == "acting" and f["status"] == "ok" and f["low"] < f["mid"] < f["high"], f
        m = s.get(f"/people/{first['id']}/career/model", role="acting")
        usual, new = m["usual"]["prediction"], m["new"]["prediction"]
        assert usual["low"] < usual["high"] and new["low"] < new["high"], m
        nolan = s.get("/people/525/career/model", role="directing")
        assert nolan["chips"], nolan
        career_525 = s.get("/people/525/career", role="directing")
        check = career_525.get("check")
        assert check and 1368337 in {x["movie_id"] for x in check["films"]}, career_525.get("check")
        assert career_525["forecast"]["test"]["holdout"]["year_from"] == 2026, career_525["forecast"]["test"]
        return (f"next film {f['low']:.1f}-{f['high']:.1f} from {f['explain']['n_rated']} rated films; usual "
                f"{usual['low']:.1f}-{usual['high']:.1f}, new {new['low']:.1f}-{new['high']:.1f}; "
                f"Nolan's chips {', '.join(x['name'] for x in nolan['chips'])}")

    s.check("GET /people/{id}/career and /career/model (Day 14.8)", career)

    def options() -> str:
        o = s.get("/meta/options")
        assert len(o["themes"]) == 27 and len(o["fields"]) == 14
        return f"{len(o['fields'])} fields, {len(o['themes'])} themes, {len(o['languages'])} languages"

    s.check("GET /meta/options", options)

    def model_card() -> str:
        c = s.get("/model-card")
        assert expected_version is None or c["model_version"] == expected_version, c["model_version"]
        revenue = c["test"]["targets"]["revenue"]
        assert revenue["films"] > 0 and 0 < revenue["model"]["coverage"] < 1 and c["holdout"]["targets"]["score"]["films"] > 0
        return f"2019+ revenue in range {revenue['model']['coverage']:.1%} of {revenue['films']:,} films"

    s.check("GET /model-card", model_card)

    if args.web_url:
        web_checks(s, args.web_url, expected_version)

    print("All checks passed." if not s.failures else f"{s.failures} check(s) FAILED.")
    sys.exit(1 if s.failures else 0)


if __name__ == "__main__":
    main()
