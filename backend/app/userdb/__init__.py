"""The user database (Day 14): Postgres for the demo account's lists, ratings, notes and sessions.

Movies stay in the read-only SQLite file baked into the image; only user data lives here, because Render
Free wipes the container's disk on every sleep and redeploy. Locally it is the `db` service of
docker compose; live it is Neon (USER_DATABASE_URL).

    pool.py     make_pool(url): a small psycopg pool (1-4 connections, checked before each use)
    migrate.py  migrate(conn): applies migrations/*.sql once each       uv run python -m backend.app.userdb.migrate
    seed.py     the demo account and its starting set (demo_seed.json)  uv run python -m backend.app.userdb.seed
    repo.py     plain SQL for users, sessions, lists, notes and app_state
"""
