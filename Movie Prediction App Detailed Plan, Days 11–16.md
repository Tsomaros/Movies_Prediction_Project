# Movie Prediction App: Detailed Plan, Days 11–16

Oct 22, 2026 · @Dimitris (Day 14 and Day 14.5 inserted Oct 24, Day 14.6, 14.7 and 14.8 Oct 25, 2026)

## Overview

Week three (Days 11–16) takes the project from a working form to a deployed, documented, demo-ready app. Each day was planned the same way as before: Claude researched and proposed options, Dimitris chose, and a day was only closed once he approved it.

**What week three adds**

- **Day 11:** the results page, with ranges, a break-even band, drivers, comparables and honest accuracy numbers.
- **Day 12:** the public side: browse, detail pages, curated home rows and TMDB attribution.
- **Day 13:** compare with up to 3 variants, a release-month sweep, every error state, and a quality pass.
- **Day 14:** a one-click demo account with a watched list, a watchlist, ratings and private notes, stored in Neon Postgres.
- **Day 14.5:** "Surprise me": a random unseen film or a pick from your watchlist, with a poster-shuffle reveal and filters.
- **Day 14.6:** actor pages: TMDB photo and biography, stats from our data, a sortable filmography, and "Predict a film with this actor"; people in browse search.
- **Day 14.7:** the same pages for crew (directors, writers, producers and the rest) with a role switch, and cast photos on film pages.
- **Day 14.8:** a Career section on person pages: scores over the years, a backtested next-film forecast, and the score model on their usual film and something new.
- **Day 15:** deployment on Render Free (no card), monitoring and an interview-day safety net.
- **Day 16:** documentation, model card, demo script and interview preparation.

**Schedule change (Oct 24).** Day 14 (accounts) was inserted; deployment moved from Day 14 to Day 15 and documentation from Day 15 to Day 16. A movie chat assistant is listed in the README's next steps.

**Principle for this week:** the app should be understandable in 5 seconds and trustworthy on a closer look. Every number shown comes from the model or the test results, never typed by hand.

## Day 11: Results page

Day 11 ends with a results page a creator understands in 5 seconds and trusts on a closer look, with every number backed by the model and the honest test results.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Page order | Summary → range chart → drivers → comparables → notes → actions | Answer first, then the why |
| Range chart | Custom Tailwind + SVG range bars; log money axis, 0–10 score axis | Light, fast, on-brand |
| Budget vs revenue | One shared money axis with a break-even **shaded band at 2×–2.5×** budget, labelled as a rule of thumb | Answers "will it make money?" without a fake probability |
| Numbers | 2 significant figures for money, one decimal for score, "2025 dollars, worldwide" stated once | No false precision |
| Badges | "Rough estimate", "Budget estimated", budget comparison | Uncertainty visible where it matters |
| Drivers | Tabs per target (opening on Revenue), up/down columns, 1–3 strength bars | Focused, not overwhelming |
| Accuracy | New `GET /api/v1/model-card` endpoint feeds a "How accurate is this?" panel | Numbers always match the deployed model |
| Print/PDF | Included; moves to Day 13 if time runs short | Creators can attach results to a pitch |

### Tasks

1. **Model-card endpoint (45 min).** Test metrics, data range, number of films, model version and training date, generated from artifact metadata; tested; added to the README.
2. **Page and summary cards (1.5 h).** `/predict/result` reads the input from the URL; skeleton loading; three cards with expected value and range; badges.
3. **Range chart (1.5 h).** Low-to-high bars with an expected marker; shared log money axis; the break-even band; a separate score bar; screen-reader text; readable on phones.
4. **Drivers (1 h).** Tabs, up/down columns, strength bars + words; colour-blind-safe colours with icons and text.
5. **Comparable films (1 h).** 5 cards (poster, title, year, real numbers or "not reported"), a "why similar" tag, links to detail pages.
6. **Notes (45 min).** Always-visible limitations note; new-person note; accuracy panel from `/model-card` with a README link.
7. **Actions (1 h).** Edit inputs, try a variation, share URL, print stylesheet.
8. **Tests and checks (45 min).** The golden examples render correctly (badges, notes, formatting, model-card numbers); manual phone, theme and print checks.
9. **Wrap-up (15 min).** `PROGRESS.md`, README screenshot, commit.

**Done when** a submitted form leads to a complete results page with ranges, break-even band, drivers, comparables, honest accuracy numbers and working actions, on desktop and mobile, in both themes.

## Day 12: Public browse, detail page and attribution

Day 12 ends with a public side that feels like a real movie site, connected to the creator tool, with TMDB attribution on every page. Changeable parts live in config so they're easy to adjust later.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Paging | Numbered pages, kept in the URL | The URL always says where you are |
| Grid control | Three poster sizes (small/medium/large) plus a list view, remembered | Users choose how dense the grid is |
| Filters | Genre, year range, language, score; "has budget/revenue data" dropped | Score is more useful to visitors |
| Low-vote films | Included in the score filter and "Top rated" row; vote count always shown next to the score, e.g. "9.4 (12 votes)" | Nothing hidden; visitors can judge |
| Cast without photos | Initials avatars with a name-derived colour | Looks deliberate, consistent per person |
| Money on detail page | Toggle between original and 2025 dollars | Shows the inflation work |
| "Predict a film like this" | Button pre-filling the creator form; mapping in one isolated function | Connects both halves; easy to change later |
| Home page | 3–4 curated rows from one config file | Feels alive; one-line edits later |
| About page | Included | A mini case study for interviewers |

### Tasks

1. **Backend additions (45 min).** Score filter on `GET /movies`; drop the money-data filter; curated rows use existing filters; tests updated.
2. **Browse page (2.5 h).** Search as you type (300 ms); filters; sort (popularity, newest, title, score); numbered pages; grid size control + list view; sidebar on desktop, drawer on mobile; no-results state with clear-filter buttons; everything in the URL.
3. **Posters (30 min).** Two sizes, lazy loading, fixed 2:3 ratio, designed placeholder.
4. **Movie detail page (2 h).** Header facts and overview; score with votes; money with the toggle; cast with characters and initials avatars; key crew; similar films; "Data from TMDB" note.
5. **"Predict a film like this" (45 min).** Pre-fills genres, themes, runtime, language, certification, director and cast.
6. **Curated rows (1 h).** "Most popular", "Top rated", "From the 1990s", "Biggest box office (2025 $)" from one config file.
7. **Attribution and About (1 h).** Footer on every page: TMDB logo (less prominent, unaltered), the required notice, a TMDB link. About page: data source, how predictions work, model-card numbers, limitations, GitHub link.
8. **Quality and tests (45 min).** Per-page code loading; movie titles in browser tabs; keyboard-navigable grid; alt text. Tests: URL round-trips, detail page with and without money, pre-fill mapping, attribution on every route.
9. **Wrap-up (15 min).** `PROGRESS.md`, screenshots, commit.

**Done when** a visitor can search, filter and page through films, open a detail page, jump to a pre-filled prediction, and see the TMDB attribution everywhere, on desktop and mobile, in both themes.

## Day 13: Compare, release-month sweep, edge cases and final polish

Day 13 ends with a "what if" tool that makes differences easy and honest to read, an app that handles every failure gracefully, and a measured quality pass on all key pages.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Building variations | One change per variant, with a manual picker plus quick presets | A clear cause for each difference; a fast demo |
| Honest differences | Small changes compared with the range width are greyed out: "within the uncertainty" | The app says when a change doesn't matter |
| Month sweep | Included, via a new `POST /api/v1/predict/sweep` endpoint (field + values) | One request; reusable for runtime or budget later |
| Edge cases | The list below, no additions | Covers every realistic failure |
| Quality pass | Lighthouse audit + keyboard-only run + cross-browser check | Measured, not assumed |
| Cuts | **None.** Day 13 may continue into the Day 14 session | Deployment is mostly waiting and checking |

### Tasks

0. **Carry-overs first (0–3 h).** Fuzz testing (Day 9), shareable URL and auto-save (Day 10), print/PDF (Day 11), if their cut lines were used.
1. **Compare: building variations (1.5 h).** `/predict/compare` from "Try a variation"; up to 3 variants, each one change; presets "Holiday release", "Make it a franchise", "Double the budget", "Unknown cast", "PG-13 instead of R"; variants kept in the URL.
2. **Compare: the view (1.5 h).** Columns on desktop, stacked on mobile; shared money axis with break-even bands; changes per target; driver-change lines.
3. **Honest differences (45 min).** Threshold set from validation, stored in the model card, read by the frontend.
4. **Month sweep (1.5 h).** New sweep endpoint (same rate limit as predict); chart of expected revenue and range for 12 months; the creator's choice highlighted; months within the uncertainty of the best marked "about as good".
5. **Edge cases and error states (2 h).**

   | Situation | What the user sees |
   | --- | --- |
   | Server waking up | After 3 s: "Waking up the server, this can take up to a minute on free hosting" |
   | API down or network error | Friendly message with retry; form keeps its content |
   | Too many requests (429) | "You're going a bit fast. Try again in a minute" |
   | Unknown director or actor | "New person" chip in the form; note on results |
   | Broken shared URL | Invalid fields dropped, the rest pre-filled, a notice of what was removed |
   | Movie not found | 404 page with search and home links |
   | Unexpected crash | Error boundary with reload; the rest keeps working |
   | Slow connection | Skeletons everywhere, no layout jumps |
6. **Final quality pass (1.5 h).** Lighthouse on home, browse, form and results, top issues fixed, scores in the README; keyboard-only creator flow; Chrome, Firefox, Safari/WebKit and one phone.
7. **Tests (45 min).** Presets change one field; uncertainty label; sweep returns 12 months; simulated 429, network failure and 404; broken URL recovery.
8. **Wrap-up (15 min).** `PROGRESS.md`, compare and sweep screenshots, commit.

**Time:** about 10 hours, up to 13 with all carry-overs; overflow continues into the Day 14 session.

**Done when** a creator can compare up to 3 variations and sweep release months with honest uncertainty labels, every error state shows a helpful message, and Lighthouse scores are recorded.

## Day 14: Test user, watched list, watchlist and notes

Day 14 ends with one demo user who logs in with one click, tracks watched films with a date and a 1–10 rating, keeps a plan-to-watch list, and writes private notes on any movie. The data lives in Neon Postgres so it survives Render's sleep and redeploys, and it resets to a tidy starting set every night.

**Why a separate database.** Render Free web services have an ephemeral filesystem: anything written at runtime, including a SQLite file, is lost on every redeploy, restart or spin-down after 15 minutes idle. Movies stay in the read-only SQLite database baked into the image; user data goes to Neon.

**Principles for this day**

- The movie database and the public endpoints don't change; they stay read-only and cacheable.
- Every user table has `user_id`, so real users later need no schema change.
- The database enforces the rules (one list per film, rating only on watched films), so the API can't create bad states.
- One shared demo account is safe: private notes, write limits, caps and a nightly reset.
- Without `USER_DATABASE_URL` the accounts endpoints answer 503 and everything else works as before.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| User data | Neon Postgres Free, Postgres 18, Frankfurt (`aws-eu-central-1`); movies stay in read-only SQLite | Survives sleep and redeploys; permanent free tier, no card |
| Rejected storage | Supabase (pauses after 7 days idle), Render Postgres (expires after 30 days), SQLite in the container (wiped on sleep) | Each would break the live demo at some point |
| Local dev and tests | `postgres:18` in `docker compose`; tests use a throwaway database there, marked `pg` and skipped when no Postgres is reachable | Same engine everywhere; `make test-fast` stays offline |
| DB access | psycopg 3 + plain SQL in a small repository layer; small pool (1–4), direct connection | Same style as the SQLite side; no PgBouncer quirks |
| Migrations | Numbered SQL files plus a short runner that records what ran | Enough for a few tables |
| Lists | Watched or plan-to-watch, one per film; watched date defaults to today; optional 1–10 rating on watched films | Simple, enforced by the database |
| Notes | Private, many per film, newest first, max 2,000 characters | No moderation; works like a journal |
| Login | "Try the demo account" button first, small password link below | Interviewers get in with one click |
| Sessions | Sessions table, SHA-256 of a random 32-byte token in Postgres, httpOnly cookie, fixed 7 days; no session secret | Logout really ends a session; a hash of a random token needs no key |
| Secrets | `USER_DATABASE_URL` and `DEMO_PASSWORD` only | Nothing unused to configure |
| Passwords | argon2id at OWASP minimum (19 MB, 2 passes) | Safe on a 512 MB server |
| Nightly reset | Lazy, on the first demo login after midnight Athens time, guarded by an advisory lock | No cron on Render Free |
| Abuse limits | 30 writes/min per user; 500 list entries and 200 notes; login 5/min, demo login 10/min per IP | One account is shared by everyone |
| Client IP | uvicorn's proxy headers with `FORWARDED_ALLOW_IPS`, done now instead of on deployment day | Per-IP login limits need the visitor's address, and the Secure cookie needs the real scheme |
| Logged-out click | Login dialog opens in place, then the action completes | No lost clicks |
| Card buttons | Quick buttons on hover (desktop); badges only on phones | Clean grid on small screens |
| Rating input | 10 stars, shown as "8/10" | Matches the 0–10 TMDB scale |
| E2E | One Playwright flow, reused on Day 15 against the live site | Proves the whole path works |

### Tasks

1. **Neon and schema (1 h 15 min).** Neon project (Frankfurt, Postgres 18), `USER_DATABASE_URL` with `connect_timeout=10` (the Free compute suspends after 5 minutes idle and takes 0.5 s to a few seconds to wake). psycopg pool of 1–4 with a check before each checkout. `backend/app/userdb/migrations/001_init.sql` and a runner recording `schema_migrations`. Tables `users`, `user_movies` (primary key user and movie; rating and date only when watched), `comments` (1–2,000 characters), `sessions`, `app_state`; UTC `timestamptz`; deleting a user deletes their rows; `movie_id` is checked by the API, with no cross-database key. `demo_seed.json` (about 12 watched, 8 on the watchlist, 4 notes) and a seed script that refuses ids missing from the movie database.
2. **Auth (1 h 30 min).** `POST /auth/login`, `POST /auth/demo`, `POST /auth/logout`, `GET /auth/me` (`{"user": null}` when logged out, not a 401). Cookie `mp_session`: httpOnly, Secure on https, SameSite=Lax, path `/`. CSRF: SameSite=Lax plus a matching `Origin` and JSON on every write. A wrong password always says "Wrong username or password". The demo login runs the nightly reset in one transaction under `pg_advisory_xact_lock`.
3. **User endpoints (1 h 45 min).** Under `/api/v1/me`, private and `Cache-Control: private, no-store`: `GET /me/movies` (one tab plus counts for all three), `PUT` and `DELETE /me/movies/{id}`, `GET /me/movies/status?ids=` (up to 48), `GET` and `POST /me/movies/{id}/notes`, `GET /me/notes`, `PATCH` and `DELETE /me/notes/{note_id}`. The user's rows (at most 500) are joined with SQLite in one query and sorted and paged in Python, returning the `/movies` card shape. Unknown film or someone else's note → 404; over the caps → 409; over the write limit → 429.
4. **Frontend (3 h).** `useMe`; `/login` with the big demo button; a login dialog for logged-out clicks; header avatar, "Demo" chip and menu; on the film page Watched / Plan to watch / Not in a list, a date, 10 stars and notes (2,000-character counter, Ctrl+Enter, inline edit, delete with Undo); badges and hover buttons on the browse grid from one status call per page; `/my-movies` with Watched, Plan to watch and Notes tabs, state in the URL, "Demo data resets every night"; optimistic updates with rollback; keyboard stars announcing "8 out of 10".
5. **Tests (1 h 45 min).** Auth, lists, notes, caps and limits, the reset with a frozen clock and two simultaneous logins, against the compose Postgres; Vitest for the dialog, rollback, stars and URL state; one Playwright flow (demo login → watched with a rating → note → My movies).
6. **Wrap-up (15 min).** README section on accounts and the demo button, `PROGRESS.md`, commit.

**Time:** about 9.5 hours.

**Cut line:** if behind, the Playwright flow moves to the Day 15 session first, then the Notes tab. The demo button, lists, rating, notes on the detail page and the reset always stay.

**Done when** the demo button logs in, both lists, ratings and notes work on desktop and mobile in both themes, data survives a container restart, the reset brings back the starting set, and all tests pass.

## Day 14.5: "Surprise me" random picker

Day 14.5 ends with a "Surprise me" button in the header that picks a random film, either one you haven't seen from the whole database or one from your watchlist, with a short poster-shuffle reveal and optional filters. It was planned the same way as the other days: Claude proposed options, Dimitris chose.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Sources | "Anything I haven't seen" (whole database minus watched) and "From my watchlist" | Covers both "find me something new" and "pick from my list" |
| Quality | Whole-database mode: 200+ votes and score ≥ 6.0 (11,043 films with a poster; 100/6.0 gave 16,084, 500/6.5 gave 4,726). "Include hidden gems" removes the floor but still needs a poster (78,346 of 79,199 films). Watchlist mode has no floor | Pure random surfaces mostly obscure films; you chose your watchlist yourself; the reveal is a poster shuffle |
| Placement | Button in the header opening a dialog (bottom sheet on phones) | Reachable from every page; one component, easy to move |
| Filters | Optional and collapsed: genre, decade, language, max runtime; remembered in the browser | One click still works; "I have 100 minutes" is useful |
| Reveal | Posters shuffle for about 1 s, then settle; instant with "reduce motion" | Fun without slowing repeat spins or hurting accessibility |
| Re-rolls | "Spin again" never repeats a film in the open tab (shown ids sent as `exclude`, at most 200) | Five spins give five different films |
| Logged out | Whole-database mode works (no watched exclusion, also with no accounts database); watchlist mode opens the login dialog, then spins | Same pattern as the rest of Day 14 |
| Empty states | A 200 with `movie: null` and a reason: `watchlist_empty`, `no_match` (the filters match nothing), `all_seen` (everything matching is watched or shown) | The dialog shows a helpful message, not an error |
| Rate limit | Its own limiter, 60 a minute per IP (browse has none) | Picks can't be cached like browse pages |
| Data access | Watched/watchlist ids from Postgres, candidates from SQLite, the pick made in Python | User data and films live in different databases; about 11k ids is a few ms |

### Tasks

1. **Quality floor check (15 min).** Count candidates at a few vote/score thresholds; the floor lives in `services/random_pick.py`.
2. **Endpoint (1 h).** `GET /api/v1/random?source=all|watchlist&genre=…&decade=…&language=…&max_runtime=…&gems=false&exclude=…`, service code in `services/random_pick.py`. Returns the browse card shape plus runtime and about 8 extra posters for the shuffle; `Cache-Control: private, no-store`.
3. **Backend tests (45 min).** Never a watched film; watchlist mode only watchlist films; the floor only in whole-database mode and `gems=true` removes it; each filter; `exclude` prevents repeats; each empty state; logged-out watchlist → 401.
4. **Dialog and header button (1 h).** Dice icon; dialog on desktop, bottom sheet on phones; source switch; collapsed filters remembered in the browser.
5. **Reveal and result card (45 min).** Poster shuffle then settle; poster, title, year, score with votes, runtime, genres; Open details, Add to watchlist, Mark as watched (also takes it off the watchlist), Spin again.
6. **Empty states (20 min).** "Add films first" with a browse link; "Loosen a filter" with clear filters; a friendly "all seen" with Start over.
7. **Demo account seed (15 min).** Check the demo user has watched and watchlist films, so both modes demo well.
8. **Frontend tests and checks (30 min).** Vitest: logged-out watchlist opens the login dialog; reduce motion skips the animation; empty states. One spin in the Playwright flow. Phone and theme check.
9. **Wrap-up (15 min).** `PROGRESS.md`, README section and screenshot, commit.

**Time:** about 5 hours.

**Done when** a visitor can spin a random unseen film with or without filters, a logged-in user can spin from their watchlist, re-spins never repeat, every empty state shows a helpful message, and it works on desktop and phone in both themes.

## Day 14.6: Actor pages

Day 14.6 ends with a page per actor (`/people/:id`): TMDB photo, biography and life dates when TMDB has them, a stats strip from our own data, a sortable poster grid of their films, and "Predict a film with this actor". Browse search shows matching people above the films, and cast and director names on film pages link to these pages. It was planned in `2026-10-25-actor-pages.md` (Dimitris's document) and adapted to the code before the build.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Pull scope | Cast members with 2+ films: 118,245 people, about 1 h 40 min at 20 requests a second (every cast id is 321,259, about 4.5 h) | Everyone still gets a page from our data; one-film actors just have no photo or biography |
| Into the database | An add-on step, `make people-db` (`python -m ml.data.people load`), fills `person_details` in the existing `data/movies.db`; `build_db` runs it too when the pull file exists | No re-pull, no features rebuild; `meta.build` (built_at, films) and the models stay untouched |
| Search | Keep the in-memory autocomplete behind `GET /people` (already word-prefix, "tom ha"), now folding accents ("penelope" finds Penélope), and add `thumb` and `known_for` to its hits from one SQL query; no `people_fts` table | The form's autocomplete keeps working as it is; no bigger database |
| Image size | Measure what the details add and report it; cut biographies to 1,500 characters only if they add more than about 50 MB | The image is already 984 MB, above the old ~700 MB aim |
| Popularity | `tmdb_popularity` only for display and ordering ties, never a model input | Pre-release inputs only |
| Commits | One commit per task | Dimitris's choice |

### Tasks

1. **Person records:** `ml/data/people.py` slims and cleans one TMDB `/person/{id}` record (blanks and impossible dates become empty; only http(s) homepages and `nm…` IMDb ids).
2. **Resumable pull:** `make people`, reusing the film pull's runner; `--refresh-older-than 180` for TMDB's six-month rule.
3. **`person_details` table** and the load step, with coverage stats in `meta`.
4. **Queries:** person, credits (cast and crew), stats (films, years, top genres, average score over films with 50+ votes, box office over trusted 2025 $, top co-star and director with 2+ shared films).
5. **API:** `GET /api/v1/people/{id}`; `GET /people` hits gain `thumb` and `known_for`.
6. **Frontend helpers:** `usePerson`, `formatLife`, the person → form mapping.
7. **Person page** (`/people/:id`, lazy): header, stats chips, sortable grid with characters, crew credits, predict button.
8. **People row** in browse search, and links from cast and crew names on film pages.
9. **Wrap-up:** real data load, smoke check, image size, README, `PROGRESS.md`.

**Done when** search → person page → sortable filmography → a pre-filled prediction works on desktop and phone in both themes, and all tests pass.

## Day 14.7: Crew pages and cast photos

Day 14.7 gives every crew member the actor-page treatment and shows TMDB photos for the cast on film pages. Dimitris asked for it after Day 14.6.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Crew pull | Every crew member: 121,214 more people (130,723 crew, 9,509 already pulled as actors), about 1 h 40 min | Every director, writer, producer, composer, cinematographer and editor gets a photo where TMDB has one |
| Cast photos | From the details we have: 71% of cast slots (687,568 of 968,355); the rest keep initials | No second 2 h 50 min pull for one-film actors |
| The page | One page with a role switch (Acting, Directing, Writing, Production, Music, Camera, Editing) for the roles a person has, in the URL as `?role=`, defaulting to their main role; the grid, stats and sort follow it | One page per person; a writer-director sees both sides |
| Predict | Acting: lead actor; Directing: director; no button for other roles | The form has no writer, producer or composer field |
| Search | The browse row adds directors; writers and producers are reached from film pages | Only actors and directors have an in-memory index; no new index under the memory gate |

### Tasks

1. **Crew pull:** `person_ids` adds every crew member; `make people`, then `make people-db`.
2. **Cast photos:** `GET /movies/{id}` cast gains `photo`; the film page shows it.
3. **Roles in the API:** credits and stats per role, `main_role`, collaborators per role.
4. **Role switch** on the person page; the director predict button.
5. **People row** with directors.
6. **Wrap-up:** real data, image and memory, smoke, README, `PROGRESS.md`.

## Day 14.8: Career chart and forecast

Day 14.8 adds a Career section to every person page, between the stats strip and the films: a chart of their film scores over the years, a track-record forecast for their next film checked by a backtest, and the score model on two made-up films, "Their usual film" and "Something new". Dimitris wrote the spec and plan (`2026-10-25-career-chart-design.md`, `2026-10-25-career-chart.md`); the work runs task by task with subagents.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Name | Day 14.8 | Day 14.7 is the crew pages; deployment stays Day 15 |
| Rated film | `score_ok` (50+ votes, `MIN_VOTES` in `ml/data/clean.py`) and a year; fewer votes are faint dots only | The plan says import the constant; the spec's "30" was a guess at it |
| Role | The page's own `?role=` switch; Career shows for acting, directing and writing, and says it isn't available for other roles. Only `?view=` is new | One switch per page; the forecast has no settings for crew roles |
| Lead | Acting credit with `ord <= 2` | `ord` is the cast order column |
| Forecast | Weighted track record shrunk toward the role's average, range `c ± q·σ` clipped to 1–10; h, k, q per role from the backtest | The spec's formulas |
| Backtest years | Tune on next films before 2019, report 2019+; history = strictly earlier release dates | Dimitris's choice: a separate model from the Day 5 ones |
| Model films | Recipes completed to a form the contract accepts: 5 actor slots (unknown ones as new names), themes and certification from recent films of those genres when their own films have none | `validate` needs 5–10 actors, 1+ themes and a certification |
| Scoring | Through the existing `PredictionService` (and its cache), score only shown; never a budget | The same path as `POST /predict` |
| Limits | Both career endpoints count toward the predict limit (30 a minute per IP) | The spec |
| Chart | Recharts, in the lazy person page chunk | The spec |
| Score only (follow-up) | The Revenue view that replaced "Compared with its year" was removed again, and the year toggle with it; films under 40 minutes stay out of the chart, forecasts and recipes | Dimitris's decision after seeing the revenue ranges |

### Tasks

1. **Career queries** (`repo/career.py`).
2. **Forecast maths** (`ml/career/forecast.py`).
3. **Backtest** (`ml/career/backtest.py`, `make career` -> `ml/artifacts/career_forecast.json`).
4. **Recipes** (`services/career_model.py`).
5. **Endpoints** `GET /people/{id}/career` and `/career/model`.
6. **Frontend hooks**, the explanation text and `recipeToForm`.
7. **Chart** and table.
8. **Section and cards** on the person page.
9. **Wrap-up:** image and memory, smoke, README, `PROGRESS.md`.

## Day 15: Deployment

Day 15 ends with the app live at a public link on a free host that needs no card, verified end to end, monitored, and backed up for interview day.

### Hosting options considered

| Host | Resources | Idle behaviour | Cost | Outcome |
| --- | --- | --- | --- | --- |
| **Render Free** | 512 MB RAM, 0.1 CPU | Sleeps after 15 min, about 1 min to wake | Free, no card | **Chosen** |
| Render Starter | 512 MB RAM, 0.5 CPU | Always on | $7/month | Paid |
| Google Cloud Run | Chosen memory and CPU | Scales to zero | Free tier, but needs a card | Rejected: card |
| Hugging Face Spaces | 2 vCPU, 16 GB RAM | Sleeps after 48 h | Docker Spaces need a paid plan | Rejected: paid |
| Fly.io / Railway | Usage-based | — | No free tier for new users / one-time $5 credit | Rejected |

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| Host | Render Free, Frankfurt region | The only free option that runs our container without a card |
| Frontend | Served by FastAPI from the same container | One URL, no CORS, fewest moving parts |
| Image (Oct 27) | Built here and pushed to a private GHCR image tagged by git commit; Render pulls it with a read token | About 470 MB the image needs (slim database, models, 8-bit MiniLM) is not in git, so Render can't build it; private keeps the TMDB-derived database from being downloadable |
| Deploys | Manual only: `make deploy` builds, pushes and calls the deploy hook with that commit's tag; image services never auto-deploy | A quick commit can't break the live demo; a rollback picks an earlier tag |
| Domain | Platform address | Free, works immediately |
| Speed | 400 ms local target; up to about 3 s live, stated honestly in the README | 0.1 CPU is slow |
| Memory | int8 MiniLM (done on Day 9); Day 9 gate under about 450 MB, startup peak checked under a 512 MB limit | Fits 512 MB safely |
| Monitoring (Oct 27) | A daily GitHub Action runs `scripts/smoke.py` against the live URL (waiting up to 3 min for the wake-up) and emails on failure; no 5-minute pings | Any uptime ping wakes the service, so frequent ones are a keep-alive |
| Sentry (Oct 27) | Backend and frontend, errors only (no tracing or replay), no personal data, off without a DSN; the frontend SDK loads lazily | Know about problems before the interviewer does, without growing the first page |
| Client IP (Oct 27) | The per-IP limits read `CF-Connecting-IP` (`CLIENT_IP_HEADER`), not `X-Forwarded-For` | Render appends to a visitor's own `X-Forwarded-For`, so forged values got past the limits; Cloudflare sets `CF-Connecting-IP` and refuses it from clients |
| Local copy (Oct 27) | `docker compose` runs the same single image as Render (app on :8080, API on :8000) | A clean clone can pull the image instead of rebuilding it from untracked files |
| Safety net | Warm-up routine, local `docker compose`, recorded demo | The demo works even if the network doesn't |

### Tasks

0. **Carry-over (if needed).** Finish Day 13 first.
1. **Single production container (1 h).** React build copied into the backend image and served by FastAPI; unknown paths fall back to `index.html`; CORS limited to the live domain; rate limit on; `/docs` public; no secrets needed.
2. **int8 encoder swap:** done on Day 9 (`text.APP_MODEL`, 8-bit per channel), nothing to do.
3. **Render setup (1 h).** Free web service from the private GHCR image (Dimitris creates the Render, GitHub token and Neon accounts; Claude can't); Frankfurt; `PORT` 8000; `make deploy` pushes and triggers the deploy hook; rollback from the dashboard or by an earlier tag.
4. **Live verification (1 h).** `scripts/smoke.py` against the public URL; full manual run-through on desktop and phone in both themes; attribution check; record wake-up time and live prediction speed.
5. **Monitoring (1 h).** The daily smoke Action (scheduled workflows stop after 60 days without repo activity); Sentry on FastAPI and React with one test error.
6. **Safety net (1 h).** Warm-up routine; local `docker compose up` from a clean clone; 2–3 minute demo video plus a README GIF.
7. **Accounts on Render (from Day 14).** Set `USER_DATABASE_URL` and `DEMO_PASSWORD` on Render; run the migrations and the seed; add demo login and a list toggle to `scripts/smoke.py`; run the Playwright flow against the live URL; check the real client IP reaches the rate limiter; repeat the memory check with the Postgres driver loaded.
8. **Wrap-up (30 min).** README: live link, honest live-speed numbers, deployment section; `PROGRESS.md`; tag `v1.0`.

**Future upgrade (README next step):** a fully static version, with models in ONNX running in the browser and browse data as files, would host free anywhere with no sleeping.

**Done when** the live link passes the smoke test and the manual run-through, monitoring and Sentry are active, and both backups are ready.

## Day 16: Documentation and demo prep

Day 16 ends with a repo that explains itself in 30 seconds or in depth, a rehearsed 5-minute demo, and everything needed for the interview conversation.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| README | Focused README + `docs/` folder | Skimmers get the essentials; engineers can go deep |
| Diagrams | Mermaid, rendered on GitHub | Versioned with the code, no redrawing |
| Decision log | `docs/decisions.md`, including "two databases" and "why Neon" (Day 14) | Answers "why did you choose X?" in writing |
| Model card | `MODEL_CARD.md`, Hugging Face style | Shows ML maturity; matches `/model-card` |
| Demo | The 5-minute storyline below, with a failure card | Smooth and rehearsed |
| Summary | One-page PDF | Easy to send before the interview |
| Q&A prep | Private document, not in the repo | Highest value for the conversation itself |

### Demo storyline

| Time | Part | What you show |
| --- | --- | --- |
| 0:00–0:30 | The problem | Creators can't quickly sanity-check a pitch |
| 0:30–2:00 | Creator flow | Superhero sequel example → ranges, break-even band, drivers, comparables |
| 2:00–3:00 | Honesty | Accuracy panel, rough-estimate badge, unknown-cast example |
| 3:00–4:00 | What if | Compare presets, month sweep, "within the uncertainty" label |
| 4:00–4:30 | Public side | Browse → detail → "Predict a film like this"; the demo button, a rating and a note; a 15-second "Surprise me" spin |
| 4:30–5:00 | Under the hood | Time-split evaluation, time-travel test, architecture in one line |

### Tasks

1. **README and docs (2 h).** README: pitch, live link, GIF, key test results, quick start, architecture, limitations, next steps, attribution. `docs/`: `data.md`, `modeling.md`, `evaluation.md`, `api.md`.
2. **Mermaid diagrams (45 min).** System (browser → FastAPI → SQLite + models and Neon Postgres for user data, plus the offline pipeline) and prediction flow (form → features → budget → revenue → score → drivers → comparables).
3. **Decision log (1 h).** One entry per key decision: choice, alternatives, why. Drawn from these plan documents.
4. **Model card (45 min).** Intended use, data and biases, test metrics and coverage, known failure cases, limitations.
5. **Demo script and rehearsal (1 h).** The storyline above, an "if something fails" card, two timed rehearsals.
6. **One-page summary (45 min).** Problem, approach, results, stack, links; exported to PDF.
7. **Interview Q&A (1 h).** 15–20 likely questions with short answers, plus a 1-minute "walk me through the project".
8. **Final cleanup (1 h).** Dead code removed; notebooks numbered with outputs; MIT LICENSE; fresh-clone test using only the README; GitHub description, topics, preview image, pinned; final `PROGRESS.md` retrospective; tag `v1.0`.

**Done when** a stranger can understand, run and evaluate the project from the repo alone, the demo is rehearsed twice within 5 minutes, and the PDF and Q&A notes are ready.

## Changes to earlier days

These came out of week-three planning and are already reflected in the Days 1–5 and Days 6–10 documents.

| Day | Change | Reason |
| --- | --- | --- |
| 3 | MiniLM quantized to int8 before training; if already built, swapped at inference on deployment day (Day 15) after a consistency check | Fits Render Free's 512 MB and 0.1 CPU without retraining after the test run |
| 9 | Memory measurement becomes a gate: under about 450 MB after 100 predictions | Render Free has 512 MB RAM |
| 8 | New endpoints: `GET /model-card` (Day 11) and `POST /predict/sweep` (Day 13) | Accuracy panel and month sweep |
| 8 | `GET /movies` gains a score filter, loses the money-data filter (Day 12) | Visitor preference |

## Sources

- [Render: Deploy for Free](https://render.com/docs/free): ephemeral filesystem, 15-minute spin-down, free Postgres expires after 30 days with a 14-day grace period
- [Neon: free managed Postgres FAQ](https://neon.com/faqs/managed-postgres-databases-free-tier): permanent free plan, 0.5 GB and 100 compute-hours per project, no card
- [Neon: scale to zero FAQ](https://neon.com/faqs/postgres-databases-vector-embeddings-scale-to-zero): Free compute suspends after 5 minutes, can't be disabled
- [Neon changelog, 5 June 2026](https://neon.com/docs/changelog/2026-06-05): Postgres 18 is the default for new projects
- [Prisma: Neon guide](https://www.prisma.io/docs/v6/orm/overview/databases/neon): cold start from 500 ms to a few seconds, `connect_timeout`
- [Supabase pricing guide (nocode.mba)](https://www.nocode.mba/articles/supabase-pricing): free projects pause after 7 days of inactivity
- [Render: platforms with a real free tier in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026.md): no-card free web services, 15-minute sleep, Fly.io free tier status
- [Render free tier details (agentdeals.dev)](https://agentdeals.dev/vendor/render): 512 MB RAM, 0.1 CPU
- [Render.com in mid-2026 (jwatte.com)](https://jwatte.com/blog/render-com-platform-review.md): bandwidth cut, about 1 minute to wake
- [Hugging Face Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview): Docker Spaces need a paid plan
- [Railway vs Render vs Fly.io, October 2026 (apicostcalc.com)](https://apicostcalc.com/blog/railway-render-flyio-three-real-hosting-bills-2026.html): Railway trial credit, Render free hours
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing?hl=nl): free tier figures
