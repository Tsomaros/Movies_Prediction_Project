"""The built app served by the API (backend/app/web.py, Day 15), on a tiny fake dist/ folder."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import API_PREFIX, Settings
from tests.ml.test_eval import db  # noqa: F401 (fixture: a small movies.db)

INDEX = '<!doctype html><title>Movie Prediction</title><div id="root"></div>'
BUNDLE = "console.log('app');" * 200  # over gzip's 1 KB minimum


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text(BUNDLE, encoding="utf-8")
    (tmp_path / "robots.txt").write_bytes(b"User-agent: *\n")
    (tmp_path / "collages").mkdir()
    (tmp_path / "collages" / "movies.webp").write_bytes(b"RIFF....WEBP")
    (tmp_path.parent / "secret.txt").write_text("not for the web", encoding="utf-8")
    return tmp_path


@pytest.fixture
def web(db, dist):
    with TestClient(create_app(Settings(db_path=db / "movies.db", web_dir=dist), predictor=object())) as c:
        yield c


def test_the_start_page_and_client_routes_get_the_app_never_cached(web):
    for path in ("/", "/predict/result", "/movies/603", "/people/31?role=directing"):
        r = web.get(path)
        assert r.status_code == 200 and r.text == INDEX, path
        assert r.headers["content-type"].startswith("text/html")
        assert r.headers["cache-control"] == "no-cache"


def test_hashed_bundles_are_cached_for_a_year_and_gzipped(web):
    r = web.get("/assets/index-abc123.js", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.text == BUNDLE
    assert "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert r.headers["content-encoding"] == "gzip"


def test_other_files_are_served_as_they_are(web):
    r = web.get("/robots.txt")
    assert r.status_code == 200 and r.text == "User-agent: *\n"
    assert r.headers["cache-control"] == "no-cache"
    assert web.get("/collages/movies.webp").headers["content-type"] == "image/webp"


def test_a_missing_bundle_is_a_404_not_the_app(web):
    assert web.get("/assets/index-old999.js").status_code == 404


def test_unknown_api_paths_stay_json_404s_and_the_api_still_answers(web):
    r = web.get(f"{API_PREFIX}/nothing-here")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    assert web.get(f"{API_PREFIX}/health").status_code == 200
    assert web.get("/openapi.json").status_code == 200
    assert "swagger" in web.get("/docs").text.lower()


def test_paths_outside_the_folder_get_the_app_not_the_file(web):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        r = web.get(path)
        assert "not for the web" not in r.text, path


def test_safety_headers_on_the_app_and_the_api(web):
    for path in ("/", f"{API_PREFIX}/health"):
        h = web.get(path).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["referrer-policy"] == "strict-origin-when-cross-origin"


def test_the_api_serves_no_app_without_web_dir(db):
    with TestClient(create_app(Settings(db_path=db / "movies.db"), predictor=object())) as c:
        assert c.get("/predict/result").status_code == 404


def test_a_web_dir_without_index_html_stops_the_start(db, tmp_path):
    with pytest.raises(ValueError, match="index.html"):
        create_app(Settings(db_path=db / "movies.db", web_dir=tmp_path))
