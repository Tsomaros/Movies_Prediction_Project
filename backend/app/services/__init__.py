"""Logic between the routers and the model / database.

    prediction.py  -> the prediction cache, compare and the month sweep
    search/        -> the form's autocomplete and the header's people search, in memory
    movies/        -> TMDB image URLs and the Surprise me pick
    career/        -> the Career section's forecast and the model card's made-up films
    fresh/         -> new and upcoming films: the TMDB pull, the merge into movies.db, the 6-hour refresher
    platform/      -> passwords and sessions, rate limits, error reports
"""
