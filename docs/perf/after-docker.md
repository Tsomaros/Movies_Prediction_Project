# Benchmark of http://localhost:8000

Throttled run (Docker, --cpus 0.1 --memory 512m); 20 repeats after 2 warm-up requests each, one request at a time; 2026-11-01 23:51.

Times are milliseconds measured by the client. `miss` = a prediction the cache did not hold (a new runtime each time), `hit` = the same request again. The gates use the miss rows.

| Endpoint | Cache | p50 | p95 | max | server p50 | errors |
|---|---|---:|---:|---:|---:|---:|
| POST /predict (franchise_blockbuster) | miss | 1296.4 | 1393.0 | 1393.0 | 1206.3 | 0 |
| POST /predict (franchise_blockbuster) | hit | 97.8 | 295.5 | 295.5 | 45.0 | 0 |
| POST /predict (small_drama) | miss | 1299.8 | 1803.8 | 1803.8 | 1297.3 | 0 |
| POST /predict (small_drama) | hit | 96.5 | 295.4 | 295.4 | 48.1 | 0 |
| POST /predict (unknown_cast) | miss | 1292.5 | 1304.9 | 1304.9 | 1203.2 | 0 |
| POST /predict (unknown_cast) | hit | 49.9 | 51.0 | 51.0 | 47.5 | 0 |
| POST /predict/compare (3 variants) | miss | 3699.8 | 5899.2 | 5899.2 | 3697.2 | 0 |
| POST /predict/compare (3 variants) | hit | 49.6 | 97.7 | 97.7 | 23.7 | 0 |
| POST /predict/sweep (12 months) | miss | 499.8 | 596.5 | 596.5 | 495.8 | 0 |
| POST /predict/sweep (12 months) | hit | 103.2 | 393.6 | 393.6 | 97.8 | 0 |
| GET /movies (genre, years, sort=score) | - | 102.0 | 192.7 | 192.7 | 99.3 | 0 |
| GET /movies (language, score_min, page 2) | - | 87.7 | 96.4 | 96.4 | 3.3 | 0 |
| GET /movies (home row: popularity) | - | 102.5 | 196.4 | 196.4 | 99.8 | 0 |
| GET /movies/299536 (detail) | - | 104.3 | 203.4 | 203.4 | 101.7 | 0 |
| GET /movies?q=avengers infinity (search) | - | 4.7 | 95.8 | 95.8 | 2.5 | 0 |
| GET /movies?q=the (search, common word) | - | 696.3 | 793.0 | 793.0 | 606.2 | 0 |
| GET /people?role=actor&q=tom ha | - | 5.8 | 96.8 | 96.8 | 3.5 | 0 |
| GET /people?role=director&q=nol | - | 4.3 | 95.8 | 95.8 | 2.3 | 0 |
| GET /companies?q=univ | - | 3.1 | 91.3 | 91.3 | 1.3 | 0 |
| GET /people/31 (Tom Hanks) | - | 298.3 | 502.2 | 502.2 | 201.2 | 0 |
| GET /people/525 (Christopher Nolan) | - | 100.9 | 191.9 | 191.9 | 98.0 | 0 |

## Gates

| Gate | Target | Slowest p95 | Result |
|---|---|---:|---|
| G1 | POST /predict p95, miss, local <= 400 ms | - | not measured on this run |
| G2 | POST /predict p95, miss, throttled <= 1.5 s | 1804 ms | FAIL |
| G3 | compare and sweep p95, miss, throttled <= 2.5 s | 5899 ms | FAIL |
| G4 | read endpoints p95, throttled <= 300 ms | 793 ms | FAIL |
