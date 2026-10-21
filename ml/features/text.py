"""Sentence embeddings with MiniLM (all-MiniLM-L6-v2) on ONNX Runtime. No PyTorch.

    download_model()         -> fetch the pinned ONNX model and tokenizer into ml/artifacts/minilm/
    model_available()        -> True when both files are present
    Embedder().embed(texts)  -> (n, 384) float32 array, one L2-normalised vector per text

The pooling matches sentence-transformers: mean of the token vectors over the attention mask,
then L2 normalisation, so the dot product of two vectors is their cosine similarity.

CLI: uv run python -m ml.features.text   (download if needed, then a quick sanity check)
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Sequence

import httpx
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"  # pinned commit, so every download is identical
MODEL_DIR = Path("ml/artifacts/minilm")
MODEL_FILES = {  # repo path -> (local name, sha256)
    "onnx/model.onnx": ("model.onnx", "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452"),
    "tokenizer.json": ("tokenizer.json", "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037"),
}
EMBED_DIM = 384
MAX_TOKENS = 256  # the model was trained on inputs up to 256 word pieces; longer text is cut
BATCH_SIZE = 64


# ---------------------------------------------------------------- download


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_available(model_dir: Path = MODEL_DIR) -> bool:
    return all((model_dir / name).exists() for name, _ in MODEL_FILES.values())


def download_model(model_dir: Path = MODEL_DIR) -> None:
    """Download each missing file to a .part file, check its hash, then move it into place."""
    model_dir.mkdir(parents=True, exist_ok=True)
    for repo_path, (name, sha256) in MODEL_FILES.items():
        target = model_dir / name
        if target.exists() and (sha256 is None or _sha256(target) == sha256):
            continue
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{repo_path}"
        part = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {repo_path} ...")
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
                r.raise_for_status()
                with part.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            got = _sha256(part)
            if sha256 is not None and got != sha256:
                raise RuntimeError(f"{repo_path}: sha256 {got} does not match the pinned {sha256}")
            os.replace(part, target)
        finally:
            part.unlink(missing_ok=True)
        print(f"  saved {target} ({target.stat().st_size / 1e6:.1f} MB, sha256 {_sha256(target)})")


# ---------------------------------------------------------------- embedding


class Embedder:
    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        if not model_available(model_dir):
            raise FileNotFoundError(f"MiniLM not found in {model_dir}; run `make model` first")
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(MAX_TOKENS)
        self.tokenizer.enable_padding()  # pad each batch to its longest text
        self.session = ort.InferenceSession(str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}

    def _batch(self, texts: list[str]) -> np.ndarray:
        encodings = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        tokens = self.session.run(None, {k: v for k, v in inputs.items() if k in self.input_names})[0]
        weights = mask[:, :, None].astype(np.float32)
        pooled = (tokens * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
        return pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)

    def embed(self, texts: Sequence[str], batch_size: int = BATCH_SIZE) -> np.ndarray:
        """Embed texts in batches of similar length (less padding), returned in the input order."""
        out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            out[idx] = self._batch([texts[i] for i in idx])
        return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    download_model()
    embedder = Embedder()
    a, b, c = embedder.embed(["a bank heist", "robbers steal money", "a love story in Paris"])
    print(f"heist vs robbers: {a @ b:.3f}   heist vs love story: {a @ c:.3f}")
    if not a @ b > a @ c:
        raise SystemExit("Sanity check failed: the heist sentences should be the closest pair")
    print("Sanity check passed.")


if __name__ == "__main__":
    main()
