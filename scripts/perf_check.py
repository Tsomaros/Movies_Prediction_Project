"""Check that predictions are unchanged since the V1.5 baseline (gate G9).

    uv run python scripts/perf_check.py

Regenerates the snapshot outputs (scripts/perf_snapshot.py) and compares them with
tests/fixtures/perf_snapshot.json: floats within abs_tol=1e-9, everything else exactly. Prints "perf_check: OK"
and exits 0, or prints each difference (path, expected, got) and exits 1. Run it at the end of every task.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

from perf_snapshot import SNAPSHOT, build_snapshot

TOL = 1e-9
MAX_SHOWN = 40


def diff(want: Any, got: Any, path: str = "") -> list[str]:
    if isinstance(want, bool) or isinstance(got, bool) or not (
            isinstance(want, (int, float)) and isinstance(got, (int, float))):
        pass
    else:
        return [] if math.isclose(want, got, rel_tol=0, abs_tol=TOL) else [f"{path}: expected {want!r}, got {got!r}"]
    if isinstance(want, dict) and isinstance(got, dict):
        out = [f"{path}/{k}: missing" for k in sorted(want.keys() - got.keys())]
        out += [f"{path}/{k}: unexpected" for k in sorted(got.keys() - want.keys())]
        for k in sorted(want.keys() & got.keys()):
            out += diff(want[k], got[k], f"{path}/{k}")
        return out
    if isinstance(want, list) and isinstance(got, list):
        out = [f"{path}: length {len(want)} -> {len(got)}"] if len(want) != len(got) else []
        for i, (w, g) in enumerate(zip(want, got)):
            out += diff(w, g, f"{path}[{i}]")
        return out
    return [] if want == got and type(want) is type(got) else [f"{path}: expected {want!r}, got {got!r}"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    want = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    got = json.loads(json.dumps(build_snapshot(), ensure_ascii=False))  # through JSON, as the file went
    problems = diff(want, got)
    if not problems:
        print("perf_check: OK")
        return 0
    print(f"perf_check: FAILED, {len(problems)} difference(s)")
    for line in problems[:MAX_SHOWN]:
        print("  " + line)
    if len(problems) > MAX_SHOWN:
        print(f"  ... and {len(problems) - MAX_SHOWN} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
