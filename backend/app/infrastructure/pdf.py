"""US-03 — PDF text extraction with word positions (normalised to 0..1) using PyMuPDF."""

from __future__ import annotations

import fitz  # PyMuPDF


class NotAPDF(ValueError):
    pass


def extract(data: bytes) -> dict:
    """Return {"meta_title", "pages": [{"page", "words": [[x0,y0,x1,y1,text,line]]}]}."""
    if not data.startswith(b"%PDF"):
        raise NotAPDF("file is not a PDF")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — any parser failure means unusable upload
        raise NotAPDF(f"unreadable PDF: {exc}") from exc
    pages = []
    with doc:
        for pno, page in enumerate(doc, start=1):
            w, h = page.rect.width or 1, page.rect.height or 1
            words = []
            for x0, y0, x1, y1, text, block, line, _ in page.get_text("words", sort=True):
                words.append([
                    round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5),
                    text, f"{block}.{line}",
                ])
            pages.append({"page": pno, "words": words})
        meta_title = (doc.metadata or {}).get("title")
        heading = _first_page_heading(doc[0]) if doc.page_count else ""
    return {"meta_title": meta_title, "heading": heading, "pages": pages}


def _first_page_heading(page) -> str:
    """US-03 AT-03.5 — text set in the largest font on the top half of page 1 (the visible title)."""
    spans = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            if abs(line.get("dir", (1, 0))[1]) > 0.01:  # skip rotated text (e.g. the arXiv margin stamp)
                continue
            for s in line.get("spans", []):
                if s["text"].strip() and s["bbox"][1] < page.rect.height / 2:
                    spans.append((round(s["size"], 1), s["text"].strip()))
    if not spans:
        return ""
    biggest = max(size for size, _ in spans)
    return " ".join(t for size, t in spans if size == biggest)[:200]
