# API

The FastAPI backend: every endpoint, the errors, the limits and the measured speed. Back to the [README](../README.md).

## API

A FastAPI backend in `backend/app/`. Every endpoint lives under `/api/v1`, and the interactive docs are at `/docs`. Run it with `make api` (http://localhost:8000; about 10 s to load the models and lookups once). The React app ([Frontend](app.md#frontend)) is built against this API.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/predict` | A creator form in; ranges, drivers, comparable films and warnings out |
| POST | `/api/v1/predict/compare` | A base form and 1–3 variants; every prediction plus the differences |
| POST | `/api/v1/predict/sweep` | One form with one field (`release_month`, `runtime` or `budget`) tried at 2–12 values; the three ranges at each |
| GET | `/api/v1/movies` | Search (`q`), filters (`genre`, `year_from`, `year_to`, `language`, `score_min`: films with any number of votes), `when` (V1.2: `released` = out in the last 14 days, `upcoming` = due in the next 60, UTC), `sort` (popularity, newest, soonest: the next release first, title, score: 500+ votes only, revenue: 2025 $, trusted figures only), `page`, `page_size` (at most 48); each film with its score, votes and revenue in 2025 $. Without `when` and without `q`, a film that is not yet released is left out; a search finds it. The list includes the new and upcoming films the refresh merges in (V1.2), and an answer that holds one is cached for 10 minutes instead of an hour |
| GET | `/api/v1/movies/{id}` | Facts, themes, cast (with TMDB photos where the person pull has them; `linked: false` on a person who came with a new film, who has no page) and crew, money (as reported and in 2025 $), score, posters and 6 similar films |
| GET | `/api/v1/people?role=director\|actor&q=` | Director and actor autocomplete (any word of the name, accents folded), each with a TMDB photo thumbnail and the film they're known for |
| GET | `/api/v1/people/search?q=&role=all\|actor\|director\|writer&page=&page_size=` | The header's people search (V1.1): actors, directors and writers whose name has a word starting with `q` (accents folded), 24 a page (at most 48), ranked by films in the role (for `all`, distinct films over the three), then TMDB popularity and name. Each result has its roles with film counts (most first), a w185 photo and the most-voted film it is known for; `role_counts` says how many each role chip would show. Under 2 letters or digits: `total: 0` |
| GET | `/api/v1/people/{id}` | One person: TMDB photo, biography, life dates and links (where the person pull found them), their `main_role`, and per role (acting, directing, writing, production, music, camera, editing) their films (characters, or jobs) and stats from our data (films, years, top genres, average score over 50+ vote films, trusted box office in 2025 $, the actor and director they shared 2+ of those films with) |
| GET | `/api/v1/people/{id}/career?role=acting\|directing\|writing` | One person's dated films in a role (score, votes, lead or supporting), a 5-film career line, the best film and a track-record forecast of their next film's score with its backtest coverage (Day 14.8). Each film has `settling`: its score was under 182 days old when pulled, so it is drawn but not counted. `forecast.test.holdout` is the same backtest on films after 2025 (`year_from`, `coverage`, `n_points`; `coverage` is null when the role has none). `check` is the range built from counted films up to 2025 with each rated later film marked `inside` or not (compared at one decimal, as the card shows them); it is null without 5 such films or a later rated film. Counts toward the predict limit |
| GET | `/api/v1/people/{id}/career/model?role=acting\|directing&genre=` | The score model on "Their usual film" and "Something new" (each with the recipe it scored, never a budget) plus up to 4 never-done genre chips; with `genre`, only that "Something new"; cached, counts toward the predict limit |
| GET | `/api/v1/companies?q=`, `/api/v1/collections?q=` | Studio and franchise autocomplete |
| GET | `/api/v1/meta/options` | Every form field and limit from the contract, the 27 themes, common languages and countries, suggested years |
| GET | `/api/v1/model-card` | The served models' accuracy: the 2019+ test and the 2026 holdout next to the best baseline, training films, the database's size and years, and the "within the uncertainty" thresholds |
| GET | `/api/v1/health` | Status, model version, database build, uptime, the prediction cache and `fresh` (V1.2: when the new and upcoming films were last merged in and how many there are, null before the first refresh) |
| POST | `/api/v1/auth/demo`, `/api/v1/auth/login`, `/api/v1/auth/logout`; GET `/api/v1/auth/me` | The demo account's session ([Accounts](app.md#accounts-day-14)) |
| GET, PUT, DELETE | `/api/v1/me/movies`, `/api/v1/me/movies/{id}`, `/api/v1/me/movies/status?ids=` | Your watched list (date, 1–10 rating) and watchlist |
| GET, POST, PATCH, DELETE | `/api/v1/me/movies/{id}/notes`, `/api/v1/me/notes`, `/api/v1/me/notes/{id}` | Your private notes |
| GET | `/api/v1/random?source=all\|watchlist&genre=&decade=&language=&max_runtime=&gems=&exclude=` | "Surprise me": one random film you haven't watched, or one from your watchlist, with posters for the shuffle ([Surprise me](app.md#surprise-me-day-145)) |

**Predictions.**
- **The form:** `/predict` takes the creator form from `ml/features/contract.py`. People, companies and the franchise can be an id from autocomplete, a typed name or `{id, name}`. Leave `budget` out and it is estimated.
- **The output:** exactly what `predict()` returns, plus `cached` and full TMDB poster URLs for the comparables. The OpenAPI schema documents every field, for the Day 10 TypeScript types.
- **The model card:** `uv run python -m ml.eval.model_card` copies the numbers from `reports/final_test.json` and `reports/audit_metrics.json` into `ml/artifacts/final/model_card.json` (committed, because the image has no `reports/`). Per target it has the films, the share inside the range, the typical miss of the middle (money as a factor, exp(MAE log); score in points), within 2× and the median range width, for LightGBM and for B2. `/model-card` adds the database's films and years, and answers 503 if the card was written for other models than those being served. `tests/ml/test_model_card.py` fails when the committed card no longer matches the reports.
- **"Within the uncertainty" (Day 13):** the card also holds the thresholds the compare page uses. A change between two versions of a film counts only if it moves the middle by at least a tenth of the median 80% range on validation (2016–18, `reports/metrics.json`). For money that is a factor of width^0.1, because the width is high ÷ low: **×1.43** for revenue (×1.47 with the budget estimated) and **×1.23** for budget. For the score it is **0.17 points**.
- **Compare:** each variant lists only the fields it changes, and `null` clears an optional one. For each variant, `differences` gives the changed fields, the money middles as a ratio of the base's (×1.8), the score as a point difference (+0.3), and whether the revenue mode changed.
- **Sweep (Day 13):** `{form, field, values}` tries one field at each value, e.g. the 12 months of the planned year, and returns the budget, revenue and score ranges at each, plus the revenue mode. It counts as one request against the rate limit, and every point goes through the prediction cache.

```bash
curl -s localhost:8000/api/v1/predict -H 'Content-Type: application/json' -d '{
  "genres": ["Drama"], "release_year": 2026, "release_month": 10, "runtime": 105, "language": "en",
  "certification": "R", "director": 45400, "actors": [36592, 1373737, 1190668, "Ann Newcomer", "Bo Unknown"],
  "themes": ["family", "coming of age and school"], "companies": [41077], "countries": ["US"]}'
```

**Errors.** Every 422 has one shape, `{"detail": "Some fields need fixing", "errors": {field: message}}`, and one response lists every problem:
- **Messages:** they come from the contract, so a wrong type reads like a wrong value: `{"runtime": "must be a number", "themes": "required", "genres": "unknown value(s): 'Cartoon'"}`.
- **Compare:** errors name the variant, e.g. `variants.1.budget`.
- **Sweep:** errors name the form's field (`form.runtime`) or the value (`values.3`).
- **Other errors:** an unknown film is a 404, and a wrong method a 405.
- **In the schema:** every 422 is documented as this shape (`FieldErrors`), and 404 and 429 as `{"detail"}`, so the frontend's generated types match what the API sends.

**Limits and caching.**
- **Rate limit:** 30 prediction requests a minute per IP, shared by `/predict`, `/compare` and `/sweep` (our own sliding window, in memory). The 31st gets a 429, "Please try again in a minute", with `Retry-After`.
- **Read limit (V1.1):** 120 GET and HEAD requests a minute per IP on everything under `/api/` but `/health` (Docker's healthcheck and the smoke test call it), counted apart from predictions (`RATE_LIMIT_READ`). Typing in the header search costs 1–3 requests a pause, so a visitor never comes near it; the 121st gets a 429 with `Retry-After`.
- **Prediction cache:** the 1,000 most recently used predictions are kept (LRU), keyed by the validated form, so the same film written two ways is one entry.
- **HTTP caching:** movie, autocomplete, options and model-card responses are cacheable for an hour (`Cache-Control: public, max-age=3600`); health is `no-store`.
- **Settings:** `MOVIES_DB`, `MODELS_DIR`, `CORS_ORIGINS` (default the Vite dev server), `RATE_LIMIT`, `RATE_LIMIT_READ`, `CACHE_SIZE` and `USER_DATABASE_URL` come from environment variables, or from `.env`.

**Search and lookups.**
- **Search:** every word of `q` is a quoted prefix in SQLite FTS5, over titles, original titles and overviews, with accents ignored. Typed text can never be FTS syntax.
- **Similar films:** they come from the Day 7 index with no date rule, any year but never the film itself.
- **Autocomplete:** in memory. Any word of a name can start the match ("hanks", "tom ha"), and the names with the most films come first. The 398k names and their word keys are packed into byte blobs, about 33 MB; plain Python lists took about 207 MB.
- **The database:** opened read-only (`mode=ro`), with one connection per request, so the API cannot write to it.

**Measured** on this Windows laptop with the real models:

| | |
| --- | --- |
| Startup (models, feature context, comparables, lookups) | about 10 s |
| `/predict` over HTTP, uncached | median 167 ms (under the 400 ms target); about 3 ms from the cache |
| `/predict/compare` with 3 variants, uncached | about 0.5 s |
| `/predict/sweep` over 12 months, uncached | 1.6 s in Docker (12 predictions); cached, a few ms |
| Autocomplete / movie search / movie page | 2–10 ms / 5–90 ms / about 20 ms |
| Memory after startup / after predictions with a synopsis (MiniLM loaded) | 639 MB / 746 MB on Windows, before the Day 9 cuts; in Docker now 323 MB / 407 MB ([Running with Docker](deployment.md#running-with-docker)) |

Memory was 1,236 MB at first. The track record (`ml/features/history.py`) kept 350k small objects (about 870 MB); it now packs them into flat arrays (about 108 MB), and the rebuilt features table is bit-for-bit identical to the stored one. Day 9 brought the app under the 450 MB gate for the free host.

`tests/api/test_api.py` (63 tests, offline, on a small fake database and small models) checks:
- every endpoint, pinned to a list so a new one must get a test;
- both revenue modes, the cache, compare's differences, a 12-month sweep equal to single predictions, every kind of 422, and the 31st request;
- FTS input that would be syntax, pages, filters and sorting;
- similar films that never include the film itself, read-only connections, and parallel requests.

`tests/api/test_api_golden.py` (10 tests, skipped without the real data and models) checks:
- the golden forms over HTTP equal `predict()` and the snapshot, in under 400 ms;
- real autocomplete, movie pages, options and health.
