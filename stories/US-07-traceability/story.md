# US-07 — Bidirectional map ↔ paper traceability

As a reader, I want selections in the map and the paper to light up each other, so that I always see the evidence behind an idea and the ideas behind a passage.

## Acceptance tests
- **AT-07.1** Given a node, when I select it then all its quotes are highlighted in the paper and the viewer scrolls to the first — Levels: system
- **AT-07.2** Given a text selection in the paper, then nodes whose quotes overlap it are highlighted in the map — Levels: unit, system
- **AT-07.3** Given a quote highlight in the paper, when I tap it then its node(s) are selected — Levels: system
- **AT-07.4** Given the paper toolbar, I can toggle the layers: map quotes, chat quotes, my annotations — Levels: system
- **AT-07.5** Given a map payload, then each quote carries node/message id, paper id, page and rects normalised to 0..1 — Levels: integration

## Main files
- `frontend/js/workspace.js`
- `frontend/js/geometry.mjs`
- `backend/app/api/maps.py`
