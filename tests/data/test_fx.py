"""Tests for ml.data.fx: conversion to nominal USD and the World Bank build (offline)."""

import csv

import httpx
import pytest

from ml.data import fx as fxmod
from ml.data.fx import build_fx, load_fx, to_usd


def test_usd_passes_through():
    assert to_usd(123.0, "USD", 1990, {}) == 123.0


def test_converts_with_year_rate():
    assert to_usd(1000, "JPY", 2000, {("JPY", 2000): 100.0}) == 10.0


def test_pre_euro_after_1999_uses_fixed_rate():
    assert to_usd(655957, "FRF", 2005, {("EUR", 2005): 0.8}) == pytest.approx(100000 / 0.8)


def test_pre_euro_after_1999_missing_eur_is_none():
    assert to_usd(1, "DEM", 2005, {}) is None


def test_pre_euro_before_1999_uses_own_series():
    assert to_usd(500, "FRF", 1990, {("FRF", 1990): 5.0}) == 100.0


def test_missing_rate_returns_none():
    fx = {("JPY", 2000): 100.0}
    assert to_usd(1, "EUR", 1995, {}) is None
    assert to_usd(1, None, 2000, fx) is None
    assert to_usd(1, "JPY", 2001, fx) is None


def test_zero_rate_returns_none():
    assert to_usd(1, "JPY", 2000, {("JPY", 2000): 0.0}) is None


def _handler(request: httpx.Request) -> httpx.Response:
    assert "MoviePredictionApp" in request.headers["user-agent"]
    code = request.url.path.split("/country/")[1].split("/")[0]
    series = {
        "FRA": [("1990", 0.82), ("1995", None), ("2005", 0.8)],
        "EMU": [("2005", 0.8), ("2000", 1.08)],
        "DEU": [("1990", 1.62)],
    }.get(code, [])
    rows = [{"date": d, "value": v} for d, v in series]
    return httpx.Response(200, json=[{"page": 1}, rows])


def test_build_fx_rescales_euro_equivalent_series(tmp_path, monkeypatch):
    monkeypatch.setattr(fxmod, "CURRENCY_COUNTRY", {"EUR": "EMU", "FRF": "FRA"})
    out = tmp_path / "fx.csv"
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    n = build_fx(range(1960, 2026), out, client=client)
    fx = load_fx(out)
    assert n == len(fx) == 3
    assert fx[("FRF", 1990)] == pytest.approx(0.82 * 6.55957)
    assert not any(c == "FRF" and y >= 1999 for c, y in fx)
    assert ("FRF", 1995) not in fx  # null value skipped
    assert fx[("EUR", 2000)] == 1.08
    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["currency"], r["year"]) for r in rows] == [("EUR", "2000"), ("EUR", "2005"), ("FRF", "1990")]


def test_build_fx_keeps_an_own_currency_series_below_2(tmp_path, monkeypatch):
    # DEM's 1990 rate (1.62 marks per USD) is below 2 but is not in euro-equivalents.
    monkeypatch.setattr(fxmod, "CURRENCY_COUNTRY", {"DEM": "DEU"})
    out = tmp_path / "fx.csv"
    build_fx(range(1960, 2026), out, client=httpx.Client(transport=httpx.MockTransport(_handler)))
    assert load_fx(out)[("DEM", 1990)] == 1.62
