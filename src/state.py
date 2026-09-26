"""
Shared state for the arXiv digest/QA agent.

Everything nodes in the graph read or write lives on AgentState. It is a
plain dataclass (not a framework object) so it can be:
  - passed around in-memory during a single process run, and
  - serialized to JSON and written to disk, so a later process (e.g. a
    fresh CLI invocation for QA-only mode) can rehydrate it without
    re-running the whole pipeline.

See README.md, "State: in-memory vs. persisted" for the reasoning.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Intent(str, Enum):
    SPECIFIC_PAPER = "specific_paper"
    TOPIC_SEARCH = "topic_search"
    UNKNOWN = "unknown"


class RunStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"   # ran, but with a graceful fallback (see warnings)
    FAILED = "failed"


@dataclass
class PaperMetadata:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    updated: str
    categories: list[str]
    abs_url: str
    pdf_url: str
    # similarity score to the user's query, when this came from a topic
    # search (used for ranking / selection). None for direct ID lookups.
    relevance_score: Optional[float] = None


@dataclass
class Section:
    heading: str
    text: str
    start_page: int


@dataclass
class ParsedPaper:
    full_text: str
    sections: list[Section]
    num_pages: int
    parse_quality: str  # "clean" | "partial" | "abstract_only"
    parse_notes: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    chunk_id: str
    text: str
    section: str
    page: int
    order: int


@dataclass
class Briefing:
    arxiv_id: str
    title: str
    authors: list[str]
    published: str
    link: str
    summary: str
    problem_statement: str
    method: list[str]
    key_results: list[str]
    limitations: list[str]
    suggested_questions: list[str]
    caveats: list[str] = field(default_factory=list)  # e.g. "based on abstract only"


@dataclass
class QATurn:
    question: str
    answer: str
    grounded: bool
    retrieved_chunk_ids: list[str]
    max_similarity: float


@dataclass
class AgentState:
    # --- input ---
    raw_query: str = ""
    intent: Intent = Intent.UNKNOWN
    requested_arxiv_id: Optional[str] = None

    # --- retrieval ---
    candidates: list[PaperMetadata] = field(default_factory=list)
    selected_paper: Optional[PaperMetadata] = None

    # --- parsing ---
    parsed: Optional[ParsedPaper] = None

    # --- chunking / vector store ---
    chunks: list[Chunk] = field(default_factory=list)
    vector_collection_name: Optional[str] = None
    vector_store_path: Optional[str] = None

    # --- output ---
    briefing: Optional[Briefing] = None

    # --- QA ---
    qa_history: list[QATurn] = field(default_factory=list)

    # --- run bookkeeping ---
    status: RunStatus = RunStatus.OK
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)  # node names in execution order
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def log(self, node_name: str, note: str = "") -> None:
        self.trace.append(f"{node_name}{': ' + note if note else ''}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        if self.status == RunStatus.OK:
            self.status = RunStatus.DEGRADED

    def fail(self, msg: str) -> None:
        self.errors.append(msg)
        self.status = RunStatus.FAILED

    # ---- persistence -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> "AgentState":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_state(data)


def _dict_to_state(data: dict[str, Any]) -> AgentState:
    """Rehydrate an AgentState from its JSON dict form (see .save/.load)."""
    state = AgentState()
    state.raw_query = data.get("raw_query", "")
    state.intent = Intent(data.get("intent", Intent.UNKNOWN))
    state.requested_arxiv_id = data.get("requested_arxiv_id")
    state.candidates = [PaperMetadata(**c) for c in data.get("candidates", [])]
    sp = data.get("selected_paper")
    state.selected_paper = PaperMetadata(**sp) if sp else None
    parsed = data.get("parsed")
    if parsed:
        sections = [Section(**s) for s in parsed.get("sections", [])]
        state.parsed = ParsedPaper(
            full_text=parsed.get("full_text", ""),
            sections=sections,
            num_pages=parsed.get("num_pages", 0),
            parse_quality=parsed.get("parse_quality", "clean"),
            parse_notes=parsed.get("parse_notes", []),
        )
    state.chunks = [Chunk(**c) for c in data.get("chunks", [])]
    state.vector_collection_name = data.get("vector_collection_name")
    state.vector_store_path = data.get("vector_store_path")
    briefing = data.get("briefing")
    state.briefing = Briefing(**briefing) if briefing else None
    state.qa_history = [QATurn(**q) for q in data.get("qa_history", [])]
    state.status = RunStatus(data.get("status", RunStatus.OK))
    state.warnings = data.get("warnings", [])
    state.errors = data.get("errors", [])
    state.trace = data.get("trace", [])
    state.created_at = data.get("created_at", state.created_at)
    return state
