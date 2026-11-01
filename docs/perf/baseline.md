# V1.5 speed pass: baseline (before any change)

Measured on 2026-11-01 on branch `perf/v1.5-speed-pass`, commit 6e630f4 plus the timing middleware and the new tools
(the middleware costs well under 1 ms). Windows 11 laptop, Docker Desktop (WSL2). Full tables:
[baseline-local.md](baseline-local.md) (unthrottled) and [baseline-docker.md](baseline-docker.md) (`--cpus 0.1 --memory 512m`).
Tools: `scripts/bench.py` (20 repeats, 2 warm-ups, cache misses and hits kept apart), `scripts/perf_check.py` (G9).

## Gates at baseline

| Gate | Target | Baseline | Result |
|---|---|---|---|
| G1 `POST /predict` p95, local, cache miss | <= 400 ms | 251 ms (small drama; the others 177-186 ms) | pass |
| G2 `POST /predict` p95, throttled, miss | <= 1.5 s | 11.1 s (blockbuster), 9.5 s (drama), 3.2 s (unknown cast); p50 5.6 s / 5.7 s / 1.5 s | FAIL |
| G3 compare and sweep p95, throttled, miss | <= 2.5 s | compare 36.0 s (p50 24.4 s), sweep 78.7 s (p50 70.8 s) | FAIL |
| G4 read endpoints p95, throttled | <= 300 ms | 2.3 s `/movies` home row, 1.9 s `/movies?q=the`, 0.8 s `/movies` genre+years+sort=score; the other 8 pass | FAIL |
| G5 peak RAM during the benchmark | < 450 MB | 377 MiB during the bench (398 MiB sampled while loading; idle 308-314 MiB) | pass |
| G6 startup, container start to `/health` 200, throttled | <= 20 s | 86 s and 100 s (two runs; the models and lookups load in 60-69 s, the rest is Python and imports) | FAIL |
| G7 Lighthouse mobile, Home + Browse + Movie detail | >= 90 | 87, 87, 80 | FAIL |
| G8 initial JS (gzipped), Home | <= 200 KB | 185 KB | pass |
| G9 outputs equal to the snapshot | identical | `perf_check` OK, run twice | pass |

Cache hits are cheap everywhere: about 50 ms throttled (the server needs under 3 ms; the rest is the 0.1 CPU time slice),
2.5-3.5 ms local. The problem is the miss: one prediction costs about 160 ms local and about 5.6 s throttled (35x), and
compare and sweep run 4 and 12 of them one after another (0.65 s and 2.0 s local; 24 s and 71 s throttled). The throttled
timings come in steps of about 100 ms (Docker's CPU quota period).

## Image, memory, startup

| Item | Value |
|---|---|
| Image `ghcr.io/tsomaros/movie-prediction:latest` | 1.51 GB on disk (1,513,149,058 bytes as `docker image inspect`) |
| Startup (start -> first `/health` 200), `--cpus 0.1` | 85.7 s and 100.1 s (polled every 3 s); log line "loaded the models and lookups in 60.3 s" / "68.5 s" |
| Idle RAM after startup | 308-337 MiB (`docker stats`) |
| Peak RAM, startup | about 398-433 MiB (sampled every 5 s) |
| Peak RAM, benchmark (383 samples) | 379 MiB (max of the three runs 377-399 MiB) |
| Build | `make docker-build` 1 min 39 s (the data layers were cached) |

## Frontend

`npm run build` (Vite 8): 3,213 modules. Largest files (raw / gzip): `CareerSection` 350.7 / 103.0 kB (lazy, Recharts),
`index` 283.5 / 89.0 kB, `dist-4SFrI0Lh` 132.7 / 45.9 kB (shared vendor chunk), `Predict` 102.4 / 33.8 kB, `persist` 90.3 /
26.2 kB, `sentry` 89.2 / 30.7 kB (lazy), `errors` 69.5 / 20.5 kB; CSS 97.3 / 15.8 kB.

Home (`/`) loads 8 scripts: 561,723 bytes raw, **185,294 bytes transferred** (gzip is already on: `GZipMiddleware` in `web.py`).
All five are served from the local API (`WEB_DIR=frontend/dist`, unthrottled, rate limits raised), not the throttled
container: the numbers show the frontend's own cost, not the slow host.

## Lighthouse (mobile, performance only, one run each)

Lighthouse via `npx lighthouse`, Microsoft Edge as the browser (`CHROME_PATH`), `--form-factor=mobile`, Lighthouse's default
simulated slow 4G and 4x CPU slowdown. Predict results is the superhero form from `?f=`.

| Page | URL | Score | FCP | LCP | TBT | CLS | Speed Index |
|---|---|---:|---:|---:|---:|---:|---:|
| Home | `/` | 87 | 1.0 s | 4.1 s | 60 ms | 0 | 1.0 s |
| Browse | `/browse` | 87 | 0.9 s | 3.5 s | 210 ms | 0.001 | 1.4 s |
| Movie detail | `/movies/299536` | 80 | 0.9 s | 5.5 s | 60 ms | 0.001 | 1.9 s |
| Predict results | `/predict/result?f=...` | 93 | 0.9 s | 3.2 s | 90 ms | 0.001 | 1.4 s |
| Actor | `/people/31` | 82 | 0.9 s | 4.1 s | 260 ms | 0.001 | 1.6 s |

LCP is the weak metric everywhere (4.1 s on Home, 5.5 s on Movie detail; the LCP element was not inspected, TMDB images are the likely cause); Browse and Actor also lose points on
blocking time (210 and 260 ms). The JSON reports are not committed (500-900 kB each).

## Notes for the next tasks

- Where the time goes is the work per prediction, not the network: a miss is 160 ms of CPU locally. The sweep and compare
  paths multiply it by 12 and 4, so one batch call is the biggest lever for G3.
- `/movies` without a query (home rows, genre filters) and `/movies?q=the` are the slow reads (170-360 ms locally).
- The persistent `couldn't stop thread 'userdb-worker-0'` line in local runs comes from `USER_DATABASE_URL` in `.env` pointing at a
  Postgres that is not running; the image has no such variable.
- `bench.py` raises the rate limits only through `RATE_LIMIT` and `RATE_LIMIT_READ` on the benchmark's own server.
