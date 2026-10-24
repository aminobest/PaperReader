"""US-04/US-14 — verify a contextual evidence passage verbatim in a paper and locate it.

Matching is done on a normalised character stream (NFKC, lower-case, alphanumerics only) so that
whitespace, punctuation, line-break hyphenation ("repre-\\nsentation") and ligatures ("ﬁ") never
cause false negatives, while any change of actual words still fails.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in text if ch.isalnum())


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    line: str  # block/line key: words sharing it are on one visual line


@dataclass
class PageIndex:
    page: int  # 1-based
    words: list[Word]
    chars: str = ""
    owners: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        chars: list[str] = []
        owners: list[int] = []
        for i, w in enumerate(self.words):
            for ch in normalize(w.text):
                chars.append(ch)
                owners.append(i)
        self.chars = "".join(chars)
        self.owners = owners

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class PaperIndex:
    paper_id: str
    label: str  # "P1", "P2" … as shown to the LLM
    title: str
    pages: list[PageIndex]


@dataclass
class Located:
    paper_id: str
    page: int
    text: str  # exact words from the PDF
    rects: list[list[float]]  # [x0, y0, x1, y1] normalised 0..1, one per visual line


class QuoteError(ValueError):
    pass


def check_shape(quote: str) -> str:
    """Return the normalised quote or raise QuoteError for quotes that can never be evidence."""
    if "..." in quote or "…" in quote:
        raise QuoteError("contains an ellipsis; quotes must be one contiguous passage")
    norm = normalize(quote)
    if not norm:
        raise QuoteError("empty quote")
    return norm


def _line_rects(words: list[Word]) -> list[list[float]]:
    lines: dict[str, list[float]] = {}
    for w in words:
        r = lines.get(w.line)
        if r is None:
            lines[w.line] = [w.x0, w.y0, w.x1, w.y1]
        else:
            r[0], r[1], r[2], r[3] = min(r[0], w.x0), min(r[1], w.y0), max(r[2], w.x1), max(r[3], w.y1)
    return [[round(v, 5) for v in r] for r in lines.values()]


def locate_in_page(norm_quote: str, page: PageIndex) -> list[Word] | None:
    pos = page.chars.find(norm_quote)
    if pos < 0:
        return None
    idx = sorted(set(page.owners[pos : pos + len(norm_quote)]))
    return [page.words[i] for i in idx]


def locate(quote: str, paper: PaperIndex, page_hint: int | None = None) -> Located:
    """Find `quote` in `paper` (hinted page first). Raises QuoteError when absent (AT-04.1/04.2)."""
    norm = check_shape(quote)
    pages = sorted(paper.pages, key=lambda p: (p.page != page_hint, p.page))
    for page in pages:
        words = locate_in_page(norm, page)
        if words:
            return Located(
                paper_id=paper.paper_id,
                page=page.page,
                text=" ".join(w.text for w in words),
                rects=_line_rects(words),
            )
    raise QuoteError(f"not found verbatim in {paper.label}")
