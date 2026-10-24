"""The connection pool for the user database.

    make_pool(url)  -> an open psycopg ConnectionPool: 1-4 autocommit connections returning dict rows

Neon's free compute suspends after 5 minutes idle and closes its connections, so every checkout is checked
first (a dead connection is replaced, not handed out), and a cold start gets connect_timeout=10 seconds.
Opening the pool doesn't wait for a connection, so the API starts even while the database sleeps.
Connections are in autocommit mode: a write that needs several statements uses `with conn.transaction()`.
"""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

CONNECT_TIMEOUT = 10  # seconds, for a suspended Neon compute to wake
CHECKOUT_TIMEOUT = 15  # seconds to wait for a free connection before giving up (503)


def make_pool(url: str) -> ConnectionPool:
    return ConnectionPool(url, min_size=1, max_size=4, timeout=CHECKOUT_TIMEOUT, check=ConnectionPool.check_connection,
                          kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": CONNECT_TIMEOUT},
                          open=True, name="userdb")
