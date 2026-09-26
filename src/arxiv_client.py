"""
Wrapper around the official arXiv API (Atom feed, no scraping).
Docs: https://info.arxiv.org/help/api/user-manual.html
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .state import PaperMetadata

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
BASE_URL = "http://export.arxiv.org/api/query"

ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")


class ArxivError(RuntimeError):
    pass


def extract_arxiv_id(text: str) -> str | None:
    """Pull a bare arXiv id out of an id, a URL, or free text. None if absent."""
    m = ID_RE.search(text)
    return m.group(1) if m else None


def _parse_entry(entry: ET.Element) -> PaperMetadata:
    def txt(tag: str) -> str:
        el = entry.find(f"atom:{tag}", ATOM_NS)
        return (el.text or "").strip() if el is not None else ""

    raw_id_url = txt("id")  # e.g. http://arxiv.org/abs/2401.12345v2
    arxiv_id = extract_arxiv_id(raw_id_url) or raw_id_url

    authors = [
        (a.find("atom:name", ATOM_NS).text or "").strip()
        for a in entry.findall("atom:author", ATOM_NS)
        if a.find("atom:name", ATOM_NS) is not None
    ]
    categories = [
        c.attrib.get("term", "")
        for c in entry.findall("atom:category", ATOM_NS)
        if c.attrib.get("term")
    ]

    pdf_url = ""
    for link in entry.findall("atom:link", ATOM_NS):
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href", "")
    if not pdf_url:
        # fall back to the conventional PDF URL pattern
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    abs_url = f"https://arxiv.org/abs/{arxiv_id}"

    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=re.sub(r"\s+", " ", txt("title")).strip(),
        authors=authors,
        abstract=re.sub(r"\s+", " ", txt("summary")).strip(),
        published=txt("published"),
        updated=txt("updated"),
        categories=categories,
        abs_url=abs_url,
        pdf_url=pdf_url,
    )


def _query(params: dict, retries: int = 3, backoff: float = 2.0) -> ET.Element:
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=20)
            resp.raise_for_status()
            return ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as exc:
            last_exc = exc
            time.sleep(backoff * (attempt + 1))
    raise ArxivError(f"arXiv API request failed after {retries} attempts: {last_exc}")


def fetch_by_id(arxiv_id: str) -> PaperMetadata | None:
    root = _query({"id_list": arxiv_id})
    entries = root.findall("atom:entry", ATOM_NS)
    if not entries:
        return None
    return _parse_entry(entries[0])


def search_by_topic(query: str, max_results: int = 8) -> list[PaperMetadata]:
    # sort by relevance; arXiv's own ranking is a reasonable first pass,
    # we re-rank with embeddings on top of this in selection_ranking.py
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    root = _query(params)
    entries = root.findall("atom:entry", ATOM_NS)
    return [_parse_entry(e) for e in entries]
