# Data and features

Where the films come from, how they are cleaned, and every model input. Back to the [README](../README.md).

## Data

- **Source:** our own TMDB API pull. The 1,200 most-voted films per year, 1960–2025, in all languages (79,199 films). The first 700 per year carry almost all the money data; the extra 500 mostly add score data.
- **Per film:** basic info, genres, overview, runtime, budget, revenue, collection, US certification, keywords, production companies and countries, the top 15 cast, and key crew (director, writers, producers, composer, cinematographer, editor).
- **Raw output:** `data/raw/tmdb_movies.jsonl`, and the person pull `data/raw/tmdb_people.jsonl` ([Person pages](app.md#person-pages-days-146147)). Neither is committed to git.
- **Database:** `data/movies.db` (SQLite), built from the raw pull by `make db`, plus the `features` table from `make features`. Neither it nor the overview embedding cache (`data/overview_embeddings.npz`) is committed to git. It holds the cleaned films, people, genres, companies, keywords and collections, full-text search on titles and overviews, and these views:
  - `v_train_revenue`, `v_train_budget` and `v_train_score` for training
  - `v_directors` and `v_actors` for autocomplete
- **Inflation:** `data/cpi_us_annual.csv` holds US CPI-U annual averages for 1960–2025 (FRED `CPIAUCNS`) and is committed. October 2025 was never published because of the government shutdown, so it is filled with the midpoint of September and November. **Add a row for each new year before pulling it**; without one, that year's 2025-dollar values stay empty.


## Cleaning rules

All rules live in `ml/data/clean.py` and are tested in `tests/test_clean.py`. **Every released film is kept** for browsing; bad values become NULL, and suspect money is flagged rather than deleted. Each model trains on its own view. The counts are from the 2026-10-21 pull (79,199 films), and every build stores them in the database's `meta` table.

| Rule | What happens | Films affected |
| --- | --- | --- |
| Status | Only films with status "Released" are kept | 0 dropped |
| Duplicate ids | The latest pull (`pulled_at`) is kept | 0 dropped |
| Text | Whitespace trimmed and empty text becomes NULL; a missing title falls back to `original_title` | 0 titles |
| Release date | Parsed into `release_date`, `year` and `month`; `split` is set from the year | 0 unparseable |
| Runtime | 0 or over 600 minutes → NULL | 1,238 |
| Placeholder money | Budget or revenue below $1,000 → NULL (TMDB shorthand such as `7` meaning $7M) | 167 budgets, 151 revenues |
| Inflation | `budget_2025` / `revenue_2025` = nominal × CPI(2025) / CPI(release year) | All films with money |
| Low ratio | Revenue below 0.0001 × budget → `money_suspect` (token box office, e.g. streaming releases) | 3 |
| Currency | A non-English budget above 3× the 99th percentile of its language's *other* budgets (in 2025 dollars) → `money_suspect`. Languages with fewer than 30 budgets are compared with all other non-English budgets | 3 |
| Still earning | Released less than 182 days before the pull → `revenue_incomplete` | 0 |
| COVID | Released 2020–2021 → `covid_period` | 2,400 |
| Score | 0 votes → score NULL; `score_ok` needs at least 50 votes; `score_weight` = log(1 + votes) | 33,077 `score_ok` |

There is no rule for very *high* revenue-to-budget ratios. The only films above 1,000× were real micro-budget hits (*The Blair Witch Project*, *Paranormal Activity*).

| Training view | Films included | Train / validation / test |
| --- | --- | --- |
| `v_train_revenue` | Budget and revenue known, not `money_suspect`, not `revenue_incomplete` | 8,050 / 886 / 1,485 |
| `v_train_budget` | Budget known, not `money_suspect` | 11,334 / 1,162 / 1,964 |
| `v_train_score` | `score_ok` | 22,016 / 3,600 / 7,461 |

`notebooks/02_clean_check.ipynb` re-checks every rule and the view sizes after each build.

## Features

One function, `build_features(form, as_of, ctx)` in `ml/features/build.py`, turns a creator's form into model inputs. The training table uses the same function: each film is written as a form and judged at its release date. A creator's film is judged at the 1st of its release month. The form itself is defined in `ml/features/contract.py`.

| Creator form | Inputs |
| --- | --- |
| Required | genres (1–5), release year and month, runtime, language, US certification, director, 5–10 actors in billing order, 1–5 themes |
| Optional | production companies, countries, franchise, synopsis, budget (2025 dollars) |

People, companies and the franchise can be picked from autocomplete or typed. A name that isn't in the database counts as a new person, a new company or an original film.

The `features` table in `data/movies.db` has 175 features for every film. `ml/features/feature_list.json` lists each feature's source and which models may use it.

| Group | Features | Notes |
| --- | --- | --- |
| Track record | 24 | Director, and the first 5 billed actors as max, mean and min: earlier films, years active, median earlier log revenue and score shrunk towards the typical film as if they had 4 more average films, earlier franchise films, `is_new` |
| Budget track record | 6 | Median earlier log budget (2025 dollars) of the director, the actors (max, mean, min) and the biggest-spending company, shrunk the same way; the franchise's earlier entries (unshrunk). An earlier film's budget counts from its release |
| Companies | 33 | Top 30 in train, `company_other`, `company_unknown`, `major_studio` (9 classic Hollywood majors) |
| Themes | 27 | Story themes grouped from the 300 most common TMDB keywords (`ml/features/themes.json`) |
| Genres | 19 | One per TMDB genre |
| Countries, language | 17, 16 | Top 15 in train, plus "other" (and "unknown" for countries) |
| Synopsis | 17 | MiniLM (`all-MiniLM-L6-v2`, ONNX) reduced to 16 numbers with PCA, plus `has_synopsis` |
| Certification | 6 | G, PG, PG-13, R, NC-17, unrated/unknown (NR and missing) |
| Release date | 5 | Year, month, summer (May–Aug), holiday (Nov–Dec), `covid_period` |
| Franchise | 3 | `is_franchise` (sequels only), earlier films in the collection, their median log revenue |
| Runtime, budget | 1, 1 | `log_budget` in 2025 dollars; not allowed in the budget model |

**Leak safety.** These rules are tested in `tests/test_features.py`:
- Only films released strictly before the film's date count, so a film never counts towards itself.
- An earlier film's revenue and score count only once it is 182 days old. Its budget counts from its release, since a budget is known before release.
- The typical film used for shrinkage is built from earlier films only.
- The top-N lists, theme keywords and PCA are fitted on train films (≤2015) only.
- A film counts as a franchise film only if its collection already had an earlier film. A first entry joins a collection only once sequels exist, which would leak its later success.

`notebooks/03_features.ipynb` shows missing values, the strongest single signals and a look at the themes and synopsis numbers.
