from __future__ import annotations

import os
import tempfile

from .. import pdf_parser
from ..state import AgentState, ParsedPaper

NODE_NAME = "fetch_parse"


def fetch_parse_node(state: AgentState) -> AgentState:
    paper = state.selected_paper
    if paper is None:
        state.fail("fetch_parse reached with no selected paper")
        return state

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, f"{paper.arxiv_id}.pdf")
        try:
            pdf_parser.download_pdf(paper.pdf_url, pdf_path)
        except Exception as exc:
            # Can't get the PDF at all -> degrade to abstract-only rather
            # than failing the whole run. The briefing/QA will be
            # noticeably thinner, but the user still gets something, and
            # the caveat is surfaced (see summarize_node / briefing.caveats).
            state.warn(f"could not download PDF ({exc}); falling back to abstract-only mode")
            state.parsed = ParsedPaper(
                full_text=paper.abstract,
                sections=[],
                num_pages=0,
                parse_quality="abstract_only",
                parse_notes=[f"PDF download failed: {exc}"],
            )
            state.log(NODE_NAME, "abstract_only (download failed)")
            return state

        try:
            parsed = pdf_parser.parse_pdf(pdf_path)
        except pdf_parser.PdfParseError as exc:
            state.warn(f"PDF parsing failed ({exc}); falling back to abstract-only mode")
            parsed = ParsedPaper(
                full_text=paper.abstract,
                sections=[],
                num_pages=0,
                parse_quality="abstract_only",
                parse_notes=[f"PDF parse failed: {exc}"],
            )

    state.parsed = parsed
    if parsed.parse_quality != "clean":
        state.warn(f"PDF parse quality: {parsed.parse_quality} ({'; '.join(parsed.parse_notes)})")
    state.log(NODE_NAME, f"quality={parsed.parse_quality}, pages={parsed.num_pages}")
    return state
