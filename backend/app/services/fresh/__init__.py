"""New and upcoming films, merged into movies.db (V1.2; one database since V1.3).

A film released in the last 14 days or due in the next 60 is stored like any other film, in the movie tables of
movies.db itself, so every page that works for a film from 1995 works for one from last week. Only films dated after
MODEL_DATA_MAX_YEAR (2025), or not dated yet, are ever written, and every model, track record, comparable and the
career backtest reads year <= 2025 only, so no model sees them. The table fresh_films records the ids the refresher
wrote (`added` = 1: the build didn't have the film), fresh_people the people it added (they have no page).

    pull.py       -> the two windows and TMDB's discover and details calls
    merge.py      -> merge_into: the records into movies.db, in one transaction
    refresher.py  -> Refresher: when to refresh, in the background, every 6 hours
    python -m backend.app.services.fresh --once   -> one merge into MOVIES_DB with the settings of .env

The refresh runs only with FRESH_REFRESH=1 (the image), so `make api` never changes the database training reads.
"""
