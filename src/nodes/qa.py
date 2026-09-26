from __future__ import annotations

from ..llm.base import LLMClient
from ..state import AgentState, QATurn
from ..vectorstore.chroma_store import ChromaChunkStore

NODE_NAME = "qa"

# Below this cosine similarity, we don't trust any retrieved chunk to be
# actually relevant, so we skip the LLM call entirely and say so. This is
# the main lever against hallucination: the model never sees a
# question it has no grounded material for.
MIN_SIMILARITY = 0.22
TOP_K = 5

SYSTEM_PROMPT = """You answer questions about a specific academic paper using ONLY the \
excerpts provided below. Rules:
- If the excerpts answer the question, answer concisely and mention which section(s) \
support it.
- If the excerpts do NOT contain enough information to answer, say explicitly that the \
paper (or at least the retrieved portion of it) does not appear to address this, rather \
than guessing or using outside knowledge.
- Never state a number, result, or claim that isn't present in the excerpts."""

NOT_GROUNDED_MESSAGE = (
    "I couldn't find anything in the paper closely related to that question, "
    "so I don't want to guess. Try rephrasing, or ask about a topic the paper "
    "actually covers (see the briefing's suggested questions)."
)


def make_qa_node(llm: LLMClient, store: ChromaChunkStore):
    """Returns a function (state, question) -> state, appending one QATurn.

    This is used both as a graph node (continue_on_failure=True, so one
    bad question doesn't kill the session) and directly from the CLI's
    interactive loop - see main.py and README "State: in-memory vs.
    persisted" for why QA is modeled as a repeatedly-invoked node rather
    than an unrolled loop inside the graph.
    """

    def answer(state: AgentState, question: str) -> AgentState:
        paper = state.selected_paper
        if paper is None or not state.chunks:
            state.qa_history.append(
                QATurn(question=question, answer=NOT_GROUNDED_MESSAGE, grounded=False,
                       retrieved_chunk_ids=[], max_similarity=0.0)
            )
            state.warn("QA attempted with no indexed chunks")
            return state

        try:
            retrieved = store.query(paper.arxiv_id, question, top_k=TOP_K)
        except Exception as exc:
            state.qa_history.append(
                QATurn(question=question, answer=f"Retrieval failed: {exc}", grounded=False,
                       retrieved_chunk_ids=[], max_similarity=0.0)
            )
            state.warn(f"vector store query failed: {exc}")
            return state

        max_sim = max((r.similarity for r in retrieved), default=0.0)
        if not retrieved or max_sim < MIN_SIMILARITY:
            state.qa_history.append(
                QATurn(question=question, answer=NOT_GROUNDED_MESSAGE, grounded=False,
                       retrieved_chunk_ids=[r.chunk.chunk_id for r in retrieved],
                       max_similarity=round(max_sim, 4))
            )
            state.log(NODE_NAME, f"not grounded (max_sim={max_sim:.3f})")
            return state

        excerpts = "\n\n".join(
            f"[{r.chunk.section} | similarity={r.similarity:.2f}]\n{r.chunk.text}"
            for r in retrieved
        )
        user_prompt = f"Paper: {paper.title}\n\nExcerpts:\n{excerpts}\n\nQuestion: {question}"

        try:
            answer_text = llm.generate(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            answer_text = f"(LLM call failed: {exc}) Closest relevant excerpt was from '{retrieved[0].chunk.section}'."
            state.warn(f"QA LLM call failed: {exc}")

        state.qa_history.append(
            QATurn(
                question=question,
                answer=answer_text.strip(),
                grounded=True,
                retrieved_chunk_ids=[r.chunk.chunk_id for r in retrieved],
                max_similarity=round(max_sim, 4),
            )
        )
        state.log(NODE_NAME, f"grounded answer (max_sim={max_sim:.3f})")
        return state

    return answer

