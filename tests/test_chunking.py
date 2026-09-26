"""Test the section-aware chunking strategy."""
from src.chunking import chunk_paper
from src.state import ParsedPaper, Section


def test_chunk_paper_single_section():
    """Test chunking when there's only one section."""
    parsed = ParsedPaper(
        full_text="This is a very long text. " * 100,  # ~2500 characters
        sections=[Section(heading="Full Text", text="This is a very long text. " * 100, start_page=0)],
        num_pages=10,
        parse_quality="clean",
    )
    chunks = chunk_paper(parsed, "2401.12345")

    assert len(chunks) > 1
    assert all(c.chunk_id.startswith("2401.12345::") for c in chunks)
    assert all(c.section == "Full Text" for c in chunks)
    # Chunks should have some overlap
    assert chunks[0].order < chunks[-1].order


def test_chunk_paper_multiple_sections():
    """Test chunking with multiple detected sections."""
    sections = [
        Section(heading="Introduction", text="Intro text. " * 50, start_page=0),
        Section(heading="Method", text="Method text. " * 50, start_page=2),
        Section(heading="Results", text="Results text. " * 50, start_page=5),
    ]
    parsed = ParsedPaper(
        full_text="".join(s.text for s in sections),
        sections=sections,
        num_pages=10,
        parse_quality="clean",
    )
    chunks = chunk_paper(parsed, "2401.99999")

    assert len(chunks) >= 3  # At least one chunk per section
    # Check that section metadata is preserved
    intro_chunks = [c for c in chunks if c.section == "Introduction"]
    method_chunks = [c for c in chunks if c.section == "Method"]
    results_chunks = [c for c in chunks if c.section == "Results"]
    assert len(intro_chunks) >= 1
    assert len(method_chunks) >= 1
    assert len(results_chunks) >= 1


def test_chunk_paper_empty_text():
    """Test chunking when there's no text (e.g., abstract-only)."""
    parsed = ParsedPaper(
        full_text="",
        sections=[],
        num_pages=0,
        parse_quality="abstract_only",
    )
    chunks = chunk_paper(parsed, "2401.11111")

    assert len(chunks) == 0


def test_chunk_paper_tiny_text():
    """Test chunking when text is smaller than chunk size."""
    parsed = ParsedPaper(
        full_text="Short text.",
        sections=[Section(heading="All", text="Short text.", start_page=0)],
        num_pages=1,
        parse_quality="clean",
    )
    chunks = chunk_paper(parsed, "2401.22222")

    assert len(chunks) == 1
    assert chunks[0].text == "Short text."


def test_chunk_order_increases():
    """Test that chunk order is monotonically increasing."""
    parsed = ParsedPaper(
        full_text="Text block. " * 200,
        sections=[Section(heading="All", text="Text block. " * 200, start_page=0)],
        num_pages=5,
        parse_quality="clean",
    )
    chunks = chunk_paper(parsed, "2401.33333")

    orders = [c.order for c in chunks]
    assert orders == sorted(orders), "chunk orders should be monotonically increasing"
    assert orders[0] == 0
    assert orders[-1] == len(chunks) - 1
