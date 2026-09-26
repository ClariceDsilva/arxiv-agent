from __future__ import annotations

from dataclasses import dataclass

from ..embeddings import Embedder
from ..state import Chunk


@dataclass
class RetrievedChunk:
    chunk: Chunk
    similarity: float  # cosine similarity, higher is better


class ChromaChunkStore:
    """Thin wrapper around a local, persistent Chroma collection.

    One collection per paper (named by arxiv_id) so re-running the
    digest on the same paper reuses/overwrites cleanly and QA sessions
    for different papers never bleed into each other.
    """

    def __init__(self, persist_dir: str, embedder: Embedder):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed. Run: pip install chromadb") from exc
        self._embedder = embedder
        self._client = chromadb.PersistentClient(path=persist_dir)
        self.persist_dir = persist_dir

    def _collection_name(self, arxiv_id: str) -> str:
        return f"paper_{arxiv_id.replace('.', '_').replace('/', '_')}"

    def index(self, arxiv_id: str, chunks: list[Chunk]) -> str:
        name = self._collection_name(arxiv_id)
        # start clean each time we (re-)index this paper
        try:
            self._client.delete_collection(name)
        except Exception:
            pass
        collection = self._client.create_collection(name)

        if not chunks:
            return name

        vectors = self._embedder.embed([c.text for c in chunks])
        collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[{"section": c.section, "page": c.page, "order": c.order} for c in chunks],
        )
        return name

    def query(self, arxiv_id: str, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
        name = self._collection_name(arxiv_id)
        collection = self._client.get_collection(name)
        query_vec = self._embedder.embed([query_text])[0]
        result = collection.query(query_embeddings=[query_vec], n_results=top_k)

        out: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]  # cosine distance (0=identical)
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            similarity = max(0.0, 1.0 - dist)
            chunk = Chunk(
                chunk_id=cid,
                text=doc,
                section=meta.get("section", ""),
                page=meta.get("page", 0),
                order=meta.get("order", 0),
            )
            out.append(RetrievedChunk(chunk=chunk, similarity=similarity))
        return out
