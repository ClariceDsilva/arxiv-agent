from __future__ import annotations

from ..embeddings import Embedder
from ..state import AgentState, Intent

NODE_NAME = "selection_ranking"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def make_selection_ranking_node(embedder: Embedder):
    """Factory so the node can be given an already-constructed embedder
    (dependency injection keeps this testable without downloading a
    real model).
    """

    def selection_ranking_node(state: AgentState) -> AgentState:
        if state.intent != Intent.TOPIC_SEARCH:
            state.log(NODE_NAME, "skipped (specific-paper lookup)")
            return state
        if not state.candidates:
            state.fail("selection_ranking reached with no candidates")
            return state

        query_vec = embedder.embed([state.raw_query])[0]
        abstract_vecs = embedder.embed([c.abstract or c.title for c in state.candidates])

        for candidate, vec in zip(state.candidates, abstract_vecs):
            candidate.relevance_score = round(_cosine(query_vec, vec), 4)

        state.candidates.sort(key=lambda c: c.relevance_score or 0.0, reverse=True)
        state.selected_paper = state.candidates[0]

        state.log(
            NODE_NAME,
            f"selected '{state.selected_paper.title[:60]}' "
            f"(score={state.selected_paper.relevance_score})",
        )
        return state

    return selection_ranking_node
