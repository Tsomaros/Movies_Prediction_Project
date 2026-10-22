"""Plain-English sentences for the drivers, filled with the creator's own values.

    sentence(target, driver, form, features, names=None) -> one driver (drivers.top_drivers) as
                                                            {group, label, direction, strength, estimated, value, text}
    explain(target, drivers, form, features, names=None) -> {"up": [...], "down": [...]}, largest first

`form` is the clean form (contract.validate), `features` its feature row (build_features), so the
budget is the one the model used: the creator's, or the budget model's middle in "budget estimated"
mode. `names` gives display names for referenced people, companies and the franchise when the form
holds only ids (the API looks them up); otherwise the names typed in the form are used.

Each sentence names the creator's value and says which way it pushes and how strongly, never by how
much: "Releasing in December (holiday season) strongly raises the expected revenue." Release timing is
worded by its main part, driver["main_feature"] (drivers.main_feature): the year, or the month and season.
`value` is the creator's value on its own, for the frontend to highlight. No sentence contains a raw
feature name.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from ml.explain.groups import GROUPS
from ml.features.contract import UNRATED
from ml.models.chain import format_money

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
LANGUAGES = {
    "en": "English", "fr": "French", "es": "Spanish", "it": "Italian", "ja": "Japanese", "de": "German",
    "ru": "Russian", "cn": "Cantonese", "hi": "Hindi", "zh": "Mandarin", "pt": "Portuguese", "el": "Greek",
    "tr": "Turkish", "ko": "Korean", "pl": "Polish",
}  # vocab.json's languages (TMDB uses "cn" for Cantonese)
COUNTRIES = {
    "US": "the United States", "FR": "France", "GB": "the United Kingdom", "IT": "Italy", "JP": "Japan",
    "DE": "Germany", "CA": "Canada", "ES": "Spain", "MX": "Mexico", "SU": "the Soviet Union", "HK": "Hong Kong",
    "IN": "India", "BR": "Brazil", "SE": "Sweden", "GR": "Greece",
}  # vocab.json's countries
OUTCOME = {"revenue": "the expected revenue", "budget": "the expected budget", "score": "the expected audience score"}
VERB = {"up": ("raises", "raise"), "down": ("lowers", "lower")}  # (one subject, several)
ADVERB = {"strong": "strongly ", "moderate": "", "slight": "slightly "}
MAX_LISTED = 3  # longer lists of studios or themes end in "and N more"


def _join(items: list[str], limit: int = MAX_LISTED) -> str:
    items = [i for i in items if i]
    if len(items) > limit:
        items = [*items[:limit - 1], f"{len(items) - limit + 1} more"]
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _films(n: float) -> str:
    n = int(n)
    return f"{n} earlier film" if n == 1 else f"{n} earlier films"


def _names(refs: list[Mapping[str, Any]], given: list[str | None] | None) -> list[str]:
    given = list(given or [])
    out = [(given[i] if i < len(given) else None) or (ref or {}).get("name") for i, ref in enumerate(refs)]
    return [n for n in out if n]


def _subject(target: str, driver: Mapping[str, Any], form: Mapping[str, Any], f: Mapping[str, Any],
             names: Mapping[str, Any]) -> tuple[str, str, bool]:
    """(value, subject, plural) for one group: the creator's value, the phrase the sentence starts with,
    and whether that phrase takes a plural verb."""
    group, estimated = driver["group"], bool(driver.get("estimated"))
    if group == "budget":
        value = format_money(math.exp(f["log_budget"]))
        if estimated:
            return f"about {value}", f"The estimated budget of about {value}", False
        return value, f"A budget of {value}", False
    if group == "director":
        who = (_names([form.get("director")], [names.get("director")]) or ["the director"])[0]
        if f.get("director_is_new"):
            return who, f"{who}, with no earlier films as director in our data,", False
        return who, f"{who}'s {_films(f['director_n_films'])}", int(f["director_n_films"]) != 1
    if group == "cast":
        lead = next(iter(_names(form.get("actors") or [], names.get("actors"))), None)
        if f.get("actors_is_new_min"):  # nobody in the cast has an earlier film
            return lead or "the cast", "A cast with no earlier films in our data", False
        return lead or "the cast", f"The cast's earlier films{f' (led by {lead})' if lead else ''}", True
    if group == "franchise":
        name = next(iter(_names([form.get("franchise")], [names.get("franchise")])), None)
        if f.get("is_franchise"):
            label = name or "the franchise"
            return label, f"Being part of {label} ({_films(f['franchise_earlier_films'])})", False
        if name:
            return name, f"Starting {name} as a new franchise", False
        return "no franchise", "Not being part of a franchise", False
    if group == "studio":
        companies = _names(form.get("companies") or [], names.get("companies"))
        if not companies:
            return "no studio", "Having no named studio", False
        several = len(companies) > 1
        return _join(companies), f"{_join(companies)} as {'studios' if several else 'the studio'}", several
    if group == "genre":
        several = len(form.get("genres") or []) > 1
        genres = _join(form.get("genres") or [], limit=5)
        return genres, f"The genre{'s' if several else ''} {genres}", several
    if group == "themes":
        several = len(form.get("themes") or []) > 1
        themes = _join([f'"{t}"' for t in form.get("themes") or []])  # quoted: names like "love and marriage"
        return themes, f"The theme{'s' if several else ''} {themes}", several
    if group == "timing":  # worded by whichever part pushes most: the year, or the month and season
        if driver.get("main_feature") == "year":
            year = str(form["release_year"])
            recent = " (recent films earn less in our data)" \
                if target == "revenue" and driver["direction"] == "down" else ""
            return year, f"Releasing in {year}{recent}", False
        month = MONTHS[form["release_month"] - 1]
        season = " (COVID period)" if f.get("covid_period") else " (holiday season)" if f.get("holiday") \
            else " (summer)" if f.get("summer") else ""
        return month, f"Releasing in {month}{season}", False
    if group == "runtime":
        return f"{form['runtime']} minutes", f"A runtime of {form['runtime']} minutes", False
    if group == "certification":
        cert = form.get("certification")
        if cert in (None, UNRATED):
            return "unrated", "Having no US rating", False
        return cert, f"A{'n' if cert in ('R', 'NC-17') else ''} {cert} rating", False
    if group == "language":
        code = form.get("language")
        lang = LANGUAGES.get(code, code or "unknown")
        return lang, f"{lang} as the original language", False
    if group == "country":
        codes = form.get("countries") or []
        if not codes:
            return "no country", "Having no production country given", False
        where = _join([COUNTRIES.get(c, c) for c in codes])
        return where, f"Producing in {where}", False
    raise KeyError(f"no sentence for group {group!r}")


def sentence(target: str, driver: Mapping[str, Any], form: Mapping[str, Any], features: Mapping[str, Any],
             names: Mapping[str, Any] | None = None) -> dict[str, Any]:
    group, direction, strength = driver["group"], driver["direction"], driver["strength"]
    value, subject, plural = _subject(target, driver, form, features, names or {})
    text = f"{subject} {ADVERB[strength]}{VERB[direction][plural]} {OUTCOME[target]}."
    return {"group": group, "label": GROUPS[group], "direction": direction, "strength": strength,
            "estimated": bool(driver.get("estimated")), "value": value, "text": text[0].upper() + text[1:]}


def explain(target: str, drivers: list[Mapping[str, Any]], form: Mapping[str, Any], features: Mapping[str, Any],
            names: Mapping[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"up": [], "down": []}
    for d in drivers:
        out[d["direction"]].append(sentence(target, d, form, features, names))
    return out
