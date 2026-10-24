# US-12 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — fixed
- What: the map re-fits when the device class changes (e.g. rotating an iPad, desktop → phone width).
- Why: found by the CR-03 journey screenshots — the phone view kept the desktop zoom, cutting the map off.
- Files: frontend/js/workspace.js. Tests: 90-journey.spec.js (phone step).

## 2026-10-24 — extended (by US-13)
- What: panes are now placed by named grid areas computed from the US-13 layout model; tablet drawer is the `drawer` layout (still the tablet default, AT-12.2 unchanged).
- Files: frontend/css/app.css, frontend/js/workspace.js.
- Tests: 01-ui.spec.js device tests still pass unchanged.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
