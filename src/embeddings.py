"""
Embedding backend used for both indexing chunks and embedding QA
queries. Default is a small local sentence-transformers model so
embedding never touches the (rate-limited) LLM free tier quota and
works fully offline once the model is cached.
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError


class LocalSentenceTransformerEmbedder(Embedder):
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, ~80MB

    def __init__(self, model_name: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers"
            ) from exc
        self.model_name = model_name or os.environ.get(
            "EMBEDDING_MODEL", self.DEFAULT_MODEL
        )
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()


class HashingFakeEmbedder(Embedder):
    """Deterministic, dependency-free embedder for tests and offline dry
    runs where downloading a real model isn't possible/desired. NOT
    semantically meaningful - do not use for real QA.
    """

    def __init__(self, dim: int = 64):
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self._dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    @property
    def dimension(self) -> int:
        return self._dim


def get_embedder(provider: str | None = None) -> Embedder:
    provider = provider or os.environ.get("EMBEDDING_PROVIDER", "local")
    if provider == "local":
        return LocalSentenceTransformerEmbedder()
    if provider == "fake":
        return HashingFakeEmbedder()
    raise ValueError(f"Unknown embedding provider: {provider!r}")
