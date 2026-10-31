"""The "Surprise me" pick (Day 14.5): one random film from the candidates, never one already seen.

    FLOOR                                   -> (fewest votes, lowest score) for whole-database spins
    pick(candidates, seen, exclude, rng)    -> (film id, None, ids left), or (None, reason, []) when nothing is left
    shuffle_ids(left, chosen, rng)          -> up to SHUFFLE other ids, for the reveal's poster shuffle

Reasons: "no_match" when the filters match no film at all, "all_seen" when every match is watched or was
already shown in this tab (`exclude`). The router adds "watchlist_empty" for an empty watchlist.
The candidates come from SQLite and the watched ids from Postgres, so the pick is made here, in Python:
about 11k ids (78k with hidden gems) take a few ms.
"""

from __future__ import annotations

import random
from typing import Iterable, Optional

# Films with a poster on the full database (Oct 24, 2026): 100 votes and 6.0 -> 16,084 films; 200 and 6.0 -> 11,043;
# 500 and 6.5 -> 4,726. Chosen: 200 and 6.0, well-known enough without being only blockbusters.
FLOOR = (200, 6.0)
SHUFFLE = 8


def pick(candidates: Iterable[int], seen: Iterable[int], exclude: Iterable[int],
         rng: random.Random | None = None) -> tuple[Optional[int], Optional[str], list[int]]:
    """Returns (chosen id or None, reason or None, the ids that were left to choose from)."""
    candidates = set(candidates)
    if not candidates:
        return None, "no_match", []
    left = sorted(candidates - set(seen) - set(exclude))  # sorted: the same rng gives the same pick
    if not left:
        return None, "all_seen", []
    return (rng or random).choice(left), None, left


def shuffle_ids(left: list[int], chosen: int, rng: random.Random | None = None) -> list[int]:
    others = [i for i in left if i != chosen]
    return (rng or random).sample(others, min(SHUFFLE, len(others)))
