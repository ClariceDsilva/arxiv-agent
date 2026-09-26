from __future__ import annotations

from ..arxiv_client import extract_arxiv_id
from ..state import AgentState, Intent

NODE_NAME = "query_understanding"


def query_understanding_node(state: AgentState) -> AgentState:
    """Deliberately deterministic, no LLM call: whether the input is a
    specific arXiv id/URL is a regex question, not a reasoning one, and
    keeping it rule-based means this stage never fails, never costs a
    quota unit, and is trivially unit-testable.
    """
    query = state.raw_query.strip()
    arxiv_id = extract_arxiv_id(query)

    if arxiv_id and (len(query) < 40 or "arxiv.org" in query.lower()):
        # short input that's basically just an id/URL -> specific paper
        state.intent = Intent.SPECIFIC_PAPER
        state.requested_arxiv_id = arxiv_id
    elif arxiv_id:
        # an id embedded in a longer sentence: still treat as specific
        state.intent = Intent.SPECIFIC_PAPER
        state.requested_arxiv_id = arxiv_id
    elif query:
        state.intent = Intent.TOPIC_SEARCH
    else:
        state.intent = Intent.UNKNOWN
        state.fail("empty query: provide a topic or an arXiv id/URL")

    state.log(NODE_NAME, f"intent={state.intent.value}")
    return state
