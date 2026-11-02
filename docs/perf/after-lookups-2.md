# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-02 11:22.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 1202.2 | 2400.3 | 2400.3 | 1200.2 | 0 |
| POST /predict (franchise_blockbuster) | hit | 49.9 | 59.5 | 59.5 | 47.9 | 0 |
| POST /predict (small_drama) | miss | 1201.4 | 2702.6 | 2702.6 | 1199.6 | 0 |
| POST /predict (small_drama) | hit | 49.8 | 61.0 | 61.0 | 48.0 | 0 |
| POST /predict (unknown_cast) | miss | 1196.4 | 2599.7 | 2599.7 | 1194.0 | 0 |
| POST /predict (unknown_cast) | hit | 50.0 | 96.6 | 96.6 | 48.2 | 0 |
| POST /predict/compare (3 variants) | miss | 3404.1 | 5705.6 | 5705.6 | 3400.8 | 0 |
| POST /predict/compare (3 variants) | hit | 49.8 | 96.9 | 96.9 | 47.4 | 0 |
| POST /predict/sweep (12 months) | miss | 499.7 | 1200.5 | 1200.5 | 493.8 | 0 |
| POST /predict/sweep (12 months) | hit | 50.0 | 59.3 | 59.3 | 47.2 | 0 |
| GET /movies (genre, years, sort=score) | - | 100.3 | 191.6 | 191.6 | 98.2 | 0 |
| GET /movies (language, score_min, page 2) | - | 4.5 | 95.9 | 95.9 | 2.8 | 0 |
| GET /movies (home row: popularity) | - | 100.6 | 193.2 | 193.2 | 98.6 | 0 |
| GET /movies/299536 (detail) | - | 105.3 | 204.7 | 204.7 | 101.8 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.1 | 95.1 | 95.1 | 2.3 | 0 |
| GET /movies?q=the (search, common word) | - | 603.2 | 1400.1 | 1400.1 | 600.8 | 0 |
| GET /people?role=actor&q=tom ha | - | 4.5 | 199.7 | 199.7 | 2.8 | 0 |
| GET /people?role=director&q=nol | - | 3.4 | 93.8 | 93.8 | 1.9 | 0 |
| GET /companies?q=univ | - | 3.0 | 92.8 | 92.8 | 1.3 | 0 |
| GET /people/31 (Tom Hanks) | - | 104.6 | 201.4 | 201.4 | 100.5 | 0 |
| GET /people/525 (Christopher Nolan) | - | 98.7 | 191.7 | 191.7 | 7.8 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 2703 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 5706 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 1400 ms | FAIL |
