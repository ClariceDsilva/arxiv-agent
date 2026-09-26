"""Test state serialization and state transitions."""
import json
import tempfile
from pathlib import Path

from src.state import (
    AgentState,
    Briefing,
    Chunk,
    Intent,
    ParsedPaper,
    PaperMetadata,
    RunStatus,
    Section,
)


def test_state_to_dict():
    state = AgentState(raw_query="test", intent=Intent.TOPIC_SEARCH)
    d = state.to_dict()
    assert d["raw_query"] == "test"
    assert d["intent"] == "topic_search"
    assert d["status"] == "ok"


def test_state_serialization_roundtrip():
    # Build a complex state
    paper = PaperMetadata(
        arxiv_id="2401.12345",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="This is a test",
        published="2024-01-01",
        updated="2024-01-02",
        categories=["cs.AI", "cs.LG"],
        abs_url="https://arxiv.org/abs/2401.12345",
        pdf_url="https://arxiv.org/pdf/2401.12345",
    )
    state = AgentState(raw_query="test query", intent=Intent.SPECIFIC_PAPER)
    state.selected_paper = paper
    state.parsed = ParsedPaper(
        full_text="Hello world",
        sections=[Section(heading="Intro", text="Introduction text", start_page=0)],
        num_pages=10,
        parse_quality="clean",
    )
    state.chunks = [
        Chunk(chunk_id="c1", text="chunk text", section="Intro", page=0, order=0)
    ]
    state.briefing = Briefing(
        arxiv_id="2401.12345",
        title="Test Paper",
        authors=["Alice"],
        published="2024-01-01",
        link="https://arxiv.org/abs/2401.12345",
        summary="Test summary",
        problem_statement="Test problem",
        method=["method 1"],
        key_results=["result 1"],
        limitations=["limitation 1"],
        suggested_questions=["question 1"],
    )
    state.warn("test warning")
    state.log("test_node", "test note")

    # Save and load
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "state.json"
        state.save(path)
        assert path.exists()

        loaded = AgentState.load(path)
        assert loaded.raw_query == state.raw_query
        assert loaded.intent == state.intent
        assert loaded.selected_paper.arxiv_id == "2401.12345"
        assert loaded.parsed.num_pages == 10
        assert len(loaded.chunks) == 1
        assert loaded.briefing.title == "Test Paper"
        assert "test warning" in loaded.warnings
        assert "test_node" in str(loaded.trace)


def test_state_warn_sets_degraded():
    state = AgentState()
    assert state.status == RunStatus.OK
    state.warn("something odd")
    assert state.status == RunStatus.DEGRADED
    assert "something odd" in state.warnings


def test_state_fail_sets_failed():
    state = AgentState()
    assert state.status == RunStatus.OK
    state.fail("critical error")
    assert state.status == RunStatus.FAILED
    assert "critical error" in state.errors
