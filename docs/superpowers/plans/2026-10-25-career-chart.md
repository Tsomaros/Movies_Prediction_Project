# Career Chart and Forecast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every person page gets a Career section after the stats strip. It shows a chart of their film scores over the years, a backtest-calibrated track-record forecast for their next film with a plain explanation, and score-model forecasts for "Their usual film" and "Something new" (with genre chips and "Edit in predictor").

**Architecture:**
- **Shared maths:** a pure-Python module `ml/career/forecast.py` holds the forecast maths. It is used both by a build-time backtest (`ml/career/backtest.py`, which writes `ml/artifacts/career_forecast.json`) and by the API.
- **API:** reads career films with plain `sqlite3` queries in `repo/career.py`. It builds model recipes in `services/career_model.py`, scores them through the existing `predict()` path, and serves two new endpoints under `/api/v1/people/{id}/career`.
- **Frontend:** the React person page adds a lazy `CareerSection` (Recharts chart, track-record card, model card).

**Tech Stack:** Python 3.11, SQLite, NumPy, FastAPI + Pydantic, plain `sqlite3`; React + TypeScript, TanStack Query, Tailwind + shadcn/ui, Recharts, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-25-career-chart-design.md` (read it alongside this plan). It builds on the Day 14.6 actor pages (`docs/superpowers/specs/2026-10-25-actor-pages-design.md`), which must be finished first.

**Schedule:** Day 14.7 (after Day 14.6, before deployment).

**Execution method:** Subagent-driven (chosen by Dimitris on Oct 25, 2026). Use superpowers:subagent-driven-development.

## Global Constraints

- **"Rated" film:** a film with a release year and `vote_count >=` the **Day 2 score vote threshold constant** (the one behind `v_train_score`; the spec writes it as 30). Always import the constant, never a literal.
- **Minimum films:**
  - The forecast needs 5 or more rated films in the role (`MIN_RATED = 5`). The chart needs 2 or more dated films.
  - The role switch lists roles with 5+ rated films (plus the current one).
- **Roles:**
  - `acting` = `movie_cast`.
  - `directing` = `movie_crew.job = 'Director'`.
  - `writing` = `movie_crew.job IN ('Screenplay', 'Writer')`.
  - Lead role = `cast_order <= 2`.
  - Duplicate credits for one film in one role count once.
- **Forecast settings:**
  - Grid *h* ∈ {3, 5, 8, 12, ∞}, *k* ∈ {1, 2, 3, 5, 8, 13}; *q* in steps of 0.05, as the smallest value giving ≥ 80% weighted coverage.
  - Tuning uses next films released before 2019; the report uses 2019 onward.
  - A role with fewer than 300 people with test points uses the acting settings (`fallback: true`).
- **Population stats μ and σ_pop:**
  - API: rated films of that role from the 10 latest release years in the database.
  - Backtest: the 10 years before each test point's year (leak-safe).
- **Range:** clipped to [1, 10]. The career line is a centred rolling mean over 5 rated films.
- **Recipes:**
  - Built from the last 10 rated films in the role.
  - Collaborators need 2+ shared films over the whole career.
  - Release year = current year + 1. No franchise.
  - Budget is never passed to the score model, only to the predictor pre-fill.
  - "Recent" = the 5 latest release years in the database.
  - Up to 4 chips.
- **Model output:** the Day 5 calibrated score 10th–90th percentile range and median.
- **Cache:** LRU of 2,000 results keyed by `(person_id, role, genre_id or "default", model_version)`.
- **API rules:**
  - Both endpoints follow the existing rate limit (30/min/IP) and use the `GET /movies/{id}` cache headers.
  - Writing has no model block: `/career/model?role=writing` returns 404.
- **Layout:** new code follows the Day 8 layout (router per resource, schemas in `schemas/`, queries in `repo/`). Feature code for the score model must not import `ml/career`.
- **Startup memory:** the only new thing loaded at startup is `career_forecast.json` (a few KB). Day 9 memory gate < ~450 MB.
- **Copy:** user-facing copy exactly as in the spec (explanation paragraph, the "most-voted films" note, the honesty line, empty and error states).
- **Commit messages** end with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Several films in one year** (common for busy actors). Dots, the rolling line and the "next film" history must be ordered deterministically by `release_date`, then `movie_id`. Same-date films never count as history for each other → tests in Task 1 and Task 3.
2. **A person whose rated scores are all identical** (e.g. every film 7.0). The range must still have `low < high`, because σ is blended with σ_pop, and must never be NaN → test in Task 2.
3. **Very long careers with h = ∞ or tiny weights** (a 60-year gap). No NaN or division by zero, and `n_eff` stays between 1 and n → test in Task 2.
4. **Recipe inputs with gaps** (films without keywords, certification, country or runtime). The recipe uses `None` for that field and the predictor still answers → test in Task 4.
5. **Fast chip clicks.** A slow response for an earlier chip must not overwrite the card after a newer chip was chosen → test in Task 8.

---

## File Structure

| File | Responsibility |
|---|---|
| `ml/career/__init__.py` (create) | Package marker |
| `ml/career/forecast.py` (create) | Settings type, weights, track-record forecast, rolling line (pure, no I/O) |
| `ml/career/backtest.py` (create) | Next-film points, tuning, evaluation, artifact writer, CLI |
| `backend/app/repo/career.py` (create) | Career films, roles available, year averages, population stats, recipe source queries |
| `backend/app/services/career_model.py` (create) | Usual and new recipes, chips, prediction call, LRU cache |
| `backend/app/services/career_forecast.py` (create) | Loads `career_forecast.json` at startup; builds the `/career` response |
| `backend/app/schemas/career.py` (create) | Pydantic response models |
| `backend/app/routers/career.py` (create) | `GET /people/{id}/career`, `GET /people/{id}/career/model` |
| `Makefile` (modify) | `career` target after `data`; included in `docker-build` |
| `frontend/src/components/person/career/*` (create) | `CareerSection`, `CareerChart`, `CareerTable`, `TrackRecordCard`, `ModelCard` |
| `frontend/src/lib/careerExplain.ts` (create) | Explanation paragraph builder |
| `frontend/src/lib/prefill.ts` (modify) | `recipeToForm` |
| `scripts/smoke.py` (modify) | Career checks |
| `tests/test_career_forecast.py`, `tests/test_career_backtest.py`, `tests/test_career_repo.py`, `tests/test_career_model.py`, `tests/test_career_api.py` (create) | Python tests |

If an existing file lives at a slightly different path (predict service, theme mapping, prefill module), use the existing one and keep the responsibility split above.

---

### Task 1: Career queries

**Files:**
- Create: `backend/app/repo/career.py`
- Test: `tests/test_career_repo.py`

**Interfaces:**
- Consumes: tables `movies`, `movie_cast`, `movie_crew`, `movie_genres`; the Day 2 vote threshold constant `MIN_VOTES`.
- Produces:
  - `Role = Literal["acting", "directing", "writing"]`
  - `CareerFilm` (TypedDict): `movie_id: int`, `title: str`, `year: int`, `release_date: str | None`, `score: float | None`, `vote_count: int`, `rated: bool`, `lead: bool | None` (None for crew roles), `character: str | None`, `poster_path: str | None`.
  - `career_films(con, person_id: int, role: Role, min_votes: int) -> list[CareerFilm]`: dated films only, one per movie, ordered by `release_date` (NULL dates → 1 July of `year`), then `movie_id`.
  - `roles_available(con, person_id: int, min_votes: int) -> list[dict]`: `[{role, film_count, rated_count}]` for roles with any credit.
  - `year_averages(con, min_votes: int) -> dict[int, float]`: mean score of rated films per release year.
  - `population_stats(con, role: Role, min_votes: int, end_year: int) -> tuple[float, float]`: mean and standard deviation of rated films in that role with release year in `[end_year − 9, end_year]`, counting each film once.
  - `latest_year(con) -> int`: the maximum `release_year`.

- [ ] **Step 1: Write the failing tests** (small fixture database: one actor-director with 8 films, two films sharing a release date, one low-vote film, one undated film, a duplicate cast credit)

```python
def test_films_dated_only_deduped_and_ordered(con):
    films = career_films(con, ACTOR, "acting", MIN_VOTES)
    assert [f["movie_id"] for f in films] == EXPECTED_ORDER        # same-date pair ordered by movie_id
    assert len({f["movie_id"] for f in films}) == len(films)        # duplicate credit counted once
    assert UNDATED_ID not in {f["movie_id"] for f in films}

def test_rated_and_lead_flags(con):
    f = {x["movie_id"]: x for x in career_films(con, ACTOR, "acting", MIN_VOTES)}
    assert f[LOW_VOTE_ID]["rated"] is False and f[LEAD_ID]["lead"] is True and f[CAMEO_ID]["lead"] is False

def test_crew_role_has_no_lead_flag(con):
    assert all(f["lead"] is None for f in career_films(con, ACTOR, "directing", MIN_VOTES))

def test_roles_available_counts(con):
    assert {r["role"]: r["rated_count"] for r in roles_available(con, ACTOR, MIN_VOTES)} == {"acting": 7, "directing": 2}

def test_year_averages_and_population_stats(con):
    assert year_averages(con, MIN_VOTES)[2010] == pytest.approx(7.0)
    mu, sd = population_stats(con, "acting", MIN_VOTES, end_year=2015)
    assert mu == pytest.approx(EXPECTED_MU) and sd > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_career_repo.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `backend/app/repo/career.py`**

Parameterised queries only. Writing uses `job IN ('Screenplay', 'Writer')`, and a person credited as both on one film counts once.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_career_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repo/career.py tests/test_career_repo.py
git commit -m "feat(api): career film, role and population queries"
```

---

### Task 2: Forecast maths

**Files:**
- Create: `ml/career/__init__.py`, `ml/career/forecast.py`
- Test: `tests/test_career_forecast.py`

**Interfaces:**
- Produces:
  - `MIN_RATED = 5`
  - `@dataclass(frozen=True) RoleSettings(h: float, k: float, q: float)`; `h` may be `math.inf`.
  - `@dataclass(frozen=True) Forecast(low: float, mid: float, high: float, n_rated: int, own_avg: float, own_share: float, db_avg: float)`
  - `track_record(history: list[tuple[int, float]], s: RoleSettings, mu: float, sigma_pop: float) -> Forecast | None`: `history` holds (year, score) pairs of rated films. Returns `None` when `len(history) < MIN_RATED`. Uses the spec's formulas. *L* = the max year in `history`; *h* = ∞ means all weights are 1.
  - `rolling_line(points: list[tuple[int, float]], window: int = 5) -> list[tuple[int, float]]`: centred mean over the ordered rated points, returning (year, value) per point.

- [ ] **Step 1: Write the failing tests**

```python
S = RoleSettings(h=8, k=3, q=1.3)

def test_needs_five_rated_films():
    assert track_record([(2000, 7.0)] * 4, S, mu=6.3, sigma_pop=0.9) is None

def test_weights_halve_every_h_years():
    f = track_record([(2000, 5.0)] + [(2016, 8.0)] * 4, RoleSettings(8, 0.0001, 1.0), 6.3, 0.9)
    assert f.own_avg == pytest.approx((0.25 * 5 + 4 * 8) / 4.25)       # film 16 years older counts 1/4

def test_short_career_leans_to_average_long_career_to_own():
    short = track_record([(2010 + i, 8.0) for i in range(5)], S, 6.0, 0.9)
    long_ = track_record([(1980 + i, 8.0) for i in range(40)], S, 6.0, 0.9)
    assert 6.0 < short.mid < long_.mid < 8.0 and long_.own_share > short.own_share

def test_identical_scores_still_give_a_range():
    f = track_record([(2000 + i, 7.0) for i in range(10)], S, 6.3, 0.9)
    assert f.low < f.mid < f.high and not math.isnan(f.low)

def test_infinite_h_and_huge_gap_are_stable():
    for s in (RoleSettings(math.inf, 3, 1.3), RoleSettings(3, 3, 1.3)):
        f = track_record([(1950, 6.0)] + [(2020, 7.0)] * 5, s, 6.3, 0.9)
        assert all(map(math.isfinite, (f.low, f.mid, f.high)))

def test_range_clipped_to_scale():
    f = track_record([(2000 + i, 9.9) for i in range(30)], RoleSettings(8, 1, 5.0), 6.3, 2.0)
    assert 1.0 <= f.low and f.high <= 10.0

def test_rolling_line_centred_window():
    pts = [(2000 + i, float(i)) for i in range(7)]
    assert rolling_line(pts) == [(2000, 1.0), (2001, 1.5), (2002, 2.0), (2003, 3.0), (2004, 4.0), (2005, 4.5), (2006, 5.0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_career_forecast.py -v`
Expected: FAIL with `ModuleNotFoundError: ml.career`

- [ ] **Step 3: Implement `ml/career/forecast.py`**

Use NumPy arrays. With `h = inf`, use `w = ones`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_career_forecast.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add ml/career tests/test_career_forecast.py
git commit -m "feat(ml): track-record career forecast maths"
```

---

### Task 3: Backtest and artifact

**Files:**
- Create: `ml/career/backtest.py`
- Modify: `Makefile` (target `career`: `python -m ml.career.backtest`; make `docker-build` depend on it)
- Test: `tests/test_career_backtest.py`

**Interfaces:**
- Consumes: `track_record`, `RoleSettings`, `MIN_RATED` (Task 2); `career_films`, `year_averages`, `population_stats`, `latest_year` (Task 1).
- Produces:
  - `Point` (dataclass): `person_id: int`, `history: list[tuple[int, float]]`, `year: int`, `score: float`, `weight: float`
  - `next_film_points(con, role: Role, min_votes: int) -> list[Point]`:
    - every rated film after a person's 5th rated film;
    - history = rated films with a strictly earlier `release_date` (same-date films excluded);
    - `weight = 1 / points_for_that_person`.
  - `evaluate(points, s: RoleSettings, pop: Callable[[int], tuple[float, float]]) -> dict` with keys `coverage`, `mae`, `width`, `baseline_mae`, `n_people`, `n_points` (weighted). `pop(year)` returns `population_stats(..., end_year=year - 1)`.
  - `tune(points, pop) -> RoleSettings`: (h, k) by lowest weighted MAE of `mid`, then the smallest q on a 0.05 grid with coverage ≥ 0.80.
  - `build_artifact(con, min_votes: int, built_at: str) -> dict`: the spec's JSON shape, where `roles.<role>` has `h, k, q, mu, sigma_pop, fallback, test`. `mu`/`sigma_pop` use `end_year = latest_year(con)`, and `h = inf` is written as `null`.
  - CLI: `python -m ml.career.backtest [--db data/movies.db] [--out ml/artifacts/career_forecast.json] [--max-points 50000]`. It prints a per-role table (h, k, q, test coverage, MAE vs baseline). It samples at most `--max-points` training points per role with seed 0 if needed to stay under ~5 minutes.

- [ ] **Step 1: Write the failing tests** (fixture database with ~20 synthetic actors, careers spanning 2005–2023, and one same-date pair)

```python
def test_points_use_only_strictly_earlier_films(con):
    for p in next_film_points(con, "acting", MIN_VOTES):
        assert len(p.history) >= MIN_RATED
        assert all(y <= p.year for y, _ in p.history)
    sd = [p for p in next_film_points(con, "acting", MIN_VOTES) if p.person_id == SAME_DATE_ACTOR]
    assert not any(SAME_DATE_SCORE in [s for _, s in p.history] and p.score == SAME_DATE_SCORE_2 for p in sd)

def test_time_travel_changing_future_scores_changes_nothing(con):
    before = {(p.person_id, p.year): p.history for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019}
    con.execute("UPDATE movies SET vote_average = 1.0 WHERE release_year >= 2019")
    after = {(p.person_id, p.year): p.history for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019}
    assert before == after

def test_each_person_weighs_the_same(con):
    pts = next_film_points(con, "acting", MIN_VOTES)
    totals = Counter()
    for p in pts: totals[p.person_id] += p.weight
    assert all(t == pytest.approx(1.0) for t in totals.values())

def test_tune_hits_80_percent_on_training_points(con):
    pts = [p for p in next_film_points(con, "acting", MIN_VOTES) if p.year < 2019]
    pop = lambda y: population_stats(con, "acting", MIN_VOTES, y - 1)
    s = tune(pts, pop)
    assert s.h in (3, 5, 8, 12, math.inf) and s.k in (1, 2, 3, 5, 8, 13)
    assert evaluate(pts, s, pop)["coverage"] >= 0.80

def test_artifact_shape_and_fallback(con):
    art = build_artifact(con, MIN_VOTES, "2026-11-01T00:00:00+00:00")
    assert set(art) >= {"version", "built_at", "year_averages", "roles"}
    assert art["roles"]["writing"]["fallback"] is True            # fixture has < 300 writers
    assert set(art["roles"]["acting"]["test"]) == {"coverage", "mae", "width", "baseline_mae", "n_people", "n_points"}
```

(The fallback threshold is a module constant `MIN_PEOPLE = 300`. The fixture test patches it to 5 for acting so tuning runs on the small data.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_career_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `ml/career/backtest.py` and the Makefile target**

Pre-compute per-person sorted NumPy arrays once and cache `pop(year)` per year, so the 30-combination grid stays fast.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_career_backtest.py -v`
Expected: PASS

- [ ] **Step 5: Run on the real database**

Run: `make career`
Expected:
- `ml/artifacts/career_forecast.json` written; runtime under ~5 minutes.
- Acting test coverage between 0.75 and 0.85, and acting MAE below the baseline MAE.
- If coverage is outside that band, report it to Dimitris before continuing. Don't adjust anything on 2019+ data (the Day 6 no-changes-after-test rule).

- [ ] **Step 6: Commit**

```bash
git add ml/career/backtest.py tests/test_career_backtest.py Makefile ml/artifacts/career_forecast.json
git commit -m "feat(ml): career forecast backtest and calibrated settings"
```

---

### Task 4: Model recipes

**Files:**
- Modify: `backend/app/repo/career.py` (recipe source queries)
- Create: `backend/app/services/career_model.py` (recipes only in this task)
- Test: `tests/test_career_model.py`

**Interfaces:**
- Consumes: `career_films` (Task 1); the Day 3 keyword-to-theme mapping; `movies` money fields (`budget_2025`, `money_suspect`); `movie_genres`, `genres`; certification and production-country tables from Day 1/2.
- Produces:
  - `PersonSlot = dict | Literal["new"]`, where the dict is `{"id": int, "name": str}`.
  - `Recipe` (TypedDict):
    - `genres: list[int]`, `themes: list[str]`, `language`, `runtime`, `release_month`, `certification`, `country` (each value or `None`)
    - `release_year: int`, `director: PersonSlot`, `actors: list[PersonSlot]` (length 3), `budget_2025: int | None`
    - `labels: {"genres": list[str], "themes": list[str], "collaborators": list[str]}`
  - `repeat_collaborators(con, person_id: int, role: Role, kind: Literal["actor", "director"], limit: int) -> list[PersonSlot]`: 2+ shared films over the whole career; most shared, then most recent shared film, then name.
  - `usual_recipe(con, person_id: int, role: Literal["acting", "directing"], min_votes: int, next_year: int) -> Recipe`: the spec's table. Ties in "most common" go to the more recent film.
  - `never_done_genres(con, person_id: int, role) -> set[int]`: low-vote films included.
  - `recent_genre_counts(con, min_votes: int) -> tuple[Counter[frozenset[int]], Counter[int]]`: pair and single counts over rated films in the 5 latest release years. Cached per process.
  - `new_recipe(con, person_id, role, usual: Recipe, min_votes, genre_id: int | None = None) -> tuple[Recipe, str | None]`: default rule pair → single → usual genres with the note `"They've already worked in every genre."`. For a chip genre X: X plus its most common never-done partner, else X alone. Themes are the top 3 for that genre set in recent films. All people slots except the person's own are `"new"`.
  - `chips(con, person_id, role, default_genre: int | None, min_votes) -> list[dict]`: `[{genre_id, name, default}]`, at most 4, ranked by recent rated-film count. The default chip is always included.
  - `class GenreAlreadyDone(ValueError)`, `class UnknownGenre(ValueError)`, both raised by `new_recipe`.

- [ ] **Step 1: Write the failing tests**

```python
def test_usual_recipe_is_deterministic_and_uses_last_ten(con):
    a = usual_recipe(con, ACTOR, "acting", MIN_VOTES, 2027)
    assert a == usual_recipe(con, ACTOR, "acting", MIN_VOTES, 2027)
    assert a["genres"] == [DRAMA, THRILLER] and a["release_year"] == 2027
    assert a["actors"][0] == {"id": ACTOR, "name": "Actor A"}

def test_collaborators_need_two_shared_films(con):
    r = usual_recipe(con, ACTOR, "acting", MIN_VOTES, 2027)
    assert r["director"] == {"id": REPEAT_DIRECTOR, "name": "Repeat Director"}
    assert r["actors"][2] == "new"                       # only one repeat co-star exists

def test_director_page_flips_roles(con):
    r = usual_recipe(con, DIRECTOR, "directing", MIN_VOTES, 2027)
    assert r["director"]["id"] == DIRECTOR and r["actors"][0]["id"] == FAVOURITE_ACTOR

def test_missing_fields_become_none(con):
    r = usual_recipe(con, SPARSE_ACTOR, "acting", MIN_VOTES, 2027)   # films without keywords/cert/country
    assert r["themes"] == [] and r["certification"] is None and r["country"] is None

def test_new_recipe_uses_only_never_done_genres(con):
    usual = usual_recipe(con, ACTOR, "acting", MIN_VOTES, 2027)
    new, note = new_recipe(con, ACTOR, "acting", usual, MIN_VOTES)
    assert set(new["genres"]) <= never_done_genres(con, ACTOR, "acting") and note is None
    assert all(s == "new" for s in [new["director"], *new["actors"][1:]])
    assert new["runtime"] == usual["runtime"] and new["language"] == usual["language"]

def test_new_recipe_fallbacks(con):
    usual = usual_recipe(con, DID_EVERYTHING, "acting", MIN_VOTES, 2027)
    new, note = new_recipe(con, DID_EVERYTHING, "acting", usual, MIN_VOTES)
    assert new["genres"] == usual["genres"] and note == "They've already worked in every genre."
    assert chips(con, DID_EVERYTHING, "acting", None, MIN_VOTES) == []

def test_chip_errors(con):
    usual = usual_recipe(con, ACTOR, "acting", MIN_VOTES, 2027)
    with pytest.raises(GenreAlreadyDone): new_recipe(con, ACTOR, "acting", usual, MIN_VOTES, genre_id=DRAMA)
    with pytest.raises(UnknownGenre): new_recipe(con, ACTOR, "acting", usual, MIN_VOTES, genre_id=999)

def test_chips_max_four_with_default_marked(con):
    c = chips(con, ACTOR, "acting", HORROR, MIN_VOTES)
    assert len(c) <= 4 and [x["genre_id"] for x in c if x["default"]] == [HORROR]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_career_model.py -v`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement the queries and recipe functions**

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_career_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repo/career.py backend/app/services/career_model.py tests/test_career_model.py
git commit -m "feat(api): usual and something-new film recipes"
```

---

### Task 5: Endpoints, schemas, prediction and cache

**Files:**
- Create: `backend/app/services/career_forecast.py`, `backend/app/schemas/career.py`, `backend/app/routers/career.py`
- Modify: `backend/app/services/career_model.py` (prediction + cache), app startup (load the artifact, register the router), README API section
- Test: `tests/test_career_api.py`

**Interfaces:**
- Consumes: Tasks 1–4; the existing `predict()` service and its creator-form input model; the movie-detail cache-header helper; the rate limiter; `poster_urls` and `profile_urls` image helpers.
- Produces:
  - `load_career_artifact(path: Path) -> CareerArtifact`, called once at startup and stored on `app.state`. If the file is missing, startup fails with a clear message.
  - `career_response(con, art, person_id: int, role: Role | None) -> dict`: the spec's `/career` shape. `role=None` picks the role with the most films. `year_avg` is per film; `forecast.status` is `"ok"` or `"not_enough_films"`; `test` comes from `art.roles[role].test`.
  - `recipe_to_form(r: Recipe) -> CreatorForm`: maps a recipe to the predictor input, with `"new"` → new-person slot. Budget is not set for the score call.
  - `career_model_response(con, predictor, person_id, role, genre_id: int | None) -> dict`: `{usual, new, chips}`, or `{new}` when `genre_id` is given. Wrapped in an LRU cache of 2,000 keyed by `(person_id, role, genre_id or "default", model_version)`.
  - Pydantic: `CareerFilmOut`, `LinePoint`, `TrackForecast`, `CareerResponse`, `RecipeOut`, `ScoreRange`, `ModelFilm`, `Chip`, `CareerModelResponse`.
  - `GET /api/v1/people/{person_id:int}/career?role=` → `CareerResponse`
  - `GET /api/v1/people/{person_id:int}/career/model?role=acting|directing&genre=` → `CareerModelResponse`
  - Errors: 404 `{"detail": "Person not found"}`, 404 `{"detail": "No credits in this role"}`, 404 for `role=writing` on `/model`, 422 `{"detail": "Genre already done"}` and `{"detail": "Unknown genre"}`.

- [ ] **Step 1: Write the failing tests** (TestClient on the fixture database, a small artifact JSON, and a fake predictor that records its inputs)

```python
def test_career_full_response(client):
    r = client.get(f"/api/v1/people/{ACTOR}/career")
    b = r.json()
    assert r.status_code == 200 and b["role"] == "acting" and b["forecast"]["status"] == "ok"
    assert b["forecast"]["low"] < b["forecast"]["mid"] < b["forecast"]["high"]
    assert b["best_film"]["movie_id"] == BEST_ID and b["model_available"] is True
    assert "Cache-Control" in r.headers

def test_not_enough_films(client):
    assert client.get(f"/api/v1/people/{FEW_FILMS}/career").json()["forecast"]["status"] == "not_enough_films"

def test_writing_has_no_model(client):
    assert client.get(f"/api/v1/people/{WRITER}/career?role=writing").json()["model_available"] is False
    assert client.get(f"/api/v1/people/{WRITER}/career/model?role=writing").status_code == 404

@pytest.mark.parametrize("path,status", [
    ("/api/v1/people/424242/career", 404),
    (f"/api/v1/people/{ACTOR}/career?role=writing", 404),
    (f"/api/v1/people/{ACTOR}/career?role=dancing", 422),
    (f"/api/v1/people/{ACTOR}/career/model?role=acting&genre={DRAMA}", 422),
    (f"/api/v1/people/{ACTOR}/career/model?role=acting&genre=999", 422),
])
def test_career_errors(client, path, status):
    assert client.get(path).status_code == status

def test_model_response_and_no_budget_in_score_call(client, fake_predictor):
    b = client.get(f"/api/v1/people/{ACTOR}/career/model?role=acting").json()
    assert set(b) == {"usual", "new", "chips"} and b["usual"]["prediction"]["low"] < b["usual"]["prediction"]["high"]
    assert all(call.budget is None for call in fake_predictor.calls)

def test_chip_returns_only_new_and_is_cached(client, fake_predictor):
    url = f"/api/v1/people/{ACTOR}/career/model?role=acting&genre={HORROR}"
    assert set(client.get(url).json()) == {"new"}
    n = len(fake_predictor.calls)
    client.get(url)
    assert len(fake_predictor.calls) == n
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_career_api.py -v`
Expected: FAIL (404 on the new routes)

- [ ] **Step 3: Implement the services, schemas and router; register them and load the artifact at startup**

- [ ] **Step 4: Run the new tests and the whole Python suite**

Run: `pytest -q`
Expected: PASS (Day 14.6 person tests unchanged)

- [ ] **Step 5: Regenerate frontend types**

Run: `cd frontend && npm run gen:api && npx tsc --noEmit`
Expected: no type errors

- [ ] **Step 6: Commit**

```bash
git add backend tests/test_career_api.py frontend/src/api README.md
git commit -m "feat(api): career and career-model endpoints"
```

---

### Task 6: Frontend hooks, explanation text and predictor mapping

**Files:**
- Modify: the Day 10 API hooks file; `frontend/src/lib/prefill.ts`
- Create: `frontend/src/lib/careerExplain.ts`
- Test: `frontend/src/lib/careerExplain.test.ts`, `frontend/src/lib/prefill.test.ts`

**Interfaces:**
- Consumes: generated types `CareerResponse`, `CareerModelResponse`, `RecipeOut` (Task 5).
- Produces:
  - `useCareer(id: number, role?: Role)`: query key `["career", id, role]`.
  - `useCareerModel(id: number, role: "acting" | "directing", genre: number | null, enabled: boolean)`: key `["careerModel", id, role, genre]`, `placeholderData: keepPreviousData`.
  - `explainText(f: TrackForecast, test: { coverage: number }, halfLife: number | null): string`: the spec's paragraph. `halfLife = null` gives "All films count equally". Coverage is rounded to the nearest 10% as "N out of 10".
  - `recipeToForm(r: RecipeOut): Partial<FormValues>`: maps every recipe field, with `"new"` → the form's new-person value. It includes `budget_2025` as the budget.

- [ ] **Step 1: Write the failing tests**

```ts
test("explanation uses the person's numbers and the backtest hit rate", () => {
  const t = explainText({ n_rated: 23, own_avg: 6.9, own_share: 0.82, db_avg: 6.3, mid: 6.8, low: 6.1, high: 7.4 } as any,
                        { coverage: 0.81 }, 8);
  expect(t).toContain("Based on 23 rated films.");
  expect(t).toContain("a film from 8 years before the latest counts half");
  expect(t).toContain("we trust it 82% and the database average (6.3) 18%, giving 6.8");
  expect(t).toContain("8 out of 10 real next films");
});
test("infinite half-life says all films count equally", () => {
  expect(explainText(F, { coverage: 0.8 }, null)).toContain("All films count equally");
});
test("recipeToForm fills slots and new people", () => {
  const v = recipeToForm(usualRecipe);
  expect(v.actors?.[0]).toEqual({ id: 31, name: "Tom Hanks" });
  expect(v.actors?.[2]).toEqual(NEW_PERSON);
  expect(v.budget).toBe(100_000_000);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib`
Expected: FAIL

- [ ] **Step 3: Implement the hooks and helpers**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(web): career hooks, explanation text and recipe mapping"
```

---

### Task 7: Career chart

**Files:**
- Modify: `frontend/package.json` (`npm i recharts`)
- Create: `frontend/src/components/person/career/CareerChart.tsx`, `CareerTable.tsx`
- Test: `frontend/src/components/person/career/CareerChart.test.tsx`

**Interfaces:**
- Consumes: `CareerResponse` (Task 5); theme colour tokens.
- Produces:
  - `CareerChart({ data, view, onOpenMovie }: { data: CareerResponse; view: "score" | "year"; onOpenMovie: (id: number) => void })`
  - `CareerTable({ films }: { films: CareerFilmOut[] })`
  - Test ids: `dot-lead`, `dot-support`, `dot-crew`, `dot-faint`, `best-marker`, `forecast-band`.

- [ ] **Step 1: Write the failing tests** (mock `ResponsiveContainer` to a fixed size, the usual Recharts testing setup)

```ts
test("dot styles follow lead, supporting, crew and low votes", () => {
  render(<CareerChart data={actorCareer} view="score" onOpenMovie={vi.fn()} />);
  expect(screen.getAllByTestId("dot-lead")).toHaveLength(5);
  expect(screen.getAllByTestId("dot-support")).toHaveLength(2);
  expect(screen.getAllByTestId("dot-faint")).toHaveLength(1);
  expect(screen.getByTestId("best-marker")).toBeInTheDocument();
  expect(screen.getByTestId("forecast-band")).toBeInTheDocument();
});
test("no band when not enough films", () => {
  render(<CareerChart data={{ ...actorCareer, forecast: { status: "not_enough_films" } }} view="score" onOpenMovie={vi.fn()} />);
  expect(screen.queryByTestId("forecast-band")).toBeNull();
});
test("year view plots score minus year average", () => {
  render(<CareerChart data={actorCareer} view="year" onOpenMovie={vi.fn()} />);
  expect(screen.getByText("0")).toBeInTheDocument();             // middle line label
});
test("touch: first tap shows tooltip, second opens movie", async () => {
  const open = vi.fn();
  render(<CareerChart data={actorCareer} view="score" onOpenMovie={open} />);
  const dot = screen.getAllByTestId("dot-lead")[0];
  fireEvent.pointerDown(dot, { pointerType: "touch" }); fireEvent.click(dot);
  expect(open).not.toHaveBeenCalled();
  fireEvent.pointerDown(dot, { pointerType: "touch" }); fireEvent.click(dot);
  expect(open).toHaveBeenCalledWith(actorCareer.films[0].movie_id);
});
test("table lists every dated film", () => {
  render(<CareerTable films={actorCareer.films} />);
  expect(screen.getAllByRole("row")).toHaveLength(actorCareer.films.length + 1);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/person/career`
Expected: FAIL

- [ ] **Step 3: Implement the chart**

- `ComposedChart` with a `Scatter` using a custom `shape` per dot style, a `Line` for `line`, and a `ReferenceArea` "Next film" column at `last_year + 1`.
- The band is a `ReferenceArea` from `low` to `high` with a middle `ReferenceLine` and a dashed segment from the last line point.
- Year view subtracts `year_avg` per film, and `latest_year_avg` for the band.
- Height 260 px (≥ 640 px wide) / 220 px; colours from theme tokens; an `sr-only` summary sentence.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/person/career`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/person/career
git commit -m "feat(web): career chart with forecast band and table view"
```

---

### Task 8: Cards, section and page integration

**Files:**
- Create: `frontend/src/components/person/career/CareerSection.tsx`, `TrackRecordCard.tsx`, `ModelCard.tsx`
- Modify: `frontend/src/pages/PersonPage.tsx` (insert the lazy `CareerSection` between the stats strip and the filmography)
- Test: `frontend/src/components/person/career/CareerSection.test.tsx`

**Interfaces:**
- Consumes: `useCareer`, `useCareerModel`, `explainText`, `recipeToForm` (Task 6); `CareerChart`, `CareerTable` (Task 7); shared skeleton, error-with-retry and segmented-control components.
- Produces:
  - `CareerSection({ personId }: { personId: number })`. URL params `?role=` and `?view=score|year` (default `score`).
  - The role switch shows only when 2+ entries in `roles_available` have `rated_count >= 5`.

- [ ] **Step 1: Write the failing tests** (mocked API)

```ts
test("shows chart, track-record range and explanation", async () => {
  renderPerson(31, { career: actorCareer, model: actorModel });
  expect(await screen.findByText("6.1 – 7.4")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "How is this calculated?" }));
  expect(screen.getByText(/8 out of 10 real next films/)).toBeInTheDocument();
  expect(screen.getByText(/We only see the most-voted films/)).toBeInTheDocument();
});
test("view and role round-trip through the URL", async () => {
  const { router } = renderPerson(31, { career: actorDirectorCareer, model: actorModel });
  await userEvent.click(await screen.findByRole("radio", { name: "Compared with its year" }));
  await userEvent.click(screen.getByRole("radio", { name: "As director" }));
  expect(router.state.location.search).toBe("?view=year&role=directing");
});
test("model card: skeleton, then usual and new films with honesty line", async () => {
  renderPerson(31, { career: actorCareer, model: delayed(actorModel) });
  expect(await screen.findByTestId("model-skeleton")).toBeInTheDocument();
  expect(await screen.findByText("Their usual film")).toBeInTheDocument();
  expect(screen.getByText(/doesn't know how they'd handle a new genre/)).toBeInTheDocument();
});
test("a slow earlier chip never overwrites a newer choice", async () => {
  renderPerson(31, { career: actorCareer, model: actorModel,
                     chip: { [SCIFI]: delayed(scifiNew, 500), [WESTERN]: delayed(westernNew, 10) } });
  await userEvent.click(await screen.findByRole("button", { name: "Sci-Fi" }));
  await userEvent.click(screen.getByRole("button", { name: "Western" }));
  await waitFor(() => expect(screen.getByTestId("new-recipe")).toHaveTextContent("Western"));
  await new Promise((r) => setTimeout(r, 600));
  expect(screen.getByTestId("new-recipe")).toHaveTextContent("Western");
});
test("model error keeps chart and track record", async () => {
  renderPerson(31, { career: actorCareer, model: serverError });
  expect(await screen.findByText("Couldn't load the model forecast.")).toBeInTheDocument();
  expect(screen.getByText("6.1 – 7.4")).toBeInTheDocument();
});
test("writer role shows track record only", async () => {
  renderPerson(9, { career: writerCareer });
  expect(await screen.findByText(/no writer input/)).toBeInTheDocument();
  expect(screen.queryByText("Their usual film")).toBeNull();
});
test("fewer than 2 dated films hides the chart", async () => {
  renderPerson(5, { career: oneFilmCareer });
  expect(await screen.findByText("Not enough dated films to chart a career")).toBeInTheDocument();
});
test("edit in predictor opens the pre-filled form", async () => {
  const { router } = renderPerson(31, { career: actorCareer, model: actorModel });
  await userEvent.click((await screen.findAllByRole("button", { name: "Edit in predictor" }))[0]);
  expect(router.state.location.pathname).toBe("/predict");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/person/career src/pages`
Expected: FAIL

- [ ] **Step 3: Build the cards and the section**

- **Layout:** header (title "Career", role switch, view toggle) → chart (or the empty note) → "View as table" toggle → a two-column grid on ≥ 768 px (stacked below): `TrackRecordCard` and `ModelCard`.
- **Model card:** fetches only when `/career` has loaded and `model_available` is true.
- **Chips:** selection state lives in the section, and the card renders the data whose query key matches the selected chip. Older numbers show faded while `isPlaceholderData`.
- **Copy:** every message and label exactly as in the spec.

- [ ] **Step 4: Run the whole frontend suite**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(web): career section with track-record and model cards"
```

---

### Task 9: Real data, smoke, budgets and wrap-up

**Files:**
- Modify: `scripts/smoke.py`, `README.md`, `PROGRESS.md`, Docker build (copy `ml/artifacts/career_forecast.json`)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Add smoke checks**

`smoke.py` takes the first actor from `GET /api/v1/people?role=actor&q=hanks`, then:
- `GET .../career` → 200 with `forecast.status == "ok"`;
- `GET .../career/model?role=acting` → 200 with `usual` and `new`.

- [ ] **Step 2: Docker build, run and smoke**

Run: `make docker-build && make docker-run && make smoke`
Expected:
- Smoke passes, and startup logs show the career artifact loaded.
- Memory after 100 predictions plus 50 career-model calls stays under ~450 MB.

- [ ] **Step 3: Manual check**

Check phone width and desktop, in light and dark:
- An actor with a long career: toggle, tooltip, tap to open, best marker, band, "How is this calculated?".
- Chips: rapid clicks, then "Edit in predictor" on both rows.
- A director (role switch), a writer, and a person with 3 rated films.

- [ ] **Step 4: Full test run**

Run: `make test && (cd frontend && npx vitest run)`
Expected: all pass

- [ ] **Step 5: Update README (feature line, backtest results table from the artifact) and PROGRESS, commit**

```bash
git add scripts/smoke.py README.md PROGRESS.md Dockerfile Makefile
git commit -m "chore: career section smoke checks, docs and progress (Day 14.7)"
```

**Cut lines (in order, from the spec):**
1. Drop the `CareerTable` and its toggle.
2. Acting only: hide the role switch and call `/career?role=acting`.
3. Drop the chips and keep the fixed-rule "Something new".

The chart, the track-record forecast with its backtest, and both recipes are never cut.

**Done when** the spec's "Done when" holds. The Career section shows after the stats strip with:
- the chart and band;
- an explanation filled from real backtest numbers;
- both model films, with working chips and predictor buttons.

All tests pass on desktop and mobile in both themes, and memory stays under the gate.
