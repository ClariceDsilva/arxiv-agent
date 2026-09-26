from __future__ import annotations

import json
from dataclasses import asdict

from .state import Briefing


def briefing_to_markdown(b: Briefing) -> str:
    lines = [
        f"# {b.title}",
        "",
        f"**arXiv ID:** {b.arxiv_id} | **Published:** {b.published} | **Link:** {b.link}",
        f"**Authors:** {', '.join(b.authors)}",
        "",
        "## Why this paper matters",
        b.summary,
        "",
        "## Problem Statement",
        b.problem_statement,
        "",
        "## Method / Approach",
        *[f"- {item}" for item in b.method],
        "",
        "## Key Results / Claims",
        *[f"- {item}" for item in b.key_results],
        "",
        "## Limitations",
        *[f"- {item}" for item in b.limitations],
        "",
        "## Suggested Follow-up Questions",
        *[f"- {q}" for q in b.suggested_questions],
    ]
    if b.caveats:
        lines += ["", "## Caveats about this briefing", *[f"- {c}" for c in b.caveats]]
    return "\n".join(lines) + "\n"


def briefing_to_json(b: Briefing) -> str:
    return json.dumps(asdict(b), indent=2)
