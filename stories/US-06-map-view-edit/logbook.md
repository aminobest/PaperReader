# US-06 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
- Design decision: *Depth* is persisted fold state (`POST /maps/{id}/fold`, `domain.mindmap.fold_flags`), not a client-only limit, so the `+N` toggles and depth stay consistent; maps > 12 nodes open folded at depth 2.
- Design decision: auto-unfolding to reveal a node happens only on explicit traceability navigation (`Workspace.selectNodes`, paper → related nodes), never on map reload (it was undoing *Depth*).
