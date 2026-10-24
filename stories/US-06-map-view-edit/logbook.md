# US-06 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — fixed (AT-06.5 race)
- What: Depth and branch fold/unfold apply instantly on the client (`layout.mjs foldFlags`, mirror of
  `domain.mindmap.fold_flags`) and are persisted through an ordered write queue; `loadMap` ignores stale responses.
- Why: found by the CR-03 journey — tapping a branch right after changing Depth acted on stale nodes, two map
  reloads raced, the tapped node vanished, and the server could apply the writes out of order (lost unfold).
- Files: frontend/js/workspace.js, frontend/js/layout.mjs.
- Tests: tests/unit/js/frontend.test.mjs (AT-06.5 mirror), 90-journey.spec.js (depth → unfold → tap flow).

## 2026-10-24 — extended (AT-06.7)
- What: adding a node or changing its title/explanation re-derives its evidence with the AI (opt-out checkbox; API `ground`/`reground`). PATCH/POST node responses now include `job`.
- Why: requirements gap — "the paper ... is derived when the map is generated **or part of it is edited**".
- Files: backend/app/api/maps.py, backend/app/domain/mindmap.py (`meaning_changed`), frontend/js/panels.js.
- Tests: test_mindmap.py, test_maps.py, 01-ui.spec.js / 90-journey.spec.js.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
- Design decision: *Depth* is persisted fold state (`POST /maps/{id}/fold`, `domain.mindmap.fold_flags`), not a client-only limit, so the `+N` toggles and depth stay consistent; maps > 12 nodes open folded at depth 2.
- Design decision: auto-unfolding to reveal a node happens only on explicit traceability navigation (`Workspace.selectNodes`, paper → related nodes), never on map reload (it was undoing *Depth*).
