# Career Chart and Forecast: Design Spec

Oct 25, 2026 · @Dimitris · Movie Prediction App · **Day 14.7** (after Day 14.6 actor pages, before deployment)

## Goal

Every person page gets a **Career** section. It shows how their films have scored over the years, plus two honest forecasts for what comes next:

1. **Track record:** the likely score range of their next film, from their past scores only, with the range checked by a backtest.
2. **Film model:** the existing Day 5 score model run on two made-up films, "Their usual film" and "Something new". Each one shows the recipe that was scored.

**Success:** a visitor understands the career at a glance, sees a forecast with a plain explanation backed by real test numbers, and can jump into the predictor from either model film. It works on desktop and mobile, in both themes.

**Constraints carried over:** fast and simple; Day 9 memory gate (< ~450 MB); live speed up to ~3 s on Render; post-release fields (`vote_average`, `vote_count`) are used here only to describe past films and to calibrate the track-record forecast, never as score-model inputs; the Day 14.6 actor pages spec and plan stay unchanged.

## Decisions

| Topic | Decision |
|---|---|
| Forecast meaning | Score range of the person's **next film** (80% range) |
| Chart content | Dot per film, career line, filled = lead / hollow = supporting, faint dots under 30 votes, "Compared with its year" toggle, best-film marker, forecast band, role switch |
| Not included | Dot size by votes; first-lead and box-office markers |
| Forecast 1 | Weighted track record shrunk toward the average, range calibrated by a build-time backtest |
| Forecast 2 | Score model on "Their usual film" and "Something new" recipes, shown side by side with forecast 1 |
| "Something new" | Fixed-rule default plus up to 4 clickable genre chips |
| Placement | Right after the stats strip, before the filmography |
| Chart library | Recharts, lazy-loaded with the person page |
| Schedule | Day 14.7; if it runs late, actor pages ship without the section and deployment is not blocked |

## 1. Data and the track-record forecast

### Which films count

- **Role:** credits in the selected role. `acting` = `movie_cast`; `directing` = `movie_crew.job = 'Director'`; `writing` = `movie_crew.job IN ('Screenplay', 'Writer')`.
- **Rated film:** `vote_count >= 30` (the Day 2 threshold) and a release year. Rated films get a solid dot and feed the line and the forecast.
- **Low-vote film:** has a release year but fewer than 30 votes. It is drawn as a faint dot only and never used in calculations.
- **Undated film:** has no release year and is not drawn.
- **Lead role:** an acting credit with `cast_order <= 2`. Crew credits have no lead/supporting styling.
- A film appearing twice in one role (rare duplicate credits) counts once.

### Career line

A centred rolling average of 5 rated films (each film plus up to 2 neighbours on each side, fewer at the ends), computed on the server.

### "Compared with its year"

- **Year averages:** at build time, store the average score of rated films for each release year (1960–2025).
- **Dots and line:** in this view each score becomes *score − that year's average*.
- **Band:** shifted by the average of the latest complete year.
- The forecast itself is always calculated on real scores.

### Track-record forecast

Needs **5+ rated films** in the role. Otherwise the response says `not_enough_films`.

For rated films *i* with score *sᵢ* and year *yᵢ*, and *L* = year of their latest rated film:

1. **Weights:** wᵢ = 0.5 ^ ((L − yᵢ) / h)
2. **Weighted mean:** m = Σwᵢsᵢ / Σwᵢ. Effective film count: n_eff = (Σwᵢ)² / Σwᵢ²
3. **Middle value:** c = (n_eff · m + k · μ) / (n_eff + k), where μ is the role's database average over rated films from the last 10 years
4. **Spread:** v = Σwᵢ(sᵢ − m)² / Σwᵢ. Blended spread: σ = √((n_eff · v + k · σ²_pop) / (n_eff + k)), where σ_pop is the role's population spread over the same films
5. **Range:** c ± q · σ, clipped to 1–10

The response also returns the numbers for the explanation: film count, half-life *h*, blend share n_eff / (n_eff + k), *m*, *μ*, *c*, and the range.

### Backtest: `ml/career/backtest.py`

- **Test points:** for every person, each rated film after their 5th rated film in a role is a "next film". It is forecast from strictly earlier films only (earlier release date; films with the same release date are excluded).
- **Equal people:** each test point is weighted 1 / (number of test points for that person), so prolific people don't dominate.
- **Tuning on next films released before 2019:**
  - Grid *h* ∈ {3, 5, 8, 12, ∞} × *k* ∈ {1, 2, 3, 5, 8, 13}, picking the pair with the lowest weighted mean absolute error of *c*.
  - Then pick the smallest *q* (step 0.05) that gives ≥ 80% weighted coverage.
- **Report on next films from 2019 onward:** coverage, MAE, average range width, and MAE of the "database average" baseline.
- **Per role:** `acting`, `directing` and `writing` are tuned separately. A role with fewer than 300 people with test points uses the acting settings, and the report says so.
- **Output:** `ml/artifacts/career_forecast.json`
  ```
  { version, built_at,
    year_averages: { "1960": 6.4, ... },
    roles: { acting: { h, k, q, mu, sigma_pop, fallback: false,
                        test: { coverage, mae, width, baseline_mae, n_people, n_points } },
             directing: {...}, writing: {...} } }
  ```
- It runs in the build after `build_db`, is loaded once at API startup (a few KB) and is baked into the Docker image.
- The "8 out of 10" sentence in the panel is built from `test.coverage` (rounded to the nearest 10%), never hard-coded.

## 2. Model forecasts and the API

### `GET /api/v1/people/{id}/career?role=acting|directing|writing`

- **Default role:** `role` defaults to the person's role with the most films.
- **No model call**, so it's fast and fetched together with the page.
- **Response:**
```
{
  person_id, role,
  roles_available: [{ role, film_count }],           // roles with 5+ rated films (+ the current one)
  films: [{ movie_id, title, year, release_date, score, vote_count,
            rated: bool, lead: bool | null, character | null,
            poster_small | null, year_avg }],
  line: [{ year, value }],
  best_film: { movie_id, title, year, score } | null,
  latest_year_avg,
  forecast: { status: "ok" | "not_enough_films",
              low, mid, high,
              explain: { n_rated, half_life, own_share, own_avg, db_avg },
              test: { coverage, n_people } } ,
  model_available: bool                               // false for writing
}
```
- 404 if the person is unknown, or has no credits in the requested role.

### `GET /api/v1/people/{id}/career/model?role=acting|directing[&genre=<genre_id>]`

- **Without `genre`:** returns `usual`, `new` (fixed-rule pick) and `chips`.
- **With `genre`:** returns only `new` for that chip.
```
{
  usual: { recipe, prediction: { low, mid, high } },
  new:   { recipe, prediction: { low, mid, high }, note | null },
  chips: [{ genre_id, name, default: bool }]
}
```
- **`recipe`:** the creator-form input the model was given (genres, themes, language, runtime, release month and year, certification, country, director and cast slots as `{ id, name } | "new"`, `budget_2025` for the predictor pre-fill only), plus display labels for the card.
- **`prediction`:** the Day 5 calibrated 10th–90th percentile score range and median.
- **Errors:**
  - 404: unknown person, no credits in the role, or `role=writing`.
  - 422: `genre` is unknown, or the person has already done it.
- **Cache:** in-memory LRU of 2,000 results keyed by (person, role, genre or "default", model version).
- **Headers and limits:** cache headers as `GET /movies/{id}`; both career endpoints count toward the 30 requests/min limit.

### "Their usual film" recipe

Built from their **last 10 rated films** in the role (fewer if they have fewer):

| Field | Rule |
|---|---|
| Genres | 2 most common (ties → more recent) |
| Themes | 3 most common keyword themes (ties → more recent) |
| Language, release month, US certification, production country | Most common |
| Runtime | Median |
| Budget | Median of known, non-suspect budgets in 2025 $. Not scored (the score model excludes budget); used only for the predictor pre-fill |
| Franchise | None (standalone film) |
| Release year | Current year + 1 |
| **Actor page** | Person = lead actor; actor slots 2–3 = co-stars with 2+ shared films over the whole career (most shared, then most recent); director = director with 2+ shared films; empty slots = "new person" |
| **Director page** | Person = director; actor slots 1–3 = actors from their films with 2+ shared films; empty slots = "new person" |

### "Something new" recipe

- **Never done:** genres with zero credits in the role, low-vote films included.
- **Default pick:**
  - The most common genre pair among rated database films from the last 5 years where both genres are never done.
  - Otherwise the most common single never-done genre.
  - Otherwise their usual genres, with `note: "They've already worked in every genre."`
- **Chip genre X:** X plus its most common partner genre among recent films that is also never done, otherwise X alone.
- **Chips:** up to 4 never-done genres ranked by number of recent rated films; the default pick's first genre is always included and marked `default`.
- **Themes:** the 3 most common themes among recent rated films with that genre combination.
- **People:** the person in their role; all other people slots are "new person".
- **Other fields:** language, runtime, month, certification, country and release year are the same as in the usual recipe.

### Prediction call

- Recipes go through the same `predict()` path as `POST /predict`, score target only.
- The person's leak-safe track-record features are computed from all their films, because we're predicting the future.

## 3. Frontend

### Placement and controls

- **Placement:** the Career section sits on `/people/:id` between the stats strip and the filmography.
- **Header:** the title "Career", a role switch ("As actor / As director / As writer"), and a toggle "Score / Compared with its year".
  - The role switch shows only when the person has 2+ roles with 5+ rated films each.
  - The URL keeps `?role=` and `?view=score|year`.
- **Loading:** `/career` is fetched in parallel with `/people/{id}`. `/career/model` is fetched after `/career` returns and `model_available` is true.

### Chart (Recharts)

- **Size:** about 260 px tall on desktop, 220 px on phones, full width.
- **Axes:** x = year; y = score (auto range rounded to whole points) or difference from year average (0 as middle line).
- **Dots:**
  - Lead roles filled; supporting roles hollow; crew credits filled.
  - Low-vote films faint grey.
  - The best film gets a ring and a "Best: 7.9" label.
- **Career line:** solid line.
- **Forecast:** a shaded "Next film" column after the last year, with the band (low–high), a middle tick, and a dashed line from the end of the career line to the middle.
- **Tooltip:** title, year, score, character, lead/supporting.
  - Desktop: hover shows the tooltip, click opens the movie.
  - Touch: first tap shows the tooltip, second tap opens the movie.
- **Theme:** colours come from theme tokens, so light and dark both work.
- **Accessibility:** a screen-reader summary sentence ("23 rated films from 1999 to 2024; average 6.9; best film X") and a "View as table" link that expands a plain list of films.

### Track-record card

- **Shows:** the range (large), "Most likely around 6.8", and a "How is this calculated?" expander.
- **The expander paragraph** is built from `forecast.explain` and `forecast.test`:
  > Based on 23 rated films. Recent films count more: a film from 8 years before the latest counts half. Their weighted average is 6.9; with this many films we trust it 82% and the database average (6.3) 18%, giving 6.8. The range is wider for people whose scores vary more. In our tests on films from 2019 onward, 8 out of 10 real next films landed inside a range built this way.

  plus the note: *"We only see the most-voted films of each year, so smaller films aren't counted."*
- **Not enough films:** the card shows "Not enough rated films to forecast yet (needs 5)".

### Film model card

- **Two rows:** "Their usual film" and "Something new". Each row shows its range, the recipe in one line (genres · themes · named collaborators or "new collaborators" · year) and an "Edit in predictor" button.
- **Chips:** under "Something new", with the default chip highlighted. Clicking a chip fetches with `genre=`, keeps the old numbers faded until the new ones arrive, then highlights that chip.
- **Honesty line:** *"The model doesn't know how they'd handle a new genre; it shows how films like this usually do with someone of their track record."*
- **"Edit in predictor":** opens `/predict` pre-filled through a new isolated mapping function `recipeToForm()`, beside the Day 12 and Day 14.6 mappings. It includes the median budget.
- **Loading:** skeleton rows while loading.

### States

| Situation | What the user sees |
|---|---|
| Fewer than 2 dated films in the role | No chart; one-line note "Not enough dated films to chart a career" |
| 2–4 rated films | Chart without band; track-record card says not enough films |
| `/career` fails | Section shows "Couldn't load the career chart. Retry"; rest of the page unaffected |
| `/career/model` fails | Model card shows "Couldn't load the model forecast. Retry"; chart and track record stay |
| Writing role | Track record only, plus "The film model has no writer input, so only the track record is shown." |
| Has done every genre | "Something new" uses usual genres with the note; no chips |

## 4. Testing

**Python (pytest)**
- **Forecast maths:**
  - Weights halve every *h* years.
  - A 1-film case sits near μ and a 40-film case near *m*.
  - The range is clipped to 1–10, and fewer than 5 rated films returns `not_enough_films`.
- **Backtest:**
  - Time-travel test: no test point uses its own score, a same-date film or any later film.
  - Equal person weights.
  - Tuning uses pre-2019 points only.
  - The JSON has all fields, and a small role falls back to the acting settings.
- **Recipes:**
  - Same input → identical recipe.
  - Collaborators need 2+ shared films.
  - "Something new" genres are truly never done, with fallbacks pair → single → none.
  - The director page flips roles.
  - Budget is not passed to the score model.
- **Endpoints:**
  - Full responses for both endpoints.
  - 404s (unknown person, no credits in role, writing on `/model`); 422s (unknown genre, genre already done).
  - A repeat request is served from the cache.
  - The rate limit applies, and responses match the schemas.

**Frontend (Vitest + Testing Library)**
- **Chart:** renders the right dot styles, the best marker and the band. The toggle and role switch round-trip through the URL.
- **Model card:** skeleton → data. A chip click keeps the old values until the new ones arrive. The error state shows retry while the chart stays.
- **Mapping:** `recipeToForm()` fills the form correctly for both recipes and for "new person" slots.

**Smoke and manual**
- `scripts/smoke.py` calls `/career` and `/career/model` for one known person.
- Manual: phone size, both themes, memory under the Day 9 gate, `/career/model` within ~3 s on Render.

## Cut lines (in order)

1. "View as table" link → after deployment.
2. Role switch → acting only first; directing and writing after deployment.
3. Genre chips → fixed-rule "something new" only.

Never cut: the chart, the track-record forecast with its backtest, both model recipes.

## Out of scope

Dot size by vote count, first-lead and box-office markers, multi-year career extrapolation, blending the two forecasts into one number, revenue forecasts per person, comparing two people on one chart.

## Done when

A person page shows the Career section after the stats strip, with:
- the chart and forecast band;
- the explanation, filled from real backtest numbers;
- "Their usual film" and "Something new" forecasts, with working chips and "Edit in predictor" buttons.

Every test above passes, on desktop and mobile, in both themes, within the memory gate.
