# US-05 — Mind-map generation

As a reader, I want the AI to build a mind map for one paper or a set of papers, from the big picture down to tiny details, so that I understand the paper quickly even without background.

## Acceptance tests
- **AT-05.1** Given papers, when the prompt is rendered then it uses the editable template and contains every page labelled `[P<n> p.<page>]` — Levels: unit
- **AT-05.2** Given LLM JSON, then it becomes a tree (root, branches, details) with kinds, quotes and cross-links resolved by node id; malformed JSON triggers one corrective retry — Levels: unit, integration
- **AT-05.3** Given a session with papers, when I generate a map for one paper or a selection, then a job runs and the map becomes `ready` (or `failed` with the error) — Levels: integration, system

## Main files
- `backend/app/domain/mindmap.py`
- `backend/app/application/map_service.py`
- `backend/app/domain/prompts.py`
