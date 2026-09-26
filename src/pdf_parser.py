"""
Download an arXiv PDF and extract text + a rough section structure.

Failure modes handled explicitly (see README "Design Decisions"):
  - scanned / image-only PDFs (little or no extractable text)
  - broken / truncated downloads
  - very large papers (page cap, so we don't try to embed a 300-page
    thesis-length PDF into one run)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from .state import ParsedPaper, Section

MAX_PAGES = 60  # generous for a typical paper; protects against outliers
MIN_CHARS_PER_PAGE_FOR_CLEAN = 200  # below this, page is probably scanned/garbled

# Common top-level headings in CS/ML papers. Matched case-insensitively
# against short standalone lines (heuristic, not a full layout parser).
HEADING_PATTERNS = [
    r"abstract",
    r"introduction",
    r"related work",
    r"background",
    r"method(ology)?",
    r"approach",
    r"model",
    r"experiments?",
    r"evaluation",
    r"results?",
    r"discussion",
    r"limitations?",
    r"conclusion",
    r"future work",
    r"references",
    r"appendix",
    r"acknowledge?ments?",
]
HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?(" + "|".join(HEADING_PATTERNS) + r")\s*$",
    re.IGNORECASE,
)


class PdfParseError(RuntimeError):
    pass


def download_pdf(pdf_url: str, dest_path: str, timeout: int = 30) -> None:
    resp = requests.get(pdf_url, timeout=timeout, stream=True)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
        # arXiv sometimes 200s an HTML "unavailable" page instead of a PDF
        raise PdfParseError(f"expected a PDF, got content-type={content_type!r}")
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            f.write(chunk)


def _split_into_sections(pages_text: list[str]) -> list[Section]:
    sections: list[Section] = []
    current_heading = "Front Matter"
    current_lines: list[str] = []
    current_start_page = 0

    def flush(end_page: int) -> None:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append(Section(heading=current_heading, text=text, start_page=current_start_page))

    for page_idx, page_text in enumerate(pages_text):
        for line in page_text.splitlines():
            stripped = line.strip()
            m = HEADING_RE.match(stripped) if 0 < len(stripped) < 60 else None
            if m:
                flush(page_idx)
                current_heading = stripped.title()
                current_lines = []
                current_start_page = page_idx
            else:
                current_lines.append(line)
    flush(len(pages_text) - 1)
    return sections


def parse_pdf(path: str) -> ParsedPaper:
    """Extract text with PyMuPDF and split into rough sections.

    Degrades gracefully: if the PDF looks scanned (near-zero extractable
    text) we still return a ParsedPaper, just with parse_quality set so
    downstream nodes know to fall back to abstract-only summarization.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise PdfParseError("PyMuPDF (pymupdf) is not installed") from exc

    notes: list[str] = []
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PdfParseError(f"could not open PDF: {exc}") from exc

    total_pages = doc.page_count
    n_pages = min(total_pages, MAX_PAGES)
    if total_pages > MAX_PAGES:
        notes.append(f"paper has {total_pages} pages; truncated to first {MAX_PAGES} for processing")

    pages_text: list[str] = []
    for i in range(n_pages):
        try:
            page = doc.load_page(i)
            pages_text.append(page.get_text("text"))
        except Exception as exc:  # a single bad page shouldn't kill the whole parse
            notes.append(f"page {i}: extraction error ({exc})")
            pages_text.append("")
    doc.close()

    full_text = "\n".join(pages_text)
    non_empty_pages = [p for p in pages_text if len(p.strip()) > 0]
    avg_chars_per_page = (len(full_text) / n_pages) if n_pages else 0

    if len(full_text.strip()) < 50:
        quality = "abstract_only"
        notes.append("almost no extractable text found; likely a scanned/image-only PDF")
    elif avg_chars_per_page < MIN_CHARS_PER_PAGE_FOR_CLEAN or len(non_empty_pages) < n_pages * 0.5:
        quality = "partial"
        notes.append("low text density detected; extraction may be incomplete (scanned pages, complex layout, or figures-heavy)")
    else:
        quality = "clean"

    sections = _split_into_sections(pages_text) if quality != "abstract_only" else []

    return ParsedPaper(
        full_text=full_text,
        sections=sections,
        num_pages=total_pages,
        parse_quality=quality,
        parse_notes=notes,
    )
