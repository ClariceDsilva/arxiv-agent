"""
Section-aware chunking.

Strategy: chunk *within* each detected section rather than across the
whole document blindly. This keeps a chunk's "section" metadata
meaningful (useful for citing "this claim is from the Results section"
in QA answers) and avoids splitting a sentence in the Method section
together with the start of Results into one incoherent chunk.

Falls back to a single pseudo-section ("Full Text") when section
detection failed (parse_quality == "abstract_only" or no sections
found), so the pipeline still produces usable chunks.
"""
from __future__ import annotations

from .state import Chunk, ParsedPaper, Section

CHUNK_SIZE = 900       # characters, not tokens - simple & model-agnostic
CHUNK_OVERLAP = 150


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # try to end on a sentence/paragraph boundary for readability
        if end < len(text):
            boundary = text.rfind(". ", start + int(size * 0.5), end)
            if boundary != -1:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def chunk_paper(parsed: ParsedPaper, arxiv_id: str) -> list[Chunk]:
    sections: list[Section] = parsed.sections or [
        Section(heading="Full Text", text=parsed.full_text, start_page=0)
    ]

    chunks: list[Chunk] = []
    order = 0
    for section in sections:
        for piece in _chunk_text(section.text):
            chunks.append(
                Chunk(
                    chunk_id=f"{arxiv_id}::{order:04d}",
                    text=piece,
                    section=section.heading,
                    page=section.start_page,
                    order=order,
                )
            )
            order += 1
    return chunks
