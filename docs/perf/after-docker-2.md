# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-02 00:01.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 1299.7 | 2796.5 | 2796.5 | 1249.3 | 0 |
| POST /predict (franchise_blockbuster) | hit | 49.9 | 96.8 | 96.8 | 47.5 | 0 |
| POST /predict (small_drama) | miss | 1297.7 | 2699.9 | 2699.9 | 1295.0 | 0 |
| POST /predict (small_drama) | hit | 50.0 | 94.0 | 94.0 | 47.7 | 0 |
| POST /predict (unknown_cast) | miss | 1204.8 | 2799.9 | 2799.9 | 1201.2 | 0 |
| POST /predict (unknown_cast) | hit | 50.0 | 50.7 | 50.7 | 47.5 | 0 |
| POST /predict/compare (3 variants) | miss | 3699.8 | 6102.9 | 6102.9 | 3698.4 | 0 |
| POST /predict/compare (3 variants) | hit | 49.7 | 95.3 | 95.3 | 45.1 | 0 |
| POST /predict/sweep (12 months) | miss | 500.3 | 592.4 | 592.4 | 498.0 | 0 |
| POST /predict/sweep (12 months) | hit | 49.8 | 51.4 | 51.4 | 47.3 | 0 |
| GET /movies (genre, years, sort=score) | - | 102.0 | 193.6 | 193.6 | 99.2 | 0 |
| GET /movies (language, score_min, page 2) | - | 5.5 | 95.5 | 95.5 | 47.5 | 0 |
| GET /movies (home row: popularity) | - | 102.2 | 195.4 | 195.4 | 99.8 | 0 |
| GET /movies/299536 (detail) | - | 104.6 | 202.0 | 202.0 | 101.8 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.8 | 94.9 | 94.9 | 2.5 | 0 |
| GET /movies?q=the (search, common word) | - | 696.9 | 1400.8 | 1400.8 | 650.0 | 0 |
| GET /people?role=actor&q=tom ha | - | 5.7 | 95.3 | 95.3 | 3.1 | 0 |
| GET /people?role=director&q=nol | - | 4.3 | 95.2 | 95.2 | 2.3 | 0 |
| GET /companies?q=univ | - | 3.2 | 92.2 | 92.2 | 1.2 | 0 |
| GET /people/31 (Tom Hanks) | - | 107.8 | 200.6 | 200.6 | 101.8 | 0 |
| GET /people/525 (Christopher Nolan) | - | 100.9 | 105.5 | 105.5 | 98.0 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 2800 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 6103 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 1401 ms | FAIL |
