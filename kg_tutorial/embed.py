"""Embedding helper using sentence-transformers locally.

Why local instead of an API:
- No additional API key required
- Runs in milliseconds on Apple Silicon
- You can see the model — no magic
- BGE-small (134 MB) is the best size/quality tradeoff for tutorials in 2026

The model is loaded lazily so import is instant; first `embed()` call
downloads weights to `~/.cache/huggingface/` (~134 MB).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from kg_tutorial import config


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(config.EMBED_MODEL)


def embed(texts: str | list[str]) -> np.ndarray:
    """Return L2-normalized embeddings.

    Shape:
      - `embed("hi")`   → (D,)
      - `embed(["hi", "yo"])` → (2, D)
    where D=384 for BGE-small.

    L2-normalization is critical: cosine similarity then equals the dot
    product, which is what every vector store expects.
    """
    is_single = isinstance(texts, str)
    batch = [texts] if is_single else texts
    vectors = _model().encode(batch, normalize_embeddings=True, show_progress_bar=False)
    return vectors[0] if is_single else vectors


def dimension() -> int:
    return _model().get_sentence_embedding_dimension()
