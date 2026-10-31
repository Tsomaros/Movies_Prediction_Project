# Running with Docker and deployment

The one Docker image, its memory and size, and the live deployment on Render. Back to the [README](../README.md).

## Running with Docker

Two containers (`docker-compose.yml`): Postgres for the demo account (Day 14, data kept in the `userdb` volume), and the app's one image (`backend/Dockerfile`, Day 15): the API with the database, the app's models and the 8-bit text model baked in, which also serves the built React app. The app is on http://localhost:8080 and the API on :8000; both ports reach the same server. It is the image Render runs. Building it needs Docker and the local data and models (`data/movies.db`, `ml/artifacts/final/`, `make model`); a clean clone without them can pull it instead (`docker login ghcr.io`, then `docker compose pull app`; the image is private).

```bash
make docker-build   # build/movies.db (slim copy) + build/context.joblib (prebuilt track records), then the image
make docker-run     # docker compose up -d --wait: returns once both healthchecks pass; the app is on :8080
make smoke          # scripts/smoke.py: the API on :8000 and the app on :8080; make smoke URL=https://... WEB=https://... for the live site
docker compose down
```

**The app inside the image** (until Day 15 an nginx image of its own): a Node 24 stage installs the locked packages, type-checks the app and builds it, and `backend/app/web.py` serves `dist/` (`WEB_DIR`). Every other path (`/predict`, `/movies/603`) gets the app, an unknown `/api` path stays a JSON 404, the hashed bundles are cached for a year and the page not at all, responses over 1 KB are gzipped, and every answer carries `nosniff` and a referrer policy.

**What goes into the image:**
- the runtime dependencies only, 10 packages: `uv sync --no-default-groups`; `optuna`, `matplotlib`, `scikit-learn` and `onnx` are in the `ml` group, and `pytest` and `jupyter` in `dev`;
- `build/movies.db`: `data/movies.db` without the training-only `features` table, VACUUMed, 334 → 293 MB with the person details (`scripts/slim_db.py`; 220 MB before Day 14.6);
- `build/context.joblib`: History, Companies and Franchises built once (`python -m ml.features.build prebuilt`), stamped with the database's build time and film count, so a file from another build is refused;
- `ml/` and `backend/`, with the app's models and comparables index and the 8-bit MiniLM only (23 MB), copied after the data so a code-only deploy pushes only the small layers;
- the built app (`frontend/dist`, about 1 MB).

**How it runs:**
- as a non-root user, with one uvicorn worker (the prediction cache and the rate limiter live in its memory);
- a healthcheck on `/api/v1/health`;
- `CORS_ORIGINS`, `USER_DATABASE_URL`, `SENTRY_DSN` and `CLIENT_IP_HEADER` from the environment, and the port from `PORT` (8000 unless the host sets it);
- `MALLOC_ARENA_MAX=2`, and after loading the app hands freed memory back to the system (`malloc_trim`);
- `OMP_NUM_THREADS=1`: LightGBM's threads gave no speed-up under a 0.1 CPU limit (6.4 s with 8, 5.9 s with 1 per prediction).

**The smoke script** (`scripts/smoke.py`) waits for `/health`, then checks:
- the model version;
- the three golden forms, each middle equal to `tests/golden/predictions.json` to 6 significant figures;
- compare, the 12-month sweep, a bad form's 422, search, the box-office sort and the score filter, a movie page, autocomplete, options and the model card;
- with `--web-url` (`make smoke` passes `WEB`, default :8080): the start page and its two collages (WebP, under 300 kB), the script bundle (gzipped, cached for a year), a client-side route served as the app, and the API on the app's address.

That is 19 checks. It exits with status 1 on any failure, the same against local Docker and the live URL.

**Measured in Docker Desktop (Linux) on this laptop:**

| | |
| --- | --- |
| Image | 1,097 MB unpacked (the layers in `docker history`), about 411 MB compressed (Docker Desktop's `docker images` shows their sum, 1.51 GB); 1,085 / 409 MB before Day 15 added the app and Sentry, 984 / 370 MB before Day 14's account packages and the person details (Days 14.6–14.7) |
| Startup until healthy | 8.3 s (models, prebuilt track records, comparables, lookups) |
| Memory after startup | 323 MB (it peaks at 489 MB while loading) |
| Memory after 100 different predictions with synopses | **407 MB** (`docker stats` 385 MiB), under the 450 MB gate |
| After 100 predictions with synopses and 50 career pages (V1.4 image, fresh container, 2026-10-31) | `docker stats` 352 MiB (about 369 MB), under the 450 MB gate; the career pages alone added 3 MiB |
| One long run without a restart: smoke test, 100 predictions and 50 career pages (V1.4 image) | `docker stats` 459 MiB (about 481 MB, process RSS 443 MB): **above the 450 MB gate**, about 30 MB under Render Free's 512 MB. The cause is not measured. V1.4 adds no cache, and the career pages alone added 3 MiB, so the likely source is the existing prediction and career-model caches that the smoke test fills |
| Under a 512 MB limit, like Render Free | no out-of-memory kill; startup, 100 predictions and the smoke test pass |
| Under 512 MB and 0.1 CPU (Day 15, the image with the app and Sentry) | healthy after 80.5 s, startup peak 456 MiB, 353 MiB after predictions; `/predict` median 5.9 s (1 CPU: 669 ms) |
| `/predict`, uncached | median 175 ms, 90th percentile 192 ms |

**How memory came down from 663 MB:**
- **Prebuilt track records:** building History with pandas left about 320 MB freed but kept.
- **Returning freed memory** to the system.
- **Packed name lookups:** History's dict of 344k names took 83 MB.
- **Flat arrays** for Companies and Franchises: dicts of 47k small arrays took 52 MB.
- **Comparables titles as plain strings** instead of 127-character fixed-width text, which took 17 MB.

Every prediction is unchanged: the full features table rebuilt both ways matches the stored one bit for bit, and all 344,445 person and 42,519 company names resolve as before.

**How the image came down from 1.03 GB:**
- **The app stopped loading `optuna` and `scikit-learn`.** `Chain.load` imported `optuna` through `calibrate` and `tune`, and three sklearn imports moved into the training functions that use them.
- **An 8-bit MiniLM for the creator's synopsis** (23 MB instead of 90 MB). Its weights are quantised per output channel. On 1,000 overviews its vectors have a mean cosine of 0.993 with the full model's, and 89% find the same nearest overview; plain int8 gave 0.956 and 71%. Training and the comparables index keep the full model's vectors, and the golden comparables are unchanged.

## Deployment (Day 15)

The app runs at **https://movie-prediction-2f1b0265282c.onrender.com**: one Render Free web service in Frankfurt (512 MB, 0.1 CPU, no card) running the image above, with the demo account's data in Neon's free Postgres 18, also in Frankfurt.

**Why a prebuilt image.** Render can't build the image from the repository: the slim database, the models and the 8-bit MiniLM (about 470 MB) aren't in git. So the image is built here, pushed to a private GitHub Container Registry image (`ghcr.io/tsomaros/movie-prediction`, private so the TMDB-derived database can't be downloaded), and Render pulls it with a read-only token.

```bash
make deploy   # scripts/deploy.py: refuses uncommitted changes, builds from this commit, pushes :<commit> and :latest,
              # then calls Render's deploy hook (RENDER_DEPLOY_HOOK in .env) with that tag
make smoke URL=https://movie-prediction-2f1b0265282c.onrender.com WEB=https://movie-prediction-2f1b0265282c.onrender.com
```

- **Manual only:** an image service never deploys by itself, so a commit can't change the live demo. A rollback is Render's dashboard or the hook with an earlier tag.
- **The first push** uploads about 410 MB (just over 10 minutes here); the data layers come before the code, so later code-only pushes are small.
- **The service's own image tag** is what Render redeploys after a settings change, so it must be set to the deployed tag (the hook's tag counts for that deploy only).
- **Neon:** `make userdb USER_DATABASE_URL="<Neon's direct URL>"` applied the migration and the demo seed, with the same `DEMO_PASSWORD` as on Render.

**Render's settings:**

| Variable | Value |
| --- | --- |
| `USER_DATABASE_URL` | Neon's direct connection string (no pooler), with `connect_timeout=10` |
| `DEMO_PASSWORD` | the one the seed hashed |
| `CORS_ORIGINS` | `https://movie-prediction-2f1b0265282c.onrender.com` |
| `CLIENT_IP_HEADER` | `CF-Connecting-IP` |
| `TMDB_READ_TOKEN` | TMDB's read token, for the New arrivals row (V1.2). Without it nothing is refreshed and the app shows the build's films only |
| `SENTRY_DSN` | the backend's Sentry project (not set yet) |
| Health check path | `/api/v1/health` |

**The client IP on Render.** Render appends to an `X-Forwarded-For` the visitor sends instead of replacing it, so whatever a visitor writes there reached the app as their address. Six wrong logins, each with a different forged `X-Forwarded-For`, all got 401 instead of a 429 on the 6th, with `FORWARDED_ALLOW_IPS` at its default and at `*`. The limits now read `CF-Connecting-IP`, which Cloudflare (in front of Render) sets itself and which can't be forged: a request that sends its own gets Cloudflare's 403 before it reaches the app. Forged `X-Forwarded-For`, `True-Client-IP` and `X-Real-IP` headers all hit the limit on the 6th login now.

**Checked live (2026-10-27):**
- `make smoke` against the live URL: all 22 checks, the same golden predictions as locally;
- the same smoke from GitHub's servers (the daily Action's first run): passed in 57 s;
- the demo login (cookie HttpOnly, SameSite=Lax, Secure), a list entry added and removed (about 0.1 s each), and a write with another site's `Origin` refused with a 403.

**Speed on Render Free:**

| | Live |
| --- | --- |
| The first visit after 15 idle minutes (the start page) | 83.8 s: Render starts the container, then the models load |
| Model loading at startup | 31–36 s |
| `/predict`, uncached (10 forms) | median 2.2 s, max 2.6 s (target: up to about 3 s) |
| `/predict`, cached | 107 ms |
| Film, person and career pages, search, autocomplete | about 0.1 s |
| Surprise me | 0.4 s |
| Compare with two variants | 4.5 s |
| The career section's model films | 6.1 s |
| The 12-month sweep | 24.6 s |

**New and upcoming films (V1.2; one database since V1.3):**
- The image sets `FRESH_REFRESH=1`, and its `movies.db` and `/app/data` belong to the `app` user. Right after a start the app opens the database read-write once, then merges the new and upcoming films into it in the background (about 9 s for 97 films, TMDB included) and again every 6 hours; the first requests after a wake-up answer from the build. Render's disk is wiped on every sleep and redeploy, so the image's database comes back and the merge runs again. `TMDB_READ_TOKEN` must be set on Render; `FRESH_MIN_POPULARITY` (5) and `FRESH_TTL_S` (21600) are optional.
- A film that a user listed or noted is pulled by id even when it has left the window, so *My movies* keeps it until the next restart (when TMDB still knows it and the listing is read from Neon).
- The first write copies the 298 MB file into the container's writable layer: 0.5-1.0 s in Docker, held as page cache the kernel gives back under pressure. Measured locally on the V1.3 image (512 MB limit, `FRESH_TTL_S=60`, 2026-10-31): 1,254 predictions and 1,203 list and search requests in 100 s while a second merge committed; no lock error or failed refresh, no out-of-memory kill, RSS 358 MB (gate 450). A `docker compose restart` keeps the merged file, and the app still starts: the prebuilt context's stamp counts films up to 2025 only.
- The image carries `data/cpi_us_annual.csv` (the refresher cleans money in 2025 dollars). `make deploy` does not rebuild `build/`: run `make docker-build` first after any data change, and after this version (the stamp changed). `scripts/slim_db.py` refuses a `data/movies.db` that a refresh was merged into.
- Not measured on Render yet: the copy and memory after a wake-up there. If Render's writable layer were held in memory instead of on disk, the copy would not be reclaimable and the first merge could pass 512 MB. After the first deploy check that `/health`'s `fresh.films` is set and `uptime_seconds` keeps growing past `fresh.refreshed_at` (no restart loop), and look at the dashboard's memory graph. The off switch is `FRESH_REFRESH=0` in Render's environment: it overrides the image, and the app serves the build without new films.
- A database built before V1.3 lacks the two tables the app reads (`fresh_films`, `fresh_people`): `make db` creates them, or add them in place with `uv run python -c "import sqlite3; from backend.app.services.fresh.merge import ensure_tables; c = sqlite3.connect('data/movies.db', isolation_level=None); c.execute('BEGIN'); ensure_tables(c); c.execute('COMMIT')"`. Without them `/meta/options`, `/health` and `make career` fail.

**Monitoring:**
- **A daily check:** `.github/workflows/live-smoke.yml` runs `scripts/smoke.py` against the live URL at 06:17 UTC and waits up to 3 minutes for the wake-up; a failed run emails the repository's owner. Once a day, because any check wakes the service, so frequent pings would be a keep-alive. GitHub stops scheduled workflows after 60 days without activity in the repository.
- **Sentry** (errors only, no tracing or replay): the backend reports unhandled errors without cookies, IPs, request bodies or stack-frame variables (`backend/app/services/platform/monitoring.py`); the frontend loads its SDK in the background as a 30.7 kB chunk (the start page's bundle grows by 125 bytes) and the route error page reports crashes. Both are off without a DSN, and no DSN is set yet.
