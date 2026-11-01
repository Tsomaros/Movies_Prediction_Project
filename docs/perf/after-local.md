# Benchmark of http://localhost:8000

Local run (unthrottled); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-02 00:11.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 111.3 | 195.4 | 195.4 | 110.0 | 0 |
| POST /predict (franchise_blockbuster) | hit | 2.9 | 4.0 | 4.0 | 1.5 | 0 |
| POST /predict (small_drama) | miss | 123.3 | 157.4 | 157.4 | 120.7 | 0 |
| POST /predict (small_drama) | hit | 3.1 | 3.9 | 3.9 | 1.7 | 0 |
| POST /predict (unknown_cast) | miss | 107.1 | 141.6 | 141.6 | 106.2 | 0 |
| POST /predict (unknown_cast) | hit | 3.2 | 3.7 | 3.7 | 1.7 | 0 |
| POST /predict/compare (3 variants) | miss | 360.9 | 436.7 | 436.7 | 358.3 | 0 |
| POST /predict/compare (3 variants) | hit | 3.4 | 65.7 | 65.7 | 1.9 | 0 |
| POST /predict/sweep (12 months) | miss | 45.5 | 70.6 | 70.6 | 43.7 | 0 |
| POST /predict/sweep (12 months) | hit | 3.3 | 4.4 | 4.4 | 1.9 | 0 |
| GET /movies (genre, years, sort=score) | - | 16.8 | 37.8 | 37.8 | 14.9 | 0 |
| GET /movies (language, score_min, page 2) | - | 4.7 | 6.5 | 6.5 | 3.2 | 0 |
| GET /movies (home row: popularity) | - | 10.1 | 15.7 | 15.7 | 8.6 | 0 |
| GET /movies/299536 (detail) | - | 15.9 | 21.1 | 21.1 | 14.4 | 0 |
| GET /movies?q=avengers infinity (search) | - | 5.0 | 5.8 | 5.8 | 3.5 | 0 |
| GET /movies?q=the (search, common word) | - | 76.7 | 111.3 | 111.3 | 74.9 | 0 |
| GET /people?role=actor&q=tom ha | - | 6.0 | 7.1 | 7.1 | 4.5 | 0 |
| GET /people?role=director&q=nol | - | 4.0 | 5.1 | 5.1 | 2.7 | 0 |
| GET /companies?q=univ | - | 2.3 | 2.7 | 2.7 | 1.1 | 0 |
| GET /people/31 (Tom Hanks) | - | 23.7 | 34.5 | 34.5 | 20.8 | 0 |
| GET /people/525 (Christopher Nolan) | - | 11.5 | 14.1 | 14.1 | 9.6 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | 195 ms | PASS |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | - | not measured on this run |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | - | not measured on this run |
| G4 | read endpoints p95, throttled <= 300 ms | - | not measured on this run |
