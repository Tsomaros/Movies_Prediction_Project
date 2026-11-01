# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-01 20:44.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 5602.5 | 11097.3 | 11097.3 | 5647.9 | 0 |
| POST /predict (franchise_blockbuster) | hit | 50.0 | 500.2 | 500.2 | 47.2 | 0 |
| POST /predict (small_drama) | miss | 5704.2 | 9503.5 | 9503.5 | 5748.2 | 0 |
| POST /predict (small_drama) | hit | 49.9 | 93.9 | 93.9 | 47.4 | 0 |
| POST /predict (unknown_cast) | miss | 1495.5 | 3199.2 | 3199.2 | 1494.0 | 0 |
| POST /predict (unknown_cast) | hit | 50.0 | 95.8 | 95.8 | 47.5 | 0 |
| POST /predict/compare (3 variants) | miss | 24395.0 | 35992.3 | 35992.3 | 24398.8 | 0 |
| POST /predict/compare (3 variants) | hit | 6.4 | 96.1 | 96.1 | 47.2 | 0 |
| POST /predict/sweep (12 months) | miss | 70794.7 | 78692.9 | 78692.9 | 70903.2 | 0 |
| POST /predict/sweep (12 months) | hit | 102.8 | 295.4 | 295.4 | 48.9 | 0 |
| GET /movies (genre, years, sort=score) | - | 697.7 | 799.1 | 799.1 | 606.2 | 0 |
| GET /movies (language, score_min, page 2) | - | 199.3 | 204.7 | 204.7 | 195.7 | 0 |
| GET /movies (home row: popularity) | - | 1193.9 | 2300.0 | 2300.0 | 1102.8 | 0 |
| GET /movies/299536 (detail) | - | 104.3 | 202.3 | 202.3 | 101.9 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.4 | 94.8 | 94.8 | 2.4 | 0 |
| GET /movies?q=the (search, common word) | - | 897.9 | 1899.9 | 1899.9 | 894.7 | 0 |
| GET /people?role=actor&q=tom ha | - | 5.2 | 95.6 | 95.6 | 3.2 | 0 |
| GET /people?role=director&q=nol | - | 4.3 | 94.3 | 94.3 | 2.3 | 0 |
| GET /companies?q=univ | - | 3.1 | 92.4 | 92.4 | 1.3 | 0 |
| GET /people/31 (Tom Hanks) | - | 106.4 | 200.3 | 200.3 | 102.1 | 0 |
| GET /people/525 (Christopher Nolan) | - | 100.5 | 190.8 | 190.8 | 97.7 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 11097 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 78693 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 2300 ms | FAIL |
