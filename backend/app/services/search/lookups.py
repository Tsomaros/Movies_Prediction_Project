"""Autocomplete for the form (directors, actors, companies and franchises) and the header's people search
(directors, actors and writers, V1.1), searched in memory.

    NameIndex.build(rows)          -> a packed index over (id, name, n_films) rows
    index.search(q, limit=10)      -> [{id, name, n_films}]: names with a word starting with q, most films first
    index.matches(q)               -> the entries of every such name (sorted, unique), for the people search
    Lookups.from_db(con)           -> one NameIndex per kind (KINDS), built from the database (about 3 s; 50 s at 0.1 CPU)
    Lookups.load(con, prebuilt=p)  -> the same, read from a file written by save_prebuilt (refused unless it matches
                                      the database), or built when there is no file
    save_prebuilt(con, path)       -> build the indexes once and save them (joblib, V1.5)

CLI (make docker-build runs it on the image's database):
     uv run python -m backend.app.services.search.lookups [--db build/movies.db] [--out build/lookups.joblib]

Any word of a name can start the match, and the query can run on into later words: "hanks", "tom ha" and
"tom hanks" all find Tom Hanks. Matching is case-insensitive (str.casefold) on whitespace-separated words, and
accents are folded on both sides (Day 14.6): "penelope" finds Penélope Cruz, and so does "penélope".

A plain list of Python strings for the 350k people and their 730k word keys took about 207 MB; here every
name and key lives in one bytes blob with int32 offsets, so the whole index is about 25 MB. A search
binary-searches the sorted keys for the range starting with the query, then keeps the most-filmed names.
"""

from __future__ import annotations

import argparse
import sqlite3
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np

from ml.features.build import database_stamp

KINDS = ("director", "actor", "writer", "company", "collection")
LIMIT = 10
SQL = {  # id, name, number of films in that role, for everyone with at least one film
    "director": """SELECT p.id, p.name, COUNT(DISTINCT c.movie_id) FROM movie_crew c JOIN people p ON p.id = c.person_id
                   WHERE c.job = 'Director' AND p.name IS NOT NULL GROUP BY p.id""",
    "actor": """SELECT p.id, p.name, COUNT(*) FROM movie_cast c JOIN people p ON p.id = c.person_id
                WHERE p.name IS NOT NULL GROUP BY p.id""",
    "writer": """SELECT p.id, p.name, COUNT(DISTINCT c.movie_id) FROM movie_crew c JOIN people p ON p.id = c.person_id
                 WHERE c.job IN ('Screenplay', 'Writer') AND p.name IS NOT NULL GROUP BY p.id""",
    "company": """SELECT co.id, co.name, COUNT(*) FROM movie_companies mc JOIN companies co ON co.id = mc.company_id
                  WHERE co.name IS NOT NULL GROUP BY co.id""",
    "collection": """SELECT cl.id, cl.name, COUNT(*) FROM movies m JOIN collections cl ON cl.id = m.collection_id
                     WHERE cl.name IS NOT NULL GROUP BY cl.id""",
}
_END = b"\xff"  # never appears in UTF-8, so key + _END sorts after every key starting with key


def _normalise(text: str) -> str:
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return " ".join(folded.split())


def _pack(items: list[bytes]) -> tuple[bytes, np.ndarray]:
    offsets = np.zeros(len(items) + 1, dtype=np.int64)
    np.cumsum([len(b) for b in items], out=offsets[1:])
    return b"".join(items), offsets


@dataclass
class NameIndex:
    ids: np.ndarray  # int64, one per entry
    n_films: np.ndarray  # int32
    names: bytes  # UTF-8 display names, packed
    name_offsets: np.ndarray  # int64, len(ids) + 1
    keys: bytes  # casefolded word-start suffixes, packed in sorted order
    key_offsets: np.ndarray  # int64, number of keys + 1
    key_entry: np.ndarray  # int32: the entry each key belongs to

    @classmethod
    def build(cls, rows: Iterable[tuple[int, str, int]]) -> NameIndex:
        ids, counts, names, keys, owners = [], [], [], [], []
        for entry, (id_, name, n) in enumerate(rows):
            ids.append(id_)
            counts.append(n)
            names.append(name.encode("utf-8"))
            words = _normalise(name).split(" ")
            for w in range(len(words)):
                keys.append(" ".join(words[w:]).encode("utf-8"))
                owners.append(entry)
        order = sorted(range(len(keys)), key=keys.__getitem__)
        names_blob, name_offsets = _pack(names)
        keys_blob, key_offsets = _pack([keys[i] for i in order])
        return cls(np.array(ids, dtype=np.int64), np.array(counts, dtype=np.int32), names_blob, name_offsets,
                   keys_blob, key_offsets, np.array(owners, dtype=np.int32)[order] if owners else np.zeros(0, np.int32))

    def __len__(self) -> int:
        return len(self.ids)

    def _key(self, i: int) -> bytes:
        return self.keys[self.key_offsets[i]:self.key_offsets[i + 1]]

    def _first_at_least(self, target: bytes) -> int:
        lo, hi = 0, len(self.key_entry)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._key(mid) < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def name(self, entry: int) -> str:
        return self.names[self.name_offsets[entry]:self.name_offsets[entry + 1]].decode("utf-8")

    def matches(self, q: str) -> np.ndarray:
        prefix = _normalise(q).encode("utf-8")
        if not prefix:
            return np.zeros(0, dtype=np.int32)
        lo, hi = self._first_at_least(prefix), self._first_at_least(prefix + _END)
        return np.unique(self.key_entry[lo:hi])

    def search(self, q: str, limit: int = LIMIT) -> list[dict[str, Any]]:
        entries = self.matches(q)
        if len(entries) > limit:  # keep the most-filmed, then sort those few exactly
            entries = entries[np.argpartition(-self.n_films[entries], limit - 1)[:limit]]
        found = sorted(((int(self.n_films[e]), self.name(e), int(self.ids[e])) for e in entries),
                       key=lambda t: (-t[0], t[1].casefold(), t[2]))
        return [{"id": i, "name": name, "n_films": n} for n, name, i in found]

    @property
    def nbytes(self) -> int:
        arrays = (self.ids, self.n_films, self.name_offsets, self.key_offsets, self.key_entry)
        return len(self.names) + len(self.keys) + sum(a.nbytes for a in arrays)


@dataclass
class Lookups:
    indexes: dict[str, NameIndex]

    @classmethod
    def from_db(cls, con: sqlite3.Connection) -> Lookups:
        return cls({kind: NameIndex.build(con.execute(SQL[kind])) for kind in KINDS})

    @classmethod
    def load(cls, con: sqlite3.Connection, prebuilt: Path | None = None) -> Lookups:
        if prebuilt is None:
            return cls.from_db(con)
        parts = joblib.load(prebuilt)
        if parts["stamp"] != database_stamp(con):
            raise ValueError(f"{prebuilt} was built from another database ({parts['stamp']}, this one is "
                             f"{database_stamp(con)}); rebuild it with `python -m backend.app.services.search.lookups`")
        return cls({kind: NameIndex(**fields) for kind, fields in parts["indexes"].items()})

    def search(self, kind: str, q: str, limit: int = LIMIT) -> list[dict[str, Any]]:
        return self.indexes[kind].search(q, limit)

    @property
    def nbytes(self) -> int:
        return sum(i.nbytes for i in self.indexes.values())


def save_prebuilt(con: sqlite3.Connection, path: Path) -> dict[str, Any]:
    """Plain fields, not NameIndex objects: this module runs as __main__ here, and a pickled class would keep that name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = database_stamp(con)
    joblib.dump({"stamp": stamp, "indexes": {k: vars(i) for k, i in Lookups.from_db(con).indexes.items()}}, path)
    return stamp


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.app.services.search.lookups")
    parser.add_argument("--db", type=Path, default=Path("build/movies.db"))
    parser.add_argument("--out", type=Path, default=Path("build/lookups.joblib"))
    args = parser.parse_args()
    with closing(sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)) as con:
        stamp = save_prebuilt(con, args.out)
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1e6:.0f} MB) for the database built {stamp['built_at']}")


if __name__ == "__main__":
    main()
