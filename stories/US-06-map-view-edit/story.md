# US-06 — Mind-map view and editing

As a reader, I want to navigate and edit the map freely and let the AI go deeper or re-find evidence, so that the map becomes my own understanding.

## Acceptance tests
- **AT-06.1** Given a map, I can add a child, edit title/explanation/kind, delete a subtree, and move a node under another parent (cycles rejected) — Levels: unit, integration, system
- **AT-06.2** Given two nodes, I can create, relabel and delete a cross-link — Levels: integration
- **AT-06.3** Given a node, when I ask the AI to expand it then grounded child nodes are appended — Levels: integration, system
- **AT-06.4** Given an edited node, when I re-ground it then its quotes are replaced by verified quotes for its new meaning — Levels: integration
- **AT-06.5** Given a map, I can pan, zoom (wheel/pinch), fit, collapse/expand branches and show depth 1..N — Levels: unit, system
- **AT-06.6** Given a map, I can rename and delete it — Levels: integration

## Main files
- `backend/app/api/maps.py`
- `frontend/js/mindmap.js`
- `frontend/js/layout.mjs`
