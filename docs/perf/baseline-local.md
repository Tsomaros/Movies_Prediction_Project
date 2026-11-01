# Benchmark of http://localhost:8000

Local run (unthrottled); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-01 20:47.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 160.6 | 186.1 | 186.1 | 159.0 | 0 |
| POST /predict (franchise_blockbuster) | hit | 2.5 | 3.0 | 3.0 | 1.6 | 0 |
| POST /predict (small_drama) | miss | 166.9 | 251.0 | 251.0 | 165.7 | 0 |
| POST /predict (small_drama) | hit | 2.5 | 2.8 | 2.8 | 1.6 | 0 |
| POST /predict (unknown_cast) | miss | 155.1 | 177.4 | 177.4 | 153.7 | 0 |
| POST /predict (unknown_cast) | hit | 2.6 | 2.9 | 2.9 | 1.6 | 0 |
| POST /predict/compare (3 variants) | miss | 654.7 | 732.8 | 732.8 | 656.5 | 0 |
| POST /predict/compare (3 variants) | hit | 3.2 | 3.4 | 3.4 | 2.2 | 0 |
| POST /predict/sweep (12 months) | miss | 1984.6 | 2065.8 | 2065.8 | 1983.7 | 0 |
| POST /predict/sweep (12 months) | hit | 3.2 | 3.5 | 3.5 | 2.3 | 0 |
| GET /movies (genre, years, sort=score) | - | 211.9 | 287.5 | 287.5 | 212.4 | 0 |
| GET /movies (language, score_min, page 2) | - | 43.9 | 68.8 | 68.8 | 42.4 | 0 |
| GET /movies (home row: popularity) | - | 361.3 | 468.2 | 468.2 | 364.9 | 0 |
| GET /movies/299536 (detail) | - | 15.7 | 21.2 | 21.2 | 14.7 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.2 | 5.1 | 5.1 | 3.2 | 0 |
| GET /movies?q=the (search, common word) | - | 171.0 | 235.8 | 235.8 | 169.7 | 0 |
| GET /people?role=actor&q=tom ha | - | 5.4 | 6.3 | 6.3 | 4.5 | 0 |
| GET /people?role=director&q=nol | - | 3.9 | 5.3 | 5.3 | 3.0 | 0 |
| GET /companies?q=univ | - | 2.3 | 2.8 | 2.8 | 1.2 | 0 |
| GET /people/31 (Tom Hanks) | - | 20.4 | 32.6 | 32.6 | 19.0 | 0 |
| GET /people/525 (Christopher Nolan) | - | 11.2 | 16.9 | 16.9 | 10.2 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | 251 ms | PASS |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | - | not measured on this run |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | - | not measured on this run |
| G4 | read endpoints p95, throttled <= 300 ms | - | not measured on this run |
