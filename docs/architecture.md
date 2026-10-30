# Architecture

How the parts fit together: the offline pipeline that builds the data and the models, the one container that serves the app, and the path of one prediction. Back to the [README](../README.md).

## The system

```mermaid
flowchart LR
    subgraph offline["Offline, on the laptop"]
        tmdb[("TMDB API")] --> pull["ml.data.pull<br/>80,398 films, 1960–2026; models use up to 2025"]
        pull --> db[("data/movies.db<br/>SQLite")]
        db --> features["ml.features<br/>one feature function"]
        features --> models["LightGBM: budget, revenue, score<br/>+ calibration, comparables index"]
        db --> slim["scripts/slim_db.py"]
    end

    subgraph image["One Docker image (ghcr.io, private)"]
        api["FastAPI /api/v1"]
        web["React app<br/>(served by the API)"]
        sqlite[("slim movies.db<br/>read-only")]
        predictor["ml.predict.Predictor"]
        api --- web
        api --> sqlite
        api --> predictor
        refresher["Refresher<br/>(every 6 h, in the background)"]
        fresh[("/tmp/fresh.db<br/>new and upcoming films")]
        api --> refresher
        refresher -->|"os.replace"| fresh
        api -->|"attached, read-only,<br/>shadowing views"| fresh
    end
    tmdb -.->|"discover + details"| refresher
    api -.->|"listed film ids"| neon

    models --> predictor
    slim --> sqlite
    browser["Browser"] -->|"https, one origin"| render["Render Free, Frankfurt<br/>Cloudflare in front"] --> api
    api -->|"demo account:<br/>lists, ratings, notes"| neon[("Neon Postgres 18<br/>Frankfurt")]
    action["GitHub Action<br/>daily smoke"] --> render
```

- **Movies stay read-only.** The films, people and features are a SQLite file baked into the image; every request opens its own read-only connection.
- **New films live in a second small file.** `fresh.db` (the last 14 days and the next 60, plus every film a user listed) has the same schema as the movie tables and is rebuilt in the background every 6 hours. Each request attaches it and reads both files through temporary views; the models, comparables, career data and autocomplete never do ([Fresh films](app.md#new-arrivals-v12)).
- **User data lives elsewhere.** Render Free's disk is wiped on every sleep and redeploy, so the demo account's lists and notes go to Neon's free Postgres ([The app](app.md#accounts-day-14)).
- **The image is built on the laptop** and pushed to a private registry, because its 470 MB of data and models aren't in git ([Deployment](deployment.md#deployment-day-15)).

## One prediction

```mermaid
flowchart TD
    form["Creator's form<br/>(14 fields)"] --> validate["contract.validate<br/>one 422 listing every problem"]
    validate --> asof["Judged at the 1st of the release month<br/>(only earlier films count)"]
    asof --> feats["build_features<br/>track records, basics, themes"]
    feats --> budget["Budget model<br/>p10 / p50 / p90"]
    feats --> revenue{"Budget given?"}
    revenue -->|"yes"| revgiven["Revenue model<br/>'budget given' correction"]
    revenue -->|"no"| revest["Revenue model with the budget model's middle<br/>'budget estimated' correction"]
    budget --> revest
    feats --> score["Score model<br/>p10 / p50 / p90"]
    revgiven --> drivers
    revest --> drivers
    budget --> drivers["Drivers<br/>pred_contrib → 12 creator-friendly groups → sentences"]
    score --> drivers
    drivers --> comps["Comparable films<br/>released before the date, most similar first"]
    comps --> out["JSON: ranges, rough flags, budget comparison,<br/>drivers, comparables, warnings, model version"]
```

- **One feature function** (`ml/features/build.py`) serves training and the app, so they can't drift apart.
- **Every range is calibrated** to hold about 80% of real outcomes; the corrections were learned on out-of-fold predictions ([Models](modeling.md)).
- **The steps** are `ml.predict.Predictor.predict`; the API adds a cache, a rate limit and the same 422 shape for every error ([API](api.md)).
