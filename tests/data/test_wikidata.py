import json
from pathlib import Path

import httpx

from ml.data import wikidata
from ml.data.wikidata import WikidataClient, flatten_bindings, parse_rows

FIXTURE = Path(__file__).parents[1] / "fixtures" / "wikidata_year.json"


def fixture_rows() -> list[dict[str, str]]:
    return flatten_bindings(json.loads(FIXTURE.read_text(encoding="utf-8")))


def row(**changes: str) -> dict[str, str]:
    base = dict(fixture_rows()[0])
    base.update(changes)
    return base


def test_parse_rows_reads_both_properties():
    statements, report = parse_rows(fixture_rows(), year=2001)
    by_prop: dict[str, dict] = {}
    for s in statements:
        by_prop.setdefault(s["prop"], s)
    assert set(by_prop) == {"box_office", "budget"}
    assert len(statements) == 3
    box = by_prop["box_office"]
    assert box["tmdb_id"] == 1001 and isinstance(box["tmdb_id"], int)
    assert box["currency"] == "USD" and box["wikidata_id"] == "Q100"
    assert box["rank"] == "preferred" and box["region"] == "Q13780930"
    assert box["point_in_time"] == "2001-12-31" and box["year"] == 2001
    assert by_prop["budget"]["rank"] == "normal" and by_prop["budget"]["region"] is None
    assert by_prop["budget"]["amount"] == 60_000_000
    assert report["skipped_deprecated"] == 1


def test_parse_rows_amount_formats():
    statements, report = parse_rows(
        [row(amount="+1.5E8"), row(st="s2", amount="+2500000.75"), row(st="s3", amount="abc")]
    )
    assert [s["amount"] for s in statements] == [150_000_000, 2_500_001]
    assert report["skipped_bad_amount"] == 1
    assert "iso" not in fixture_rows()[2]
    assert parse_rows([fixture_rows()[2]])[0][0]["currency"] is None


def test_parse_rows_bad_tmdb_id():
    statements, report = parse_rows([row(tmdb="tv/1234"), row(tmdb="")])
    assert statements == [] and report["skipped_bad_tmdb_id"] == 2


def test_parse_rows_drops_deprecated():
    rank = "http://wikiba.se/ontology#DeprecatedRank"
    statements, report = parse_rows([row(rank=rank)])
    assert statements == [] and report["skipped_deprecated"] == 1


def test_client_retries_on_429():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))

    sleeps: list[float] = []
    client = WikidataClient(sleep=sleeps.append, transport=httpx.MockTransport(handler))
    rows = client.query("SELECT 1")
    assert len(rows) == 6 and len(calls) == 2
    assert sleeps == [1]
    assert calls[0].headers["user-agent"] == wikidata.USER_AGENT
    assert calls[0].headers["accept"] == "application/sparql-results+json"
