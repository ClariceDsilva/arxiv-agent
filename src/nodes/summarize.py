from __future__ import annotations

import json
import re

from ..briefing import briefing_to_markdown
from ..llm.base import LLMClient
from ..state import AgentState, Briefing

NODE_NAME = "summarize"

SYSTEM_PROMPT = """You are a research assistant producing an executive briefing on an \
academic paper for a busy engineer deciding whether to read it in full. Be precise, \
avoid hype, and never invent results, numbers, or claims that are not supported by the \
provided text. If the provided text is limited (e.g. only an abstract), say so plainly \
in the limitations rather than padding with speculation.

Respond with ONLY a JSON object (no markdown fences, no commentary) matching exactly \
this schema:
{
  "summary": "1 paragraph, plain English, on why this paper matters",
  "problem_statement": "1-3 sentences on the problem being addressed",
  "method": ["bullet point", "..."],
  "key_results": ["bullet point", "..."],
  "limitations": ["bullet point", "... (always include at least one; if the paper doesn't state limitations, note that explicitly)"],
  "suggested_questions": ["question a curious reader might ask next", "..."]
}"""

MAX_CONTEXT_CHARS = 18000  # keep prompts small & within free-tier TPM limits


def _build_context(state: AgentState) -> str:
    paper = state.selected_paper
    parsed = state.parsed
    header = (
        f"Title: {paper.title}\n"
        f"Authors: {', '.join(paper.authors)}\n"
        f"Categories: {', '.join(paper.categories)}\n"
        f"Abstract: {paper.abstract}\n"
    )
    if parsed and parsed.parse_quality != "abstract_only" and parsed.full_text:
        body = parsed.full_text[:MAX_CONTEXT_CHARS]
        return f"{header}\nFull text (may be truncated):\n{body}"
    return header + "\n(Only the abstract was available - the full PDF could not be read.)"


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _fallback_briefing(state: AgentState) -> Briefing:
    """Rule-based, no-LLM fallback so a briefing is always produced even
    if the model call fails twice or returns unparseable output.
    """
    paper = state.selected_paper
    return Briefing(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        published=paper.published,
        link=paper.abs_url,
        summary=paper.abstract or "(no abstract available)",
        problem_statement="(could not be determined automatically; see abstract above)",
        method=["(automatic extraction unavailable; consult the paper)"],
        key_results=["(automatic extraction unavailable; consult the paper)"],
        limitations=["Briefing generation failed; this is the raw abstract only."],
        suggested_questions=[f"What problem does '{paper.title}' actually solve?"],
        caveats=["LLM summarization failed or was unavailable; showing a minimal fallback briefing."],
    )


def make_summarize_node(llm: LLMClient):
    def summarize_node(state: AgentState) -> AgentState:
        if state.selected_paper is None:
            state.fail("summarize reached with no selected paper")
            return state

        context = _build_context(state)
        raw = None
        parsed_json = None
        last_error = None

        for attempt in range(2):
            try:
                raw = llm.generate(SYSTEM_PROMPT, context, json_mode=True)
                parsed_json = json.loads(_strip_json_fences(raw))
                break
            except Exception as exc:  # covers JSON errors and provider errors alike
                last_error = exc
                context = context[: len(context) // 2]  # shrink & retry once

        if parsed_json is None:
            state.warn(f"LLM summarization failed after retries ({last_error}); using fallback briefing")
            state.briefing = _fallback_briefing(state)
            state.log(NODE_NAME, "fallback briefing used")
            return state

        paper = state.selected_paper
        caveats = []
        if state.parsed and state.parsed.parse_quality != "clean":
            caveats.append(
                f"PDF parse quality was '{state.parsed.parse_quality}': "
                f"{'; '.join(state.parsed.parse_notes) or 'see logs'}"
            )
        caveats.extend(state.warnings)

        try:
            state.briefing = Briefing(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=paper.authors,
                published=paper.published,
                link=paper.abs_url,
                summary=parsed_json.get("summary", ""),
                problem_statement=parsed_json.get("problem_statement", ""),
                method=list(parsed_json.get("method", [])),
                key_results=list(parsed_json.get("key_results", [])),
                limitations=list(parsed_json.get("limitations", [])) or ["Not stated by the model."],
                suggested_questions=list(parsed_json.get("suggested_questions", [])),
                caveats=caveats,
            )
        except Exception as exc:
            state.warn(f"malformed briefing JSON from LLM ({exc}); using fallback briefing")
            state.briefing = _fallback_briefing(state)

        state.log(NODE_NAME, "briefing generated")
        return state

    return summarize_node


def render_briefing(state: AgentState) -> str:
    assert state.briefing is not None
    return briefing_to_markdown(state.briefing)
