"""Yearly exchange rates (World Bank) and conversion of foreign amounts to nominal USD.

Public API:
    FX_FILE, EURO_FIXED, CURRENCY_COUNTRY
    load_fx(path) -> {(currency, year): local currency units per USD}
    to_usd(amount, currency, year, fx) -> nominal USD, or None when no rate is known
    build_fx(years, out, client=None) -> number of rows written to ``out``

CLI:
    uv run python -m ml.data.fx build [--from 1960] [--to 2025] [--out data/fx_rates.csv]
"""

import argparse
import csv
from pathlib import Path

import httpx

FX_FILE = Path("data/fx_rates.csv")

# Irrevocable conversion rates: local units per euro.
EURO_FIXED = {"FRF": 6.55957, "DEM": 1.95583, "ITL": 1936.27, "ESP": 166.386}
EURO_YEAR = 1999

# World Bank country code per currency (extended from the survey).
CURRENCY_COUNTRY: dict[str, str] = {
    "EUR": "EMU",
    "GBP": "GBR",
    "JPY": "JPN",
    "INR": "IND",
    "CNY": "CHN",
    "KRW": "KOR",
    "FRF": "FRA",
    "DEM": "DEU",
    "ITL": "ITA",
    "ESP": "ESP",
}

INDICATOR = "PA.NUS.FCRF"
URL = "https://api.worldbank.org/v2/country/{code}/indicator/" + INDICATOR
USER_AGENT = "MoviePredictionApp/1.5 (https://github.com/Tsomaros)"


def load_fx(path: Path = FX_FILE) -> dict[tuple[str, int], float]:
    with path.open(newline="", encoding="utf-8") as f:
        return {(row["currency"], int(row["year"])): float(row["per_usd"]) for row in csv.DictReader(f)}


def to_usd(amount: float, currency: str | None, year: int, fx: dict) -> float | None:
    """Nominal USD for ``amount`` in ``currency`` in ``year``; None if the currency or rate is unknown."""
    if currency is None:
        return None
    if currency == "USD":
        return amount
    if currency in EURO_FIXED and year >= EURO_YEAR:
        eur = fx.get(("EUR", year))
        if not eur:
            return None
        return amount / EURO_FIXED[currency] / eur
    rate = fx.get((currency, year))
    if not rate:
        return None
    return amount / rate


def _series(client: httpx.Client, code: str, years: range) -> dict[int, float]:
    resp = client.get(
        URL.format(code=code),
        params={"format": "json", "per_page": 200, "date": f"{years.start}:{years.stop - 1}"},
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    body = resp.json()
    rows = body[1] if isinstance(body, list) and len(body) > 1 and body[1] else []
    out: dict[int, float] = {}
    for row in rows:
        if row.get("value") is None:
            continue
        year = int(row["date"])
        if year in years:
            out[year] = float(row["value"])
    return out


def build_fx(years: range, out: Path = FX_FILE, client: httpx.Client | None = None) -> int:
    """Fetch the yearly rate of every currency in CURRENCY_COUNTRY and write ``out`` (currency, year)."""
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
    rows: list[tuple[str, int, float]] = []
    try:
        for currency, code in CURRENCY_COUNTRY.items():
            series = _series(client, code, years)
            if currency in EURO_FIXED:
                # Older World Bank series may already be in euro-equivalents (about 0.8 per USD).
                if series.get(1990, 99.0) < 2:
                    series = {y: v * EURO_FIXED[currency] for y, v in series.items()}
                series = {y: v for y, v in series.items() if y < EURO_YEAR}
            rows.extend((currency, y, v) for y, v in series.items())
    finally:
        if own:
            client.close()
    rows.sort()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["currency", "year", "per_usd"])
        for currency, y, v in rows:
            w.writerow([currency, y, repr(v)])
    tmp.replace(out)
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=["build"])
    p.add_argument("--from", dest="start", type=int, default=1960)
    p.add_argument("--to", dest="end", type=int, default=2025)
    p.add_argument("--out", type=Path, default=FX_FILE)
    a = p.parse_args()
    n = build_fx(range(a.start, a.end + 1), a.out)
    print(f"wrote {n} rates to {a.out}")


if __name__ == "__main__":
    main()
