# V1.5 speed pass: after (Task 10)

Measured on 2026-11-01/02 on branch `perf/v1.5-speed-pass` at 90e0bc4 (Tasks 0-8; Task 9, the frontend step, was cut
and moves to the deploy session). Same laptop and methods as [baseline.md](baseline.md): Windows 11, Docker Desktop
(WSL2), `scripts/bench.py` with 20 repeats and 2 warm-ups, cache misses and hits apart. Fresh `make docker-build`
(build/movies.db has the 10 `SORT_INDEXES`; no `sqlite_stat1`). Full tables:
[after-local.md](after-local.md) (unthrottled), [after-docker.md](after-docker.md) and [after-docker-2.md](after-docker-2.md)
(two throttled runs, each on a fresh container, `--cpus 0.1 --memory 512m`), and
[after-docker-no-healthcheck.md](after-docker-no-healthcheck.md) (the same with `--no-healthcheck`, see G2 below).

With 20 repeats, `bench.py`'s p95 is the slowest of the 20, so one slow request decides a gate.
The throttled numbers are local Docker estimates, not Render; the real check is in the deploy session.

## Gates

Gates use the cache-miss rows and the image as built (with its Docker `HEALTHCHECK`).

| Gate | Target | Baseline | After | Result |
|---|---|---|---|---|
| G1 `POST /predict` p95, local, miss | <= 400 ms | 251 ms | 195 ms (p50 107-123 ms) | pass |
| G2 `POST /predict` p95, throttled, miss | <= 1.5 s | 11.1 s (p50 5.6 s) | 1.80 s and 2.80 s (p50 1.20-1.30 s) | FAIL |
| G3 compare and sweep p95, throttled, miss | <= 2.5 s | compare 36.0 s, sweep 78.7 s | compare 5.9 s and 6.1 s (p50 3.7 s; 3.8 s p95 in a compare-only run with `--no-healthcheck`, see G3 below); sweep 0.60 s and 0.59 s | FAIL (compare); sweep passes |
| G4 read endpoints p95, throttled | <= 300 ms | 2.3 s (home row), 1.9 s (`q=the`), 0.8 s | `q=the` 793 ms and 1,401 ms (p50 696-697 ms); `/people/31` 502 ms in one run of two (200 ms in the other); every other row 91-300 ms | FAIL |
| G5 peak RAM during the benchmark | < 450 MB | 377-399 MiB | 409 MiB and 389 MiB (about 429 and 408 MB). Not part of the gate: the startup peak is 438-464 MiB, up to about 486 MB, above 450 MB on a 512 MB host (baseline 398-433 MiB; see Image, memory, startup) | pass |
| G6 startup, container start to `/health` 200, throttled | <= 20 s | 86 s and 100 s | 85.0 s and 87.2 s | FAIL |
| G7 Lighthouse mobile, Home + Browse + Movie detail | >= 90 | 87, 87, 80 | 86, 88, 84 | FAIL |
| G8 initial JS (gzipped), Home | <= 200 KB | 185,294 bytes | 185,692 bytes | pass |
| G9 tests pass, outputs equal to the snapshot | 100% | pass | `perf_check: OK`; `make test` 688 passed, 45 skipped (the Postgres tests; `make test-pg` 48 passed); `make web-test` 344 passed | pass |

4 of 9 gates pass (G1, G5, G8, G9). The throttled misses are much faster than at baseline (predict p50 5.6 -> 1.3 s,
compare 24.4 -> 3.7 s, sweep 70.8 -> 0.5 s), but G2, G3 (compare), G4 (`q=the`), G6 and G7 still fail.

Also run: `scripts/smoke.py --base-url http://localhost:8000 --web-url http://localhost:8000 --wait 180` against the
throttled container (all checks passed) and the Playwright flow (`npm run e2e` on `make docker-run` + `make userdb`: 7 passed).

## Before and after, every metric

### Latency, throttled (Docker, 0.1 CPU, 512 MB), ms

Baseline: [baseline-docker.md](baseline-docker.md). After: run 1 / run 2 (two fresh containers).

| Endpoint | Cache | Baseline p50 / p95 | After p50 / p95, run 1 | After p50 / p95, run 2 |
|---|---|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 5,603 / 11,097 | 1,296 / 1,393 | 1,300 / 2,797 |
| POST /predict (franchise_blockbuster) | hit | 50 / 500 | 98 / 296 | 50 / 97 |
| POST /predict (small_drama) | miss | 5,704 / 9,504 | 1,300 / 1,804 | 1,298 / 2,700 |
| POST /predict (small_drama) | hit | 50 / 94 | 97 / 295 | 50 / 94 |
| POST /predict (unknown_cast) | miss | 1,496 / 3,199 | 1,293 / 1,305 | 1,205 / 2,800 |
| POST /predict (unknown_cast) | hit | 50 / 96 | 50 / 51 | 50 / 51 |
| POST /predict/compare (3 variants) | miss | 24,395 / 35,992 | 3,700 / 5,899 | 3,700 / 6,103 |
| POST /predict/compare (3 variants) | hit | 6 / 96 | 50 / 98 | 50 / 95 |
| POST /predict/sweep (12 months) | miss | 70,795 / 78,693 | 500 / 597 | 500 / 592 |
| POST /predict/sweep (12 months) | hit | 103 / 295 | 103 / 394 | 50 / 51 |
| GET /movies (genre, years, sort=score) | - | 698 / 799 | 102 / 193 | 102 / 194 |
| GET /movies (language, score_min, page 2) | - | 199 / 205 | 88 / 96 | 6 / 96 |
| GET /movies (home row: popularity) | - | 1,194 / 2,300 | 103 / 196 | 102 / 195 |
| GET /movies/299536 (detail) | - | 104 / 202 | 104 / 203 | 105 / 202 |
| GET /movies?q=avengers infinity | - | 4 / 95 | 5 / 96 | 5 / 95 |
| GET /movies?q=the | - | 898 / 1,900 | 696 / 793 | 697 / 1,401 |
| GET /people?role=actor&q=tom ha | - | 5 / 96 | 6 / 97 | 6 / 95 |
| GET /people?role=director&q=nol | - | 4 / 94 | 4 / 96 | 4 / 95 |
| GET /companies?q=univ | - | 3 / 92 | 3 / 91 | 3 / 92 |
| GET /people/31 (Tom Hanks) | - | 106 / 200 | 298 / 502 | 108 / 201 |
| GET /people/525 (Christopher Nolan) | - | 101 / 191 | 101 / 192 | 101 / 106 |

Cache hits need under 3 ms of CPU; at 0.1 CPU they land at about 5, 50 or 100 ms depending on the CPU-quota slice, so the
hit rows did not change and are not a result. A third run on the first container is not used: `bench.py` picks miss
runtimes from 41-300 at random, so a second run on a warm container repeats some and got cache hits on miss rows
(the bench reported them as errors). Run the bench on a fresh container each time.

### Latency, local (unthrottled), ms

Baseline: [baseline-local.md](baseline-local.md). After: [after-local.md](after-local.md), served with
`MOVIES_DB=build/movies.db` (the image's database, with the indexes) and `CONTEXT_FILE=build/context.joblib`.

| Endpoint | Cache | Baseline p50 / p95 | After p50 / p95 |
|---|---|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 160.6 / 186.1 | 111.3 / 195.4 |
| POST /predict (franchise_blockbuster) | hit | 2.5 / 3.0 | 2.9 / 4.0 |
| POST /predict (small_drama) | miss | 166.9 / 251.0 | 123.3 / 157.4 |
| POST /predict (small_drama) | hit | 2.5 / 2.8 | 3.1 / 3.9 |
| POST /predict (unknown_cast) | miss | 155.1 / 177.4 | 107.1 / 141.6 |
| POST /predict (unknown_cast) | hit | 2.6 / 2.9 | 3.2 / 3.7 |
| POST /predict/compare (3 variants) | miss | 654.7 / 732.8 | 360.9 / 436.7 |
| POST /predict/compare (3 variants) | hit | 3.2 / 3.4 | 3.4 / 65.7 |
| POST /predict/sweep (12 months) | miss | 1,984.6 / 2,065.8 | 45.5 / 70.6 |
| POST /predict/sweep (12 months) | hit | 3.2 / 3.5 | 3.3 / 4.4 |
| GET /movies (genre, years, sort=score) | - | 211.9 / 287.5 | 16.8 / 37.8 |
| GET /movies (language, score_min, page 2) | - | 43.9 / 68.8 | 4.7 / 6.5 |
| GET /movies (home row: popularity) | - | 361.3 / 468.2 | 10.1 / 15.7 |
| GET /movies/299536 (detail) | - | 15.7 / 21.2 | 15.9 / 21.1 |
| GET /movies?q=avengers infinity | - | 4.2 / 5.1 | 5.0 / 5.8 |
| GET /movies?q=the | - | 171.0 / 235.8 | 76.7 / 111.3 |
| GET /people?role=actor&q=tom ha | - | 5.4 / 6.3 | 6.0 / 7.1 |
| GET /people?role=director&q=nol | - | 3.9 / 5.3 | 4.0 / 5.1 |
| GET /companies?q=univ | - | 2.3 / 2.8 | 2.3 / 2.7 |
| GET /people/31 (Tom Hanks) | - | 20.4 / 32.6 | 23.7 / 34.5 |
| GET /people/525 (Christopher Nolan) | - | 11.2 / 16.9 | 11.5 / 14.1 |

The baseline's local server read `data/movies.db` (no sort indexes yet); the after run reads `build/movies.db`.

### Image, memory, startup

| Item | Baseline | After |
|---|---|---|
| Image (`docker image inspect` size) | 1,513,149,058 bytes (1.51 GB) | 1,421,877,123 bytes (1.42 GB): -116 MB of test folders (Task 2), +18 MB of indexes; that sums to -98 MB, the image shrank 91 MB, and the other 7 MB is not explained |
| `build/movies.db` | 298 MB | 316 MB (315,793,408 bytes; 10 sort indexes, Tasks 6-7) |
| Startup, start -> first `/health` 200 (polled every 1 s; baseline every 3 s) | 85.7 s, 100.1 s | 85.0 s, 87.2 s (a third run's start time was lost); 63.7 s with `--no-healthcheck` |
| "loaded the models and lookups in" (log) | 60.3 s, 68.5 s | 63.5 s, 60.4 s, 63.2 s; 45.1 s with `--no-healthcheck` |
| Idle RAM, 20 s after the first `/health` 200 | 308-337 MiB | 359, 331, 325 MiB; 337 MiB with `--no-healthcheck` |
| Peak RAM during startup (sampled every 2-4 s) | about 398-433 MiB (every 5 s) | 464, 449, 438 MiB; 428 MiB with `--no-healthcheck` |
| Peak RAM during the bench (G5) | 377-399 MiB | 409, 389 MiB; 396 MiB with `--no-healthcheck` |
| Build (`make docker-build`) | 1 min 39 s | not timed (slim_db 8 s, prebuilt 4 s, then the image) |

The startup peak is higher than at baseline: 464 MiB is about 486 MB, over 450 MB and 26 MB under Render Free's 512 MB.
The cause is not measured (sampling every 2-4 s instead of every 5 s catches more of the peak; the indexes add 18 MB of
file). G5 is defined on the benchmark and passes; the startup peak is a risk for the deploy session to watch.

### Frontend

`npm run build`: 3,214 modules (baseline 3,213: the WakeUpGate). Largest files (raw / gzip, kB): `CareerSection` 350.7 /
103.0 (lazy), `index` 284.7 / 89.4, `dist-4SFrI0Lh` 132.7 / 45.9, `Predict` 102.4 / 33.8, `persist` 90.3 / 26.2, `sentry`
89.2 / 30.7 (lazy), `errors` 69.5 / 20.5; CSS 97.3 / 15.8. All within 0.4 kB of the baseline. Home (`/`) loads 8 scripts:
562,941 bytes raw, **185,692 bytes transferred** (baseline 561,723 / 185,294).

### Lighthouse (mobile, performance only, one run each)

Same method as the baseline: `npx lighthouse` 13.6.0, Microsoft Edge as `CHROME_PATH`, `--form-factor=mobile`, the default
simulated slow 4G and 4x CPU slowdown, against the local unthrottled server serving `frontend/dist` (rate limits raised).

| Page | Baseline | After | FCP | LCP | TBT | CLS | Speed Index |
|---|---:|---:|---:|---:|---:|---:|---:|
| Home `/` | 87 | 86 | 0.9 s | 4.3 s | 60 ms | 0 | 0.9 s |
| Browse `/browse` | 87 | 88 | 0.9 s | 3.6 s | 180 ms | 0.001 | 0.9 s |
| Movie detail `/movies/299536` | 80 | 84 | 0.9 s | 4.6 s | 10 ms | 0.001 | 0.9 s |
| Predict results `/predict/result?f=` (superhero) | 93 | 93 | 0.9 s | 3.3 s | 40 ms | 0.001 | 1.0 s |
| Actor `/people/31` | 82 | 84 | 0.9 s | 4.1 s | 180 ms | 0.001 | 1.3 s |

The changes are within one run's noise (a few points); no frontend change was made (Task 9 was cut).

## Log review (docs/perf/log.md)

Every row logged "reverted" or "not done" was checked in the code:

- PRAGMA `temp_store`, `cache_size`, `mmap_size` and the `SQLITE_MMAP` setting: no PRAGMA of these anywhere in
  `backend/`, `ml/data/build_db.py` or `scripts/slim_db.py`, and no `SQLITE_MMAP` in the code, settings or Dockerfile.
- Connection reuse: `deps.get_db` still opens one `mode=ro` connection per request (`connect_read_only`).
- `ANALYZE`: build/movies.db has no `sqlite_stat1` table.
- `ORJSONResponse`: no `orjson` import or dependency.
- `immutable=1` and WAL: not used (`mode=ro`, rollback journal).

One wording fix: Task 4's "throttled hit p50 49 -> 4 ms" was one run's quota slice, not a gain; the row now says so.
No other row claims a gain that was not measured.

## Failing gates — profile

Nothing below was changed. Each option says whether it changes outputs (those need Dimitris's approval: D5 and
`perf_check` would fail) or only speed.

### G2 (predict p95, throttled): the outliers come from the Docker HEALTHCHECK

- The miss itself passes: p50 1.20-1.30 s in every run. p95 fails on one or two slow requests per 20: 1.30-1.80 s in
  run 1 and 2.70-2.80 s in run 2 (the two tabled runs), 1.30-1.71 s with `--no-healthcheck`. The server log
  of run 2 shows 8 of the 69 slow-logged predict requests at 2.0-2.9 s, the rest at 1.1-1.4 s.
- In-process in the image at 0.1 CPU (100 predictions, no HTTP): p50 1,197 ms, p95 2,204 ms, max 2,798 ms; 16 calls over
  1.55 s, only one with a gen2 GC pause in it (GC pauses are 100-400 ms, 4 per 100 predictions).
- The same with `docker run --no-healthcheck`: p50 1,195 ms, **p95 1,199 ms, max 1,403 ms**, no slow call. The image's
  `HEALTHCHECK` starts a new Python interpreter every 30 s inside the same 0.1 CPU quota, and that is what the outliers are.
- Over HTTP with `--no-healthcheck`: predict p95 1,393 / 1,706 / 1,300 ms (one slow request on the small drama), so G2
  still fails there by one request.
- Where the CPU goes (local, one predict, pyinstrument): about 115-150 ms, of it `pred_contrib` on the three middle models
  100 ms, the driver grouping 28 ms, the 9 quantile predicts 19 ms, comparables 9 ms, features 4 ms.

Options:
1. Speed only: a lighter Docker healthcheck (a shell `wget`/`curl` instead of `python -c`, or a longer interval).
   Render runs its own HTTP health check, so this mainly makes the local numbers match the host; to be confirmed on
   Render in the deploy session. It also helps G6 (below).
2. Changes outputs: fewer drivers (e.g. no score or budget drivers on the results page) or a smaller `pred_contrib`.
   Not recommended without approval.

### G3 (compare p95, throttled): pred_contrib for 4 forms

- Throttled p50 3.70 s in every run; p95 5.9 s (run 1) and 6.1 s (run 2), 4.3 s in the full bench with
  `--no-healthcheck`. Task 5's log row had p95 3,797 ms with the same p50 (3,699 ms): that was a full bench with
  `--repeats 5` on the Task 5 image, healthcheck on, so its p95 is the slowest of 5 compares (about 18 s of compare
  requests, which a 30 s healthcheck probe often misses); here it is the slowest of 20. A compare-only run on a fresh
  container with `--no-healthcheck` (20 misses, the bench's request) gave **p50 3,699 ms, p95 3,796 ms**, every request
  3,600-3,796 ms: the spread in the tabled runs is the healthcheck, as for G2. The one slower compare (4.3 s) in the
  `--no-healthcheck` full bench is not explained. Without the spread compare still fails: 3.7-3.8 s against 2.5 s.
- Locally `predict_many` on the 4 forms takes 353-413 ms; of one
  profiled call (393 ms) `pred_contrib` takes 227 ms (58%), the driver grouping and `main_feature` 37 + 9 + 8 ms,
  comparables 43 ms, the quantile predicts 12 ms. `pred_contrib` costs the same per row in a batch (Task 5), so 4 forms
  cost 4x one.
- The compare page uses only the **revenue** drivers (`CompareView` calls `driverChanges(base, p)`, target revenue) and
  no comparables. The budget and score `pred_contrib` (per row 20 and 29 ms, against 6 ms for revenue, Task 5) and the
  comparables are in the API answer but not on the page.

Options:
1. Changes outputs (approval needed): a compare answer with revenue drivers only and no comparables for the variants. By
   Task 5's per-row costs this removes about 70% of the contribution time and all comparables: an estimate of roughly
   1.5-2 s throttled, not measured. The cache would need its own key for such trimmed answers (like the sweep's `ranges:`).
2. Speed only: none found that reaches 2.5 s; the batch already calls each booster once.

### G4 (reads, throttled): the `q=the` count

- Locally `repo.search(q="the")` takes 64.5 ms: the `COUNT(*)` joining 71,766 FTS matches to `movies` 47.6 ms (74%), the
  page ids 18.5 ms, cards and genres under 1 ms. Throttled that is about 700 ms (p50 696 and 697 ms in the tabled runs,
  701 ms with `--no-healthcheck`).
- `/people/31` at 502 ms p95 in run 1 (p50 298 ms) is not explained: run 2 had p50 108 / p95 201 ms
  and the `--no-healthcheck` run 106 / 200 ms.

Options (Task 7 listed the first three):
1. Speed only: `INDEXED BY` a narrow `(id, release_date)` index for the join (count 46 -> 25 ms locally; breaks on a
   database without the index).
2. Speed only: FTS5 `prefix='2 3'` (+31 MB; count 48 -> 39 ms; changes the table the refresher writes).
3. Speed only: a count straight from FTS when no other filter is set (valid only while every film has a date).
4. Speed only, after the first request: an in-process cache of totals per query and filters (the first `q=the` stays slow).
5. Changes outputs: cap the total ("1,000+ films") when the text matches many films.

### G6 (startup, throttled): the autocomplete build

Each phase timed once in the image at 0.1 CPU (`python` in a separate container, healthcheck on, total 80.7 s):

| Phase | Time |
|---|---:|
| import numpy + pandas | 6.6 s |
| import lightgbm (scipy) | 3.5 s |
| import onnxruntime | 0.3 s |
| import fastapi | 3.6 s |
| import the rest of `backend.app.main` | 7.4 s |
| `check_manifest` (SHA-256 of the model files) | 0.5 s |
| `FeatureContext.load` (context.joblib) | 0.9 s |
| comparables `Index.load` | 4.5 s |
| revenue + budget models | 1.6 s |
| score model | 1.4 s |
| **`Lookups.from_db`** (autocomplete) | **50.3 s** |
| `build_info` | 0.1 s |

Locally `Lookups.from_db` takes 7.6 s (pyinstrument): `NameIndex.build` 6.8 s, of it `_normalise` (casefold, NFKD and
accent folding for every name) 3.1 s, the key loop 2.0 s, the sort 0.4 s; the SQL 0.7 s. Without the healthcheck the
container started in 63.7 s instead of 85-87 s.

Options (all speed only, outputs unchanged):
1. Prebuild the lookups at image build time, like `CONTEXT_FILE` (packed bytes and arrays, stamped with the database's
   `built_at`): saves most of the 50 s.
2. A faster `_normalise` (skip NFKD for pure-ASCII names; the result is the same): about 40% of the build.
3. The lighter healthcheck from G2: about 20 s locally.
4. Imports (21 s) and model loading (9 s) remain, so even with 1-3 startup stays above 20 s at 0.1 CPU. Reaching 20 s
   would need `/health` to answer before the models are loaded, which changes what `/health` means.

### G7 (Lighthouse): image LCP

- LCP is the lost score on every page: Home loses 14.5 points on it, Browse 9.8, Movie detail 16.5, Actor 13.5. FCP is
  0.9 s everywhere; TBT costs little (Browse and Actor 180 ms).
- The LCP element: Home the start page's collage (`<img fetchpriority="high">`; 2 collages, 306 KB); Browse the first
  poster (`w342`); Movie detail its poster (`w780`, 689 ms to load); Actor the photo (`h632`). The film images start late
  because their URLs are known only after the script and the API answer (resource load delay 212-307 ms observed).
- Lighthouse also lists the CSS file as render-blocking (about 310 ms estimated) and 40-101 KiB of unused JavaScript.

Options (speed only, the frontend step that was cut): smaller first images (e.g. `w342`/`w500` for the movie poster, a
smaller or AVIF collage), preconnect to `image.tmdb.org`, prefetching the first poster, and the route-level work of spec 3.6.
