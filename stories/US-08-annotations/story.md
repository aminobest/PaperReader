# US-08 — Colored annotations

As a reader, I want to highlight passages in different colors with a comment, like in Acrobat, so that I can mark the paper my way.

## Acceptance tests
- **AT-08.1** Given a text selection, when I pick a color then a highlight with text, rects and color is saved and shown — Levels: integration, system
- **AT-08.2** Given a highlight, I can change its color or comment, or delete it — Levels: integration, system
- **AT-08.3** Given an annotation payload, then color must be in the palette and rects within 0..1, else 422 — Levels: unit, integration

## Main files
- `backend/app/api/annotations.py`
- `frontend/js/pdfview.js`
