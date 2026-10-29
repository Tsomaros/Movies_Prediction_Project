"""Response models for the person pages (Day 14.6).

    PersonMatch   -> GET /people: an autocomplete hit plus a photo thumbnail and the film they're known for
    PeopleSearchPage -> GET /people/search: one page of actors, directors and writers by name, with counts per
                     role (V1.1)
    PersonDetail  -> GET /people/{id}: TMDB details (None where TMDB had none), and per role (acting, directing,
                     writing...) their films and stats from our data (Day 14.7)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.lookup import Match
from backend.app.schemas.movies import MovieSummary
from backend.app.schemas.prediction import Poster


class PersonMatch(Match):
    thumb: Optional[str] = Field(None, description="A small TMDB photo (w185), when TMDB has one")
    known_for: Optional[str] = Field(None, description="Title of their most-voted film in this role")


SearchRole = Literal["all", "actor", "director", "writer"]


class SearchRoleFilms(BaseModel):
    role: Literal["actor", "director", "writer"]
    n_films: int


class KnownFor(BaseModel):
    movie_id: int
    title: str
    year: Optional[int]


class PeopleSearchResult(BaseModel):
    id: int
    name: str
    thumb: Optional[str] = Field(description="A small TMDB photo (w185), when TMDB has one")
    roles: list[SearchRoleFilms] = Field(description="Their roles with at least one film, most films first")
    known_for: Optional[KnownFor] = Field(description="Their most-voted film as an actor, director or writer")


class RoleCounts(BaseModel):
    all: int
    actor: int
    director: int
    writer: int


class PeopleSearchPage(BaseModel):
    q: str
    role: SearchRole
    page: int
    page_size: int
    total: int = Field(description="People matching in this role")
    role_counts: RoleCounts = Field(description="People matching per role (all: in any of the three)")
    results: list[PeopleSearchResult]


class PersonRef(BaseModel):
    id: int
    name: Optional[str]
    shared_films: int


class GenreCount(BaseModel):
    name: str
    films: int


class AvgScore(BaseModel):
    value: float
    films: int = Field(description="Films with a usable score (50+ votes) it averages")


class BoxOffice(BaseModel):
    total: float = Field(description="Worldwide revenue in 2025 dollars, trusted figures only")
    films: int = Field(description="Films with a trusted revenue")
    of: int = Field(description="All their films in this role")


RoleName = Literal["acting", "directing", "writing", "production", "music", "camera", "editing"]


class PersonStats(BaseModel):
    film_count: int = Field(description="Films in this role in our data")
    first_year: Optional[int]
    last_year: Optional[int]
    top_genres: list[GenreCount]
    avg_score: Optional[AvgScore]
    box_office_2025: Optional[BoxOffice]
    top_actor: Optional[PersonRef] = Field(description="In 2+ of these films (never the person); ties by TMDB "
                                                       "popularity, then name")
    top_director: Optional[PersonRef] = Field(description="Directed 2+ of these films; None for the directing role")


class Credit(MovieSummary):
    character: Optional[str] = Field(description="Acting: who they played")
    jobs: list[str] = Field(description="Crew roles: their jobs on the film (writing: Screenplay and/or Writer)")


class Role(BaseModel):
    role: RoleName
    label: str = Field(description="Acting, Directing, Writing, Production, Music, Camera, Editing")
    films: list[Credit] = Field(description="Newest first")
    stats: PersonStats


class PersonDetail(BaseModel):
    id: int
    name: Optional[str]
    photo: Optional[Poster] = Field(description="small: w185, large: h632")
    biography: Optional[str] = Field(description="Plain text; paragraphs separated by blank lines")
    birthday: Optional[str]
    deathday: Optional[str]
    place_of_birth: Optional[str]
    known_for_department: Optional[str]
    imdb_url: Optional[str]
    homepage: Optional[str] = Field(description="http(s) only")
    tmdb_url: str
    main_role: Optional[RoleName] = Field(description="The role the page opens on: TMDB's department when they have "
                                                     "credits in it, else the role with the most films")
    roles: list[Role] = Field(description="Only roles with films, in a fixed order")
