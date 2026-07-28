"""Standalone sentence-transformers HTTP service.

POST /embed {"texts": ["...", "..."]} → {"embeddings": [[...], [...]]}
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="VAPT Embedder", version="0.1.0")


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    name = os.environ.get("MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return SentenceTransformer(name)


class EmbedIn(BaseModel):
    texts: list[str]


class EmbedOut(BaseModel):
    embeddings: list[list[float]]
    dim: int


@app.post("/embed", response_model=EmbedOut)
def embed(body: EmbedIn) -> EmbedOut:
    m = _model()
    vecs = m.encode(body.texts, normalize_embeddings=True)
    return EmbedOut(embeddings=[[float(x) for x in v] for v in vecs], dim=len(vecs[0]))


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": os.environ.get("MODEL", "sentence-transformers/all-MiniLM-L6-v2")}
