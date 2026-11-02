# Changelog

## V1.5 – Speed pass and review fixes (2026-11-01 to 2026-11-02)

- **Faster with identical predictions:** at 0.1 CPU in local Docker, a cache-miss `POST /predict` went from a 5.6 s median to 1.3 s, a compare with 3 variants from 24.4 s to 3.7 s, the 12-month sweep from 70.8 s to 0.5 s, a home row from 1.2 s to 0.1 s and startup from 86-100 s to 27-32 s. `scripts/perf_check.py` shows the outputs are unchanged. 4 of the 9 speed gates pass. Render itself hasn't been measured since. Details: [docs/perf/after.md](docs/perf/after.md).
- **How:** predictions run in batches, a sweep computes ranges only, the autocomplete is prebuilt (`LOOKUPS_FILE`), the browse sorts have their own indexes and `/health` only runs `SELECT 1`. `/predict`, `/predict/compare` and `/predict/sweep` answer `X-Cache: hit|miss`.
- **"Waking up the server…"** covers a loaded page while the API is slow. It can't cover a cold start, when nothing answers yet, the page included.
- **A merge can't break reads:** reads wait up to 30 s for the background merge's commit, instead of answering 500 at 0.1 CPU.
- **Stricter input:** a code with a trailing newline, an id beyond 2³¹-1 and non-ASCII digits in status ids are refused, and a huge film id is a 404.
- **Accounts:** only a user's newest 1,000 sessions are kept.
- **Predict:** the people warnings follow the features the models saw. Retry opens the results, and a failed name search no longer offers a new name.
- **Accessibility:** solid focus rings, a skip link, a header brand that fits narrow phones and other fixes from the UI review.
- **The accuracy panel** states the training data correctly, and Browse's years and the About page were updated.

The models and the model card are unchanged.

## V1.2 to V1.4 (2026-10-30 to 2026-10-31)

- **V1.4 – Career and 2026:** person pages now draw a person's 2026 films. A score under 182 days old is a dashed "settling" dot: it is shown but not counted in the forecast. When a person has 5+ counted films up to 2025 and a rated 2026 film, a check line says what the range from films up to 2025 was and whether the new film landed inside (Nolan: "From films up to 2025 we said 6.6 – 8.3. The Odyssey scored 8.0 so far (still settling), inside."). "How is this calculated?" under the forecast states its 2026 coverage, with "(a small sample)" under 100 films. On 2026 films the range covers 72.8% (acting, 935 films), 71.4% (directing, 58) and 82.9% (writing, 74); nothing was re-tuned. API: `settling` on career films, `check` and `forecast.test.holdout` in `/people/{id}/career`; `career_forecast.json` is version 2. The models and the model card are unchanged.
- **V1.3 – One movies database:** the new and upcoming films are merged into `movies.db` itself every 6 hours, in one transaction, instead of living in a second `fresh.db` read through views. Nothing changes on the pages. Only films dated after 2025 are written and no film the models read is ever replaced, so the models, their data and the model card are unchanged (a snapshot test checks it on a merged copy). The refresh runs only with `FRESH_REFRESH=1`, which the image sets; `FRESH_DB` is gone.
- **Top rated needs 500+ votes:** the Top rated row on `/movies` and Browse's "Highest score" sort now keep only films with 500 or more votes (was 50), so a film with a handful of votes can't top the list. The models' own 50-vote floor is unchanged.
- **V1.2 – New arrivals:** one **New arrivals** row on top of `/movies` with a *Just released | Coming soon* switch (the last 14 days, the next 60), "See all" opening Browse with the same window. New films are ordinary films: they have a film page, quick list buttons, ratings, notes, "Predict a film like this" and appear in the header search. Cards say **New** or "Coming 20 Nov" (and "Not rated yet" under 50 votes); Browse has a *Release* menu and a *Soonest first* sort. Behind it a small `fresh.db` (same schema as the movie tables) is rebuilt from TMDB in the background every 6 hours and read beside `movies.db` through attached views; no scheduler, no new service. API: `GET /api/v1/movies?when=released|upcoming`, the `soonest` sort, `fresh` in `/health`, `linked` on cast and crew. Needs `TMDB_READ_TOKEN` on the server.
- **The 2026 films** released up to 2026-10-30 (1,199) are now in `movies.db` (80,398 films) for browsing, search and the film and person pages; a snapshot test shows that no model, track record, feature or comparable sees them, so the models and the model card are unchanged.
- **The Movies | People switch** only changes what the box searches on a results page too (on `/browse` it could not be switched with an empty box).
- **Quick list buttons on every film list** when logged in: the home rows, person pages, a film's Similar films, the results page's Films like yours and the list views, beside browse and My movies. On phones they are always shown; with a mouse they appear on hover.

## V1.1 – Header search (2026-10-29)

- **One search bar in the header**, with a **Movies | People** switch, on every page with a header except Series. Quick results while typing (the top 5 in the current mode), Enter for the full results, ↑/↓ to pick a row, `/` to focus it from anywhere. On phones, a search icon opens a full-screen search.
- **People results page** `/people?q=`: actors, directors and writers, 24 a page, with All · Actors · Directors · Writers chips and their counts. Writers can be searched for the first time.
- **Wrong-mode hint:** an empty search points to the other mode when it has hits ("No movies match ‘tom hanks’. 1 person found → See people").
- **Browse** has no search box or people row of its own any more; a "Results for ‘…’" chip shows the header's search and removes it.
- **API:** `GET /api/v1/people/search` (paged, with counts per role), and a read limit of 120 GET requests a minute per IP, apart from the 30 predictions a minute.
- No data, database or model changes. Details: [The app](docs/app.md#header-search-v11) and [API](docs/api.md).

## V1.0 (2026-10-27)

The first live version: [README](README.md) and [PROGRESS.md](PROGRESS.md) Days 1–16.
