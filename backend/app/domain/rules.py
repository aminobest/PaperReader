"""Pure business rules shared by several stories (each function names its story)."""

from __future__ import annotations

import os
import re

from app.domain.grounding import PaperIndex

PALETTE = ("yellow", "green", "blue", "pink", "orange", "red")  # US-08 annotation colors


class ValidationError(ValueError):
    pass


def clean_name(name: str, what: str = "name", max_len: int = 120) -> str:
    """US-02 AT-02.1 — names are trimmed and must not be blank."""
    name = (name or "").strip()
    if not name:
        raise ValidationError(f"{what} must not be blank")
    return name[:max_len]


def default_paper_title(meta_title: str | None, filename: str, heading: str | None = None) -> str:
    """US-03 AT-03.5 — metadata title if meaningful, else the page-1 heading, else filename without extension."""
    meta_title = (meta_title or "").strip()
    if len(meta_title) >= 4 and not meta_title.lower().endswith((".pdf", ".dvi", ".doc", ".tex")):
        return meta_title[:200]
    heading = " ".join((heading or "").split())
    if len(heading) >= 8 and any(ch.isalpha() for ch in heading):
        return heading[:200]
    stem = os.path.splitext(os.path.basename(filename or "paper.pdf"))[0]
    return (stem.replace("_", " ").strip() or "Untitled paper")[:200]


def validate_annotation(color: str, rects: list) -> None:
    """US-08 AT-08.3 — palette color, 1+ rects of 4 numbers within 0..1."""
    if color not in PALETTE:
        raise ValidationError(f"color must be one of {', '.join(PALETTE)}")
    if not rects:
        raise ValidationError("at least one rectangle is required")
    for r in rects:
        if len(r) != 4 or not all(isinstance(v, (int, float)) and -0.001 <= v <= 1.001 for v in r):
            raise ValidationError("rects must be [x0, y0, x1, y1] normalised to 0..1")
        if r[2] < r[0] or r[3] < r[1]:
            raise ValidationError("rects must have x1>=x0 and y1>=y0")


def note_title(title: str | None, body: str) -> str:
    """US-09 AT-09.3 — explicit title, else first non-empty line of the body."""
    if title and title.strip():
        return title.strip()[:200]
    for line in (body or "").splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:80]
    return "Untitled note"


def papers_block(papers: list[PaperIndex]) -> str:
    """US-05 AT-05.1 — paper text for prompts, each page tagged `[P<n> p.<page>]`."""
    parts = []
    for p in papers:
        parts.append(f"=== {p.label}: {p.title} ===")
        for page in p.pages:
            parts.append(f"[{p.label} p.{page.page}]\n{page.text}")
    return "\n\n".join(parts)


def node_path(titles: list[str]) -> str:
    return " > ".join(titles)


def chat_context(path: list[str] | None, nodes: list[dict], passage: str | None) -> str:
    """US-10 AT-10.4 — the FOCUS block of the chat prompt."""
    lines = []
    for n in nodes:
        lines.append(f"- Node: {n['title']} ({n.get('kind', 'detail')})")
        if n.get("path"):
            lines.append(f"  Path: {n['path']}")
        if n.get("explanation"):
            lines.append(f"  Explanation: {n['explanation']}")
    if passage:
        lines.append(f"- Selected passage: \"{passage.strip()}\"")
    return "\n".join(lines) or "- The paper(s) as a whole"


_CITE = re.compile(r"\[(\d{1,3})\]")


def link_citations(answer: str, kept: dict[int, str]) -> str:
    """US-10 AT-10.2 — rewrite `[n]` to `[[q:<quote_id>]]` for kept quotes; drop markers of dropped ones."""
    def sub(m: re.Match) -> str:
        n = int(m.group(1))
        return f"[[q:{kept[n]}|{n}]]" if n in kept else ""
    return _CITE.sub(sub, answer)


PREF_KEYS = ("layout.desktop", "layout.tablet")  # US-13: layout is remembered per device class
MAX_PREF_BYTES = 2048


def validate_pref(key: str, value_json: str) -> None:
    """US-13 AT-13.6 — only known keys; small JSON objects (the client sanitises the content)."""
    if key not in PREF_KEYS:
        raise ValidationError(f"unknown preference {key!r}")
    if len(value_json.encode()) > MAX_PREF_BYTES:
        raise ValidationError("preference too large")
    if not value_json.startswith("{"):
        raise ValidationError("preference must be an object")
