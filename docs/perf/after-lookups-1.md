# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-02 11:17.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 1192.4 | 2702.2 | 2702.2 | 1103.7 | 0 |
| POST /predict (franchise_blockbuster) | hit | 50.0 | 50.5 | 50.5 | 48.4 | 0 |
| POST /predict (small_drama) | miss | 1194.6 | 2599.6 | 2599.6 | 1193.2 | 0 |
| POST /predict (small_drama) | hit | 49.9 | 50.5 | 50.5 | 48.1 | 0 |
| POST /predict (unknown_cast) | miss | 1103.3 | 2699.7 | 2699.7 | 1101.2 | 0 |
| POST /predict (unknown_cast) | hit | 49.9 | 50.7 | 50.7 | 48.4 | 0 |
| POST /predict/compare (3 variants) | miss | 3399.9 | 5597.4 | 5597.4 | 3398.1 | 0 |
| POST /predict/compare (3 variants) | hit | 49.8 | 96.2 | 96.2 | 47.8 | 0 |
| POST /predict/sweep (12 months) | miss | 495.0 | 1199.8 | 1199.8 | 448.6 | 0 |
| POST /predict/sweep (12 months) | hit | 50.2 | 296.8 | 296.8 | 48.3 | 0 |
| GET /movies (genre, years, sort=score) | - | 100.5 | 190.7 | 190.7 | 98.2 | 0 |
| GET /movies (language, score_min, page 2) | - | 4.9 | 95.5 | 95.5 | 3.0 | 0 |
| GET /movies (home row: popularity) | - | 100.6 | 192.3 | 192.3 | 98.5 | 0 |
| GET /movies/299536 (detail) | - | 103.1 | 200.3 | 200.3 | 100.7 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.2 | 94.9 | 94.9 | 2.3 | 0 |
| GET /movies?q=the (search, common word) | - | 602.5 | 701.1 | 701.1 | 600.3 | 0 |
| GET /people?role=actor&q=tom ha | - | 4.4 | 95.4 | 95.4 | 2.7 | 0 |
| GET /people?role=director&q=nol | - | 3.7 | 94.9 | 94.9 | 2.1 | 0 |
| GET /companies?q=univ | - | 2.7 | 92.0 | 92.0 | 1.1 | 0 |
| GET /people/31 (Tom Hanks) | - | 104.1 | 201.8 | 201.8 | 100.5 | 0 |
| GET /people/525 (Christopher Nolan) | - | 200.0 | 399.8 | 399.8 | 106.0 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 2702 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 5597 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 701 ms | FAIL |
