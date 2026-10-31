import argparse
import json
import re
from pathlib import Path

import httpx
import pytest

from ml.data import wikidata
from ml.data.pull import load_discover_ids
from ml.data.wikidata import (
    WikidataClient,
    main,
    parse_years,
    append_new_ids,
    flatten_bindings,
    new_ids,
    parse_rows,
    pulled_years,
    run_pull,
)

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


# ---------------------------------------------------------------- Task 2: pull and new ids


def make_row(st: str, tmdb: str = "1001", prop: str = "budget") -> dict[str, str]:
    return {
        "st": f"http://www.wikidata.org/entity/statement/{st}",
        "item": f"http://www.wikidata.org/entity/Q{tmdb}",
        "tmdb": tmdb,
        "prop": prop,
        "amount": "+1000",
        "iso": "USD",
        "rank": "http://wikiba.se/ontology#NormalRank",
    }


class FakeClient:
    def __init__(self, by_year: dict[int, list[dict[str, str]]]) -> None:
        self.by_year = by_year
        self.queried: list[int] = []

    def query(self, sparql: str) -> list[dict[str, str]]:
        year = int(re.search(r"YEAR\(\?date\) = (\d+)", sparql).group(1))
        self.queried.append(year)
        return self.by_year.get(year, [])


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_pull_resumes_by_year(tmp_path):
    path = tmp_path / "w.jsonl"
    by_year = {y: [make_row(f"S{y}", tmdb=str(y))] for y in (2001, 2002, 2003)}
    first = FakeClient(by_year)
    run_pull(first, range(2001, 2003), path)
    assert first.queried == [2001, 2002]
    assert pulled_years(path) == {2001, 2002}
    second = FakeClient(by_year)
    run_pull(second, range(2001, 2004), path)
    assert second.queried == [2003]
    assert [x["year"] for x in lines(path)] == [2001, 2002, 2003]


def test_pull_dedupes_statements_across_years(tmp_path):
    path = tmp_path / "w.jsonl"
    same = make_row("SAME")
    run_pull(FakeClient({2001: [same], 2002: [same, make_row("OTHER", tmdb="7")]}), range(2001, 2003), path)
    statements = [x for x in lines(path) if "statement" in x]
    assert sorted(x["statement"] for x in statements) == ["OTHER", "SAME"]
    assert next(x for x in statements if x["statement"] == "SAME")["year"] == 2001
    assert pulled_years(path) == {2001, 2002}


def test_empty_year_marked_done(tmp_path):
    path = tmp_path / "w.jsonl"
    client = FakeClient({})
    run_pull(client, range(2001, 2002), path)
    assert lines(path) == [{"year": 2001, "empty": True}]
    run_pull(client, range(2001, 2002), path)
    assert client.queried == [2001]


def write_statements(path: Path, items: list[tuple[int, int]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for year, tmdb in items:
            f.write(json.dumps({"statement": f"S{year}-{tmdb}", "tmdb_id": tmdb, "year": year}) + "\n")
        f.write(json.dumps({"year": 1990, "empty": True}) + "\n")


def test_new_ids_skips_known_and_out_of_range(tmp_path):
    path, ids = tmp_path / "w.jsonl", tmp_path / "ids.csv"
    ids.write_text("year,page,id\n2000,1,10\n", encoding="utf-8")
    write_statements(path, [(2000, 10), (2001, 11), (1959, 12), (2026, 13), (2003, 14), (2002, 14), (1960, 15)])
    assert new_ids(path, ids) == [(1960, 15), (2001, 11), (2002, 14)]


def test_append_new_ids_uses_page_zero(tmp_path):
    ids = tmp_path / "ids.csv"
    ids.write_text("year,page,id\n2004,3,9\n", encoding="utf-8")
    assert append_new_ids(ids, [(2004, 555)]) == 1
    assert ids.read_text(encoding="utf-8").splitlines()[-1] == "2004,0,555"
    assert load_discover_ids(ids, range(2004, 2005)) == [9, 555]


def test_parse_years_accepts_single_year_and_range():
    assert parse_years("2001") == range(2001, 2002)
    assert parse_years("1960-2025") == range(1960, 2026)


@pytest.mark.parametrize("text", ["1959", "2026", "1990-2030", "2005-2001", "abc"])
def test_parse_years_refuses_bad_input(text):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_years(text)


def test_new_ids_command_appends_by_default(tmp_path, monkeypatch):
    raw = tmp_path / "w.jsonl"
    ids = tmp_path / "discover_ids.csv"
    ids.write_text("year,page,id\n2000,1,10\n", encoding="utf-8")
    write_statements(raw, [(2001, 11)])
    monkeypatch.setattr(wikidata, "RAW_WIKIDATA", raw)
    monkeypatch.setattr(wikidata, "RAW_DIR", tmp_path)
    main(["new-ids", "--dry-run"])
    assert len(ids.read_text(encoding="utf-8").splitlines()) == 2
    main(["new-ids"])
    assert ids.read_text(encoding="utf-8").splitlines()[-1] == "2001,0,11"
