# US-14 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — created
- What: strengthened all AI quote-generation and correction prompts to prioritize complete,
  contextual passages that directly support a map node or answer claim. The model chooses the
  number of passages; there is no quote-count target or cap.
- Why: owner reported quotes were fragmented and difficult to connect to the map item or to
  understanding the paper.
- Files: see story.md › Main files. An additive DB column from the first version remains unused
  on already-upgraded databases; no data is deleted.
- Tests: tests/unit/test_grounding.py, tests/unit/test_mindmap.py, tests/unit/test_rules.py,
  tests/integration/test_maps.py, tests/system/specs/02-ai.spec.js.
- Verification: 122 Python unit/integration/architecture tests, 13 JavaScript unit tests,
  traceability, and the real-Luna 2-page generation system test all passed. The first system
  run checked the initial support-note implementation; after the owner's refinement, no-token
  tests were updated to verify unbounded, model-selected passage count and no word-count gate.

## 2026-10-24 — refined per owner feedback
- What: removed the added support-note field and UI, and removed any fixed number of passages
  or word-count target from generation prompts and validation. Kept the contextual passage
  guidance and verbatim grounding.
- Why: the owner wants evidence to remain direct source text and prefers the model to decide how
  many passages are needed.
- Tests: scripts/ci.sh --fast; real-LLM call not repeated to avoid additional API usage.
