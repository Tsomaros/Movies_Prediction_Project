# Changelog

## Unreleased

- **V1.2 – New Arrivals:** live "New Arrivals" (released in the last 14 days) and "Coming soon" (the next 60) rows on `/movies` and the default `/browse`, from a 6-hour in-memory TMDB cache with a stale fallback and a startup warm-up (no scheduler, nothing stored). A quick view for films not in our database, a `/new-and-upcoming` page with tabs, and live matches in the header search and the browse results. API: `GET /api/v1/movies/new-and-upcoming` and `live_matches` on `GET /api/v1/movies`. Needs `TMDB_READ_TOKEN` on the server. **The 2026 films** released up to 2026-10-30 (1,199) are now in the database (80,398 films) for browsing, search and the film and person pages; a snapshot test shows that no model, track record, feature or comparable sees them, so the models and the model card are unchanged. Not deployed yet.
- **The Movies | People switch** only changes what the box searches on a results page too (on `/browse` it could not be switched with an empty box).
- **Quick list buttons on every film list** when logged in: the home rows, person pages, a film's Similar films, the results page's Films like yours and the list views, beside browse and My movies. On phones they are always shown; with a mouse they appear on hover. Not deployed yet.

## V1.1 – Header search (2026-10-29)

- **One search bar in the header**, with a **Movies | People** switch, on every page with a header except Series. Quick results while typing (the top 5 in the current mode), Enter for the full results, ↑/↓ to pick a row, `/` to focus it from anywhere. On phones, a search icon opens a full-screen search.
- **People results page** `/people?q=`: actors, directors and writers, 24 a page, with All · Actors · Directors · Writers chips and their counts. Writers can be searched for the first time.
- **Wrong-mode hint:** an empty search points to the other mode when it has hits ("No movies match ‘tom hanks’. 1 person found → See people").
- **Browse** has no search box or people row of its own any more; a "Results for ‘…’" chip shows the header's search and removes it.
- **API:** `GET /api/v1/people/search` (paged, with counts per role), and a read limit of 120 GET requests a minute per IP, apart from the 30 predictions a minute.
- No data, database or model changes. Details: [The app](docs/app.md#header-search-v11) and [API](docs/api.md).

## V1.0 (2026-10-27)

The first live version: [README](README.md) and [PROGRESS.md](PROGRESS.md) Days 1–16.
