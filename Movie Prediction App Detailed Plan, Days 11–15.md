# Movie Prediction App: Detailed Plan, Days 11–15

Oct 22, 2026 · @Dimitris

## Overview

Week three (Days 11–15) takes the project from a working form to a deployed, documented, demo-ready app. Each day was planned the same way as before: Claude researched and proposed options, Dimitris chose, and a day was only closed once he approved it.

**What week three adds**

- **Day 11:** the results page, with ranges, a break-even band, drivers, comparables and honest accuracy numbers.
- **Day 12:** the public side: browse, detail pages, curated home rows and TMDB attribution.
- **Day 13:** compare with up to 3 variants, a release-month sweep, every error state, and a quality pass.
- **Day 14:** deployment on Render Free (no card), monitoring and an interview-day safety net.
- **Day 15:** documentation, model card, demo script and interview preparation.

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

## Day 14: Deployment

Day 14 ends with the app live at a public link on a free host that needs no card, verified end to end, monitored, and backed up for interview day.

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
| Deploys | Manual only (`make deploy` via deploy hook); auto-deploy off | A quick commit can't break the live demo |
| Domain | Platform address | Free, works immediately |
| Speed | 400 ms local target; up to about 3 s live, stated honestly in the README | 0.1 CPU is slow |
| Memory | int8 MiniLM; Day 9 gate under about 450 MB | Fits 512 MB safely |
| Monitoring | Uptime alerts on `/api/v1/health` + Sentry on backend and frontend | Know about problems before the interviewer does |
| Safety net | Warm-up routine, local `docker compose`, recorded demo | The demo works even if the network doesn't |

### Tasks

0. **Carry-over (if needed).** Finish Day 13 first.
1. **Single production container (1 h).** React build copied into the backend image and served by FastAPI; unknown paths fall back to `index.html`; CORS limited to the live domain; rate limit on; `/docs` public; no secrets needed.
2. **int8 encoder swap (45 min, only if Day 3 was built with full precision).** Consistency check on validation films: embeddings nearly identical and prediction shifts tiny compared with range width. Pass → use int8; fail → keep full precision. No retraining, so the Day 6 test results stay valid.
3. **Render setup (1 h).** Free web service from the GitHub repo with our Dockerfile; Frankfurt; auto-deploy off; `make deploy` triggers the deploy hook; rollback from the dashboard.
4. **Live verification (1 h).** `scripts/smoke.py` against the public URL; full manual run-through on desktop and phone in both themes; attribution check; record wake-up time and live prediction speed.
5. **Monitoring (1 h).** Uptime alerts (not keep-alive); Sentry on FastAPI and React with one test error.
6. **Safety net (1 h).** Warm-up routine; local `docker compose up` from a clean clone; 2–3 minute demo video plus a README GIF.
7. **Wrap-up (30 min).** README: live link, honest live-speed numbers, deployment section; `PROGRESS.md`; tag `v1.0`.

**Future upgrade (README next step):** a fully static version, with models in ONNX running in the browser and browse data as files, would host free anywhere with no sleeping.

**Done when** the live link passes the smoke test and the manual run-through, monitoring and Sentry are active, and both backups are ready.

## Day 15: Documentation and demo prep

Day 15 ends with a repo that explains itself in 30 seconds or in depth, a rehearsed 5-minute demo, and everything needed for the interview conversation.

### Decisions

| Topic | Decision | Why |
| --- | --- | --- |
| README | Focused README + `docs/` folder | Skimmers get the essentials; engineers can go deep |
| Diagrams | Mermaid, rendered on GitHub | Versioned with the code, no redrawing |
| Decision log | `docs/decisions.md` | Answers "why did you choose X?" in writing |
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
| 4:00–4:30 | Public side | Browse → detail → "Predict a film like this" |
| 4:30–5:00 | Under the hood | Time-split evaluation, time-travel test, architecture in one line |

### Tasks

1. **README and docs (2 h).** README: pitch, live link, GIF, key test results, quick start, architecture, limitations, next steps, attribution. `docs/`: `data.md`, `modeling.md`, `evaluation.md`, `api.md`.
2. **Mermaid diagrams (45 min).** System (browser → FastAPI → SQLite + models, plus the offline pipeline) and prediction flow (form → features → budget → revenue → score → drivers → comparables).
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
| 3 | MiniLM quantized to int8 before training; if already built, swapped at inference on Day 14 after a consistency check | Fits Render Free's 512 MB and 0.1 CPU without retraining after the test run |
| 9 | Memory measurement becomes a gate: under about 450 MB after 100 predictions | Render Free has 512 MB RAM |
| 8 | New endpoints: `GET /model-card` (Day 11) and `POST /predict/sweep` (Day 13) | Accuracy panel and month sweep |
| 8 | `GET /movies` gains a score filter, loses the money-data filter (Day 12) | Visitor preference |

## Sources

- [Render: platforms with a real free tier in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026.md): no-card free web services, 15-minute sleep, Fly.io free tier status
- [Render free tier details (agentdeals.dev)](https://agentdeals.dev/vendor/render): 512 MB RAM, 0.1 CPU
- [Render.com in mid-2026 (jwatte.com)](https://jwatte.com/blog/render-com-platform-review.md): bandwidth cut, about 1 minute to wake
- [Hugging Face Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview): Docker Spaces need a paid plan
- [Railway vs Render vs Fly.io, October 2026 (apicostcalc.com)](https://apicostcalc.com/blog/railway-render-flyio-three-real-hosting-bills-2026.html): Railway trial credit, Render free hours
- [Google Cloud Run pricing](https://cloud.google.com/run/pricing?hl=nl): free tier figures
