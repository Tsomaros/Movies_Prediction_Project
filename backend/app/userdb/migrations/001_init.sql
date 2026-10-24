-- Day 14: the demo account's lists, ratings, notes and sessions. Every user table has user_id, so real
-- users later need no schema change. movie_id is a TMDB id checked by the API against the movie database
-- (a separate SQLite file), so there is no foreign key for it. Times are UTC timestamptz.

CREATE TABLE users (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      text NOT NULL UNIQUE CHECK (username = lower(username) AND char_length(username) BETWEEN 1 AND 40),
    password_hash text NOT NULL,
    is_demo       boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- One list per film: watched (with an optional date and 1-10 rating) or plan to watch (neither)
CREATE TABLE user_movies (
    user_id    bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    movie_id   integer NOT NULL,
    status     text NOT NULL CHECK (status IN ('watched', 'plan_to_watch')),
    watched_on date,
    rating     smallint CHECK (rating BETWEEN 1 AND 10),
    added_at   timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, movie_id),
    CONSTRAINT only_watched_has_date_and_rating CHECK (status = 'watched' OR (watched_on IS NULL AND rating IS NULL))
);
CREATE INDEX user_movies_by_status ON user_movies (user_id, status, added_at);

-- Private notes, many per film, on any film (listed or not)
CREATE TABLE comments (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    movie_id   integer NOT NULL,
    body       text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000 AND btrim(body) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX comments_by_film ON comments (user_id, movie_id, created_at);

-- Only the SHA-256 of the cookie's random token is stored; logout deletes the row
CREATE TABLE sessions (
    token_hash bytea PRIMARY KEY,
    user_id    bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX sessions_by_expiry ON sessions (expires_at);

-- Small key/value facts, such as last_reset (the Athens date of the last nightly demo reset)
CREATE TABLE app_state (
    key   text PRIMARY KEY,
    value text NOT NULL
);
