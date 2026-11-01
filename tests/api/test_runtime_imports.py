"""The serving path must not need the training-only packages (the `ml` dependency group).

The Docker image installs the runtime dependencies only (`uv sync --no-default-groups`), so a module-level
import of optuna, matplotlib, scikit-learn, onnx or pillow on the way from `backend.app.main` to a prediction would
crash the container at start. A subprocess blocks those packages (an import raises ImportError, as in the image)
and imports the app and the whole predict path; other tests' imports can't hide a problem this way.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# distribution name -> import name, where they differ
IMPORT_NAMES = {"scikit-learn": "sklearn", "pillow": "PIL"}

CHILD = """
import importlib.abc, sys
BLOCKED = set({blocked!r})
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(f"{{name}} is training-only and not installed in the image")
sys.meta_path.insert(0, Block())
import backend.app.main, backend.app.settings, ml.predict, ml.features.build, ml.models.chain, ml.models.train
import ml.explain.drivers, ml.explain.comparables, ml.career.forecast
loaded = sorted(BLOCKED & {{m.split(".")[0] for m in sys.modules}})
assert not loaded, loaded
print("ok")
"""


def ml_group_modules() -> list[str]:
    groups = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]
    names = []
    for spec in groups["ml"]:
        dist = spec.split(">")[0].split("=")[0].split("<")[0].strip().lower()
        names.append(IMPORT_NAMES.get(dist, dist))
    return names


def test_ml_group_is_the_expected_one():
    assert {"optuna", "matplotlib", "sklearn", "onnx"} <= set(ml_group_modules())


def test_serving_path_imports_without_the_ml_group():
    code = CHILD.format(blocked=ml_group_modules())
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "ok"
