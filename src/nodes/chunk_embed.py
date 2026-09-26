from __future__ import annotations

from ..chunking import chunk_paper
from ..state import AgentState
from ..vectorstore.chroma_store import ChromaChunkStore

NODE_NAME = "chunk_embed"


def make_chunk_embed_node(store: ChromaChunkStore):
    def chunk_embed_node(state: AgentState) -> AgentState:
        if state.parsed is None or state.selected_paper is None:
            state.fail("chunk_embed reached with no parsed paper")
            return state

        chunks = chunk_paper(state.parsed, state.selected_paper.arxiv_id)
        if not chunks:
            state.warn("no text available to chunk; QA will have nothing to retrieve from")
            state.chunks = []
            state.log(NODE_NAME, "0 chunks")
            return state

        collection_name = store.index(state.selected_paper.arxiv_id, chunks)
        state.chunks = chunks
        state.vector_collection_name = collection_name
        state.vector_store_path = store.persist_dir

        state.log(NODE_NAME, f"{len(chunks)} chunks indexed into '{collection_name}'")
        return state

    return chunk_embed_node
