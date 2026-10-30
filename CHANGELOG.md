# Changelog

## Unreleased

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
