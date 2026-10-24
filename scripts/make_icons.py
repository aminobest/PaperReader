"""US-12 — renders the home-screen icons (frontend/icons/*.png) with PyMuPDF; no image deps needed."""

import os

import fitz

OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "icons")


def icon(size: int) -> None:
    doc = fitz.open()
    page = doc.new_page(width=size, height=size)
    page.draw_rect(page.rect, color=None, fill=(0.07, 0.09, 0.15))
    c = fitz.Point(size * 0.5, size * 0.5)
    for dx, dy, col in [(-0.28, -0.22, (0.15, 0.39, 0.92)), (0.28, -0.2, (0.09, 0.64, 0.29)),
                        (-0.26, 0.24, (0.86, 0.15, 0.47)), (0.27, 0.25, (0.92, 0.35, 0.05))]:
        p = fitz.Point(size * (0.5 + dx), size * (0.5 + dy))
        page.draw_line(c, p, color=col, width=size * 0.035)
        page.draw_circle(p, size * 0.075, color=None, fill=col)
    page.draw_circle(c, size * 0.14, color=None, fill=(1, 1, 1))
    page.get_pixmap().save(os.path.join(OUT, f"icon-{size}.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in (180, 192, 512):
        icon(s)
