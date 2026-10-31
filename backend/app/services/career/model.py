"""The made-up films the Career section's model card scores (Day 14.8): "Their usual film" and "Something new".

    PersonSlot, Recipe              -> a person ({id, name}) or "new"; the recipe the card shows and scores
    repeat_collaborators(con, person_id, role, kind, limit)
                                    -> [{id, name}] on 2+ of their films in that role (from repo/career)
    usual_recipe(con, person_id, role, min_votes, next_year, themes)
                                    -> their usual film, from the last 10 rated films in the role; ValueError when
                                       they have none (the API answers 404: no model for them)
    never_done_genres(con, person_id, role)
                                    -> genre ids they have no credit in, in that role
    recent_genre_counts(con, min_votes)
                                    -> (genre pair counts, genre counts) over recent rated films, cached per database
    new_recipe(con, person_id, role, usual, min_votes, themes, genre_id=None)
                                    -> (something new, note); UnknownGenre / GenreAlreadyDone for a bad genre_id
    chips(con, person_id, role, default_genre, min_votes)
                                    -> [{genre_id, name, default}]: up to 4 never-done genres, the default among them
    recipe_to_form(recipe, genre_names)
                                    -> the creator form for the score model (no budget, franchise or companies)
    career_model_response(con, predictions, person_id, role, genre_id, next_year)
                                    -> {usual, new, chips}, or {new} for a chip's genre: each film its recipe and
                                       the score model's range {low, mid, high}; ValueError as usual_recipe,
                                       UnknownGenre / GenreAlreadyDone as new_recipe
    CareerModelCache(size=2000)     -> an LRU of those answers, shared by the thread pool:
                                       cache.response(con, predictions, person_id, role, genre_id, next_year)
                                       keyed by (person, role, genre or "default", model version, next_year)

A recipe is always a form the contract accepts: gaps in their films are filled, never left None. Themes and the
certification come from recent rated films with all the recipe's genres (else its first genre), the month too;
runtime 110 and language "en" when none of their films has one. Only the country may stay None (optional).
"Most common" skips missing values and breaks ties toward the more recent film, then the order within that film.
`themes` is the theme -> keyword ids mapping (predictor.ctx.themes). Recent = repo/career.recent_*.
"""

from __future__ import annotations

import itertools
import sqlite3
import statistics
import threading
from collections import Counter, OrderedDict
from typing import Any, Hashable, Iterable, Literal, TypedDict

from backend.app.repo import career as repo
from backend.app.repo.career import Role, repeat_collaborators
from backend.app.services.prediction import PredictionService
from ml.data.clean import MIN_VOTES
from ml.features.contract import CERTIFICATIONS, MAX_RUNTIME, MIN_ACTORS, MIN_RUNTIME, certification_category

__all__ = ["PersonSlot", "Recipe", "GenreAlreadyDone", "UnknownGenre", "repeat_collaborators", "usual_recipe",
           "never_done_genres", "recent_genre_counts", "new_recipe", "chips", "recipe_to_form", "career_model_response",
           "CareerModelCache"]

PersonSlot = dict[str, Any] | Literal["new"]
ModelRole = Literal["acting", "directing"]
LAST_FILMS, N_GENRES, N_THEMES, N_ACTORS, MAX_CHIPS = 10, 2, 3, 3, 4
DEFAULT_RUNTIME, DEFAULT_LANGUAGE = 110, "en"
EVERY_GENRE = "They've already worked in every genre."


class Recipe(TypedDict):
    genres: list[int]
    themes: list[str]
    language: str
    runtime: int
    release_month: int
    release_year: int
    certification: str
    country: str | None
    director: PersonSlot
    actors: list[PersonSlot]  # 3, as shown on the card
    budget_2025: int | None  # predictor pre-fill only, never scored
    labels: dict[str, list[str]]  # genres, themes, collaborators (named people other than the person)


class UnknownGenre(ValueError):
    pass


class GenreAlreadyDone(ValueError):
    pass


# ---------------------------------------------------------------- helpers


def _most_common(per_film: list[Iterable[Hashable]], n: int) -> list[Any]:
    """The n values on the most films (per_film oldest first, None skipped); ties go to the value in the more
    recent film, then to its order within that film."""
    count: Counter[Any] = Counter()
    last: dict[Any, tuple[int, int]] = {}
    for i, values in enumerate(per_film):
        for j, v in enumerate(dict.fromkeys(x for x in values if x is not None)):
            count[v] += 1
            last[v] = (i, -j)
    return sorted(count, key=lambda v: (-count[v], (-last[v][0], -last[v][1])))[:n]


def _themes_of(keywords: set[int], themes: dict[str, set[int]]) -> list[str]:
    return [name for name, ids in themes.items() if keywords & ids]


def _recent_fill(con: sqlite3.Connection, genres: list[int], min_votes: int,
                 themes: dict[str, set[int]]) -> dict[str, Any]:
    """Top themes, certification and month of recent rated films with all these genres (else the first genre)."""
    films = repo.recent_films(con, min_votes, genres) or (repo.recent_films(con, min_votes, genres[:1]) if genres else [])
    theme_count = Counter(t for f in films for t in _themes_of(f["keywords"], themes))
    certs = Counter(certification_category(f["certification"]) for f in films if f["certification"] is not None)
    months = Counter(f["month"] for f in films if f["month"] is not None)
    return {
        "themes": sorted(theme_count, key=lambda t: (-theme_count[t], t))[:N_THEMES],
        "certification": min(certs, key=lambda c: (-certs[c], CERTIFICATIONS.index(c)), default=None),
        "month": min(months, key=lambda m: (-months[m], m), default=None),
    }


def _slot(person_id: int, name: str | None) -> dict[str, Any]:
    return {"id": person_id, "name": name}


def _labels(con: sqlite3.Connection, r: dict[str, Any], person_id: int) -> dict[str, list[str]]:
    names = repo.genre_names(con)
    people = [s for s in (r["director"], *r["actors"]) if s != "new" and s["id"] != person_id]
    return {"genres": [names[g] for g in r["genres"]], "themes": list(r["themes"]),
            "collaborators": list(dict.fromkeys(s["name"] for s in people))}  # an actor-director once


# ---------------------------------------------------------------- their usual film


def usual_recipe(con: sqlite3.Connection, person_id: int, role: ModelRole, min_votes: int, next_year: int,
                 themes: dict[str, set[int]]) -> Recipe:
    rated = [f["movie_id"] for f in repo.career_films(con, person_id, role, min_votes) if f["rated"]][-LAST_FILMS:]
    if not rated:
        raise ValueError(f"person {person_id} has no rated {role} films")
    details = repo.film_details(con, rated)
    films = [details[i] for i in rated]  # oldest first

    def common(key: str) -> Any:
        top = _most_common([[f[key]] for f in films], 1)
        return top[0] if top else None

    genres = _most_common([f["genres"] for f in films], N_GENRES)
    if not genres:  # none of their films has a genre: the most common recent one
        genres = [min(recent_genre_counts(con, min_votes)[1].items(), key=lambda t: (-t[1], t[0]))[0]]
    fill = _recent_fill(con, genres, min_votes, themes)
    runtimes = [f["runtime"] for f in films if f["runtime"] is not None]
    budgets = [f["budget_2025"] for f in films if f["budget_2025"] is not None]
    certs = _most_common([[None if f["certification"] is None else certification_category(f["certification"])]
                          for f in films], 1)
    countries = _most_common([f["countries"] for f in films], 1)

    me = _slot(person_id, repo.person_name(con, person_id))
    if role == "acting":
        actors: list[PersonSlot] = [me, *repeat_collaborators(con, person_id, role, "actor", N_ACTORS - 1)]
        director: PersonSlot = next(iter(repeat_collaborators(con, person_id, role, "director", 1)), "new")
    else:
        actors, director = list(repeat_collaborators(con, person_id, role, "actor", N_ACTORS)), me
    recipe = {
        "genres": genres,
        "themes": _most_common([_themes_of(f["keywords"], themes) for f in films], N_THEMES) or fill["themes"],
        "language": common("language") or DEFAULT_LANGUAGE,
        "runtime": min(max(round(statistics.median(runtimes)), MIN_RUNTIME), MAX_RUNTIME) if runtimes else DEFAULT_RUNTIME,
        "release_month": common("month") or fill["month"],
        "release_year": next_year,
        "certification": certs[0] if certs else fill["certification"],
        "country": countries[0] if countries else None,
        "director": director,
        "actors": actors + ["new"] * (N_ACTORS - len(actors)),
        "budget_2025": round(statistics.median(budgets)) if budgets else None,
    }
    return {**recipe, "labels": _labels(con, recipe, person_id)}  # type: ignore[typeddict-item]


# ---------------------------------------------------------------- something new


def never_done_genres(con: sqlite3.Connection, person_id: int, role: Role) -> set[int]:
    return set(repo.genre_names(con)) - repo.credited_genres(con, person_id, role)


_COUNTS: dict[tuple[str, int], tuple[Counter[frozenset[int]], Counter[int]]] = {}


def recent_genre_counts(con: sqlite3.Connection, min_votes: int) -> tuple[Counter[frozenset[int]], Counter[int]]:
    """Every 2-genre combination of each recent rated film's genres, and each genre, counted once per film. Cached per
    process by database file and vote threshold."""
    path = next(r[2] for r in con.execute("PRAGMA database_list") if r[1] == "main")
    key = (path, min_votes)
    if key not in _COUNTS:
        lists = repo.recent_genre_lists(con, min_votes)
        pairs = Counter(frozenset(p) for g in lists for p in itertools.combinations(g, 2))
        _COUNTS[key] = (pairs, Counter(x for g in lists for x in g))
    return _COUNTS[key]


def _new_genres(never: set[int], pairs: Counter[frozenset[int]], singles: Counter[int],
                genre_id: int | None) -> list[int]:
    """The default pick (pair, else single) or the chip genre plus its partner; [] when nothing is never done."""
    def pair_key(p: frozenset[int]) -> tuple[int, list[int]]:
        return -pairs[p], sorted(p)

    if genre_id is None:
        open_pairs = [p for p in pairs if p <= never]
        if open_pairs:
            pick = min(open_pairs, key=pair_key)
            return sorted(pick, key=lambda g: (-singles[g], g))
        return [min(never, key=lambda g: (-singles[g], g))] if never else []
    partners = [p for p in pairs if genre_id in p and p <= never]
    return sorted(min(partners, key=pair_key), key=lambda g: g != genre_id) if partners else [genre_id]


def new_recipe(con: sqlite3.Connection, person_id: int, role: ModelRole, usual: Recipe, min_votes: int,
               themes: dict[str, set[int]], genre_id: int | None = None) -> tuple[Recipe, str | None]:
    never = never_done_genres(con, person_id, role)
    if genre_id is not None:
        if genre_id not in repo.genre_names(con):
            raise UnknownGenre(genre_id)
        if genre_id not in never:
            raise GenreAlreadyDone(genre_id)
    pairs, singles = recent_genre_counts(con, min_votes)
    genres = _new_genres(never, pairs, singles, genre_id)
    note = None if genres else EVERY_GENRE
    genres = genres or list(usual["genres"])
    fill = _recent_fill(con, genres, min_votes, themes)
    me = _slot(person_id, repo.person_name(con, person_id))
    recipe = {**usual, "genres": genres, "themes": fill["themes"] or list(usual["themes"]),
              "director": me if role == "directing" else "new",
              "actors": [me if role == "acting" else "new"] + ["new"] * (N_ACTORS - 1)}
    recipe.pop("labels")
    return {**recipe, "labels": _labels(con, recipe, person_id)}, note  # type: ignore[return-value]


def chips(con: sqlite3.Connection, person_id: int, role: Role, default_genre: int | None,
          min_votes: int) -> list[dict[str, Any]]:
    names = repo.genre_names(con)
    singles = recent_genre_counts(con, min_votes)[1]
    ranked = sorted(never_done_genres(con, person_id, role), key=lambda g: (-singles[g], g))
    shown = ranked[:MAX_CHIPS]
    if default_genre in ranked and default_genre not in shown:
        shown[-1] = default_genre
    return [{"genre_id": g, "name": names[g], "default": g == default_genre} for g in shown]


# ---------------------------------------------------------------- scoring


def _ref(slot: PersonSlot, new_name: str) -> dict[str, Any]:
    return {"name": new_name} if slot == "new" else {"id": slot["id"], "name": slot["name"]}


def recipe_to_form(recipe: Recipe, genre_names: dict[int, str]) -> dict[str, Any]:
    """The creator form the score model gets: the recipe's people, then new actors up to MIN_ACTORS."""
    slots = recipe["actors"] + ["new"] * (MIN_ACTORS - len(recipe["actors"]))
    return {
        "genres": [genre_names[g] for g in recipe["genres"]],
        "themes": list(recipe["themes"]),
        "runtime": recipe["runtime"],
        "language": recipe["language"],
        "certification": recipe["certification"],
        "release_year": recipe["release_year"],
        "release_month": recipe["release_month"],
        "director": _ref(recipe["director"], "New director"),
        "actors": [_ref(s, f"New actor {i}") for i, s in enumerate(slots, 1)],
        "countries": [recipe["country"]] if recipe["country"] else [],
    }


def _scored(predictions: PredictionService, recipe: Recipe, names: dict[int, str]) -> dict[str, Any]:
    """The recipe and the score model's range, through the same validation and cache as POST /predict."""
    out, _ = predictions.predict(recipe_to_form(recipe, names))
    s = out["score"]
    return {"recipe": recipe, "prediction": {"low": s["low"], "mid": s["middle"], "high": s["high"]}}


def career_model_response(con: sqlite3.Connection, predictions: PredictionService, person_id: int, role: ModelRole,
                          genre_id: int | None, next_year: int) -> dict[str, Any]:
    themes = predictions.predictor.ctx.themes
    names = repo.genre_names(con)
    usual = usual_recipe(con, person_id, role, MIN_VOTES, next_year, themes)
    new, note = new_recipe(con, person_id, role, usual, MIN_VOTES, themes, genre_id)
    something_new = {**_scored(predictions, new, names), "note": note}
    if genre_id is not None:
        return {"new": something_new}
    default = new["genres"][0] if note is None else None
    return {"usual": _scored(predictions, usual, names), "new": something_new,
            "chips": chips(con, person_id, role, default, MIN_VOTES)}


# ---------------------------------------------------------------- the cache


class CareerModelCache:
    def __init__(self, size: int = 2000):
        self.size = size
        self._cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def response(self, con: sqlite3.Connection, predictions: PredictionService, person_id: int, role: ModelRole,
                 genre_id: int | None, next_year: int) -> dict[str, Any]:
        key = (person_id, role, "default" if genre_id is None else genre_id,
               predictions.predictor.manifest["version"], next_year)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        out = career_model_response(con, predictions, person_id, role, genre_id, next_year)  # outside the lock
        with self._lock:
            self._cache[key] = out
            while len(self._cache) > self.size:
                self._cache.popitem(last=False)
        return out

    def __len__(self) -> int:
        return len(self._cache)
