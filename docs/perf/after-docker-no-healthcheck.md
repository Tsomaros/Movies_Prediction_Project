# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m, --no-healthcheck: the image's HEALTHCHECK turned off); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-02 00:27.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 1295.8 | 1392.8 | 1392.8 | 1203.9 | 0 |
| POST /predict (franchise_blockbuster) | hit | 50.0 | 98.2 | 98.2 | 47.6 | 0 |
| POST /predict (small_drama) | miss | 1297.1 | 1705.6 | 1705.6 | 1207.4 | 0 |
| POST /predict (small_drama) | hit | 49.9 | 50.9 | 50.9 | 47.7 | 0 |
| POST /predict (unknown_cast) | miss | 1205.8 | 1299.8 | 1299.8 | 1202.7 | 0 |
| POST /predict (unknown_cast) | hit | 49.8 | 50.7 | 50.7 | 47.5 | 0 |
| POST /predict/compare (3 variants) | miss | 3696.7 | 4296.6 | 4296.6 | 3693.8 | 0 |
| POST /predict/compare (3 variants) | hit | 49.1 | 97.0 | 97.0 | 3.0 | 0 |
| POST /predict/sweep (12 months) | miss | 500.0 | 600.7 | 600.7 | 494.4 | 0 |
| POST /predict/sweep (12 months) | hit | 49.9 | 51.1 | 51.1 | 47.6 | 0 |
| GET /movies (genre, years, sort=score) | - | 102.0 | 196.5 | 196.5 | 99.3 | 0 |
| GET /movies (language, score_min, page 2) | - | 5.7 | 95.8 | 95.8 | 47.2 | 0 |
| GET /movies (home row: popularity) | - | 102.3 | 195.0 | 195.0 | 99.7 | 0 |
| GET /movies/299536 (detail) | - | 104.4 | 202.6 | 202.6 | 101.8 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.4 | 96.3 | 96.3 | 2.5 | 0 |
| GET /movies?q=the (search, common word) | - | 700.6 | 800.0 | 800.0 | 698.0 | 0 |
| GET /people?role=actor&q=tom ha | - | 5.0 | 97.0 | 97.0 | 4.2 | 0 |
| GET /people?role=director&q=nol | - | 4.2 | 95.2 | 95.2 | 2.3 | 0 |
| GET /companies?q=univ | - | 3.1 | 92.8 | 92.8 | 1.3 | 0 |
| GET /people/31 (Tom Hanks) | - | 106.3 | 200.4 | 200.4 | 101.8 | 0 |
| GET /people/525 (Christopher Nolan) | - | 100.2 | 193.0 | 193.0 | 97.4 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 1706 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 4297 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 800 ms | FAIL |
