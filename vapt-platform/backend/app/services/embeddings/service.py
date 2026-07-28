"""Real embeddings. Two backends:
  1. `remote` — call the embedder sidecar at EMBEDDER_URL (HTTP).
  2. `local` — load sentence-transformers in-process.
  3. `fake` — SHA-based placeholder (matches dedup.engine.fake_embedding).

Set EMBEDDING_BACKEND=remote and EMBEDDER_URL=http://embedder:9090 in
docker-compose to use the sidecar. Default is `remote` if the env var
is set, else `fake`.
"""

from __future__ import annotations

import os
from functools import lru_cache

import httpx

BACKEND = os.environ.get("EMBEDDING_BACKEND", "remote")
URL = os.environ.get("EMBEDDER_URL", "http://embedder:9090")
DIM = 384

_MODEL = None


@lru_cache(maxsize=1)
def _load_st():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None


async def _remote_embed(text: str) -> list[float] | None:
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{URL}/embed", json={"texts": [text]})
            r.raise_for_status()
            data = r.json()
            return data["embeddings"][0]
    except Exception:
        return None


def embed_text(text: str, dim: int = DIM) -> list[float]:
    if BACKEND == "local":
        m = _load_st()
        if m is not None:
            return [float(x) for x in m.encode([text], normalize_embeddings=True)[0]]
    # synchronous fallback to remote (the dedup path is sync; the
    # enrich path is async and may prefer await _remote_embed)
    try:
        import requests
        r = requests.post(f"{URL}/embed", json={"texts": [text]}, timeout=20)
        r.raise_for_status()
        return r.json()["embeddings"][0]
    except Exception:
        from app.services.dedup.engine import fake_embedding
        return fake_embedding(text, dim=dim)
