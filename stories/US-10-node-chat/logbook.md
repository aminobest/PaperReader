# US-10 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — extended (AT-10.5)
- What: delete a chat message (question + its answer); quotes cascade, AI-trace highlights disappear.
- Why: requirements gap — "CRUD operations is key everywhere".
- Files: backend/app/api/workspace.py, frontend/js/panels.js, frontend/css/app.css.
- Tests: test_workspace_admin.py, 02-ai.spec.js.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
