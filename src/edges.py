"""
Conditional edge functions that route between nodes based on state.

Each function takes (state) -> next_node_name and encodes a simple
decision rule. By keeping these separate, the flow is transparent and
easy to modify without touching node code.
"""
from __future__ import annotations

from .graph import END
from .state import AgentState, Intent, RunStatus


def route_after_understanding(state: AgentState) -> str:
    """After query_understanding, go to arxiv_retrieval unless the
    intent classification failed.
    """
    if state.status == RunStatus.FAILED:
        return END
    return "arxiv_retrieval"


def route_after_retrieval(state: AgentState) -> str:
    """After retrieval, rank candidates (for topic search) or skip
    directly to PDF fetch (for specific-paper lookups).
    """
    if state.status == RunStatus.FAILED:
        return END
    return "selection_ranking" if state.intent == Intent.TOPIC_SEARCH else "fetch_parse"


def route_after_ranking(state: AgentState) -> str:
    """After ranking, move to PDF fetch."""
    if state.status == RunStatus.FAILED:
        return END
    return "fetch_parse"


def route_after_fetch_parse(state: AgentState) -> str:
    if state.status == RunStatus.FAILED:
        return END
    return "chunk_embed"


def route_after_chunk_embed(state: AgentState) -> str:
    if state.status == RunStatus.FAILED:
        return END
    return "summarize"


def route_after_summarize(state: AgentState) -> str:
    """After summarization, exit the graph (QA happens in a loop outside)."""
    return END
