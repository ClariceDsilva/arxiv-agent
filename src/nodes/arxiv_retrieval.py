from __future__ import annotations

from .. import arxiv_client
from ..state import AgentState, Intent

NODE_NAME = "arxiv_retrieval"
MAX_CANDIDATES = 8


def arxiv_retrieval_node(state: AgentState) -> AgentState:
    try:
        if state.intent == Intent.SPECIFIC_PAPER:
            paper = arxiv_client.fetch_by_id(state.requested_arxiv_id)
            if paper is None:
                state.fail(
                    f"arXiv has no paper with id '{state.requested_arxiv_id}' "
                    "(check the id, or it may have been withdrawn)"
                )
                return state
            state.candidates = [paper]
            state.selected_paper = paper  # nothing to rank, single result
        else:  # TOPIC_SEARCH
            candidates = arxiv_client.search_by_topic(state.raw_query, max_results=MAX_CANDIDATES)
            state.candidates = candidates
            if not candidates:
                # Zero results for a vague/over-specific topic: don't just
                # dead-end - fail with an actionable message rather than
                # crashing downstream nodes on an empty selection.
                state.fail(
                    f"arXiv returned zero results for topic '{state.raw_query}'. "
                    "Try broadening the query or removing quotes/jargon."
                )
                return state
            if len(candidates) == MAX_CANDIDATES:
                state.warn(
                    f"topic search returned the max of {MAX_CANDIDATES} candidates; "
                    "there may be more relevant papers not shown"
                )
    except arxiv_client.ArxivError as exc:
        state.fail(f"arXiv API error: {exc}")
        return state

    state.log(NODE_NAME, f"{len(state.candidates)} candidate(s)")
    return state
