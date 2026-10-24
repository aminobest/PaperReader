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
    return {"meta_title": meta_title, "pages": pages}
