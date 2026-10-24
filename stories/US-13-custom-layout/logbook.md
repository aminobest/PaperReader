# US-13 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — created
- What: layout menu (▦) with side-panel position right/left/bottom/drawer, swap map↔paper, reset;
  draggable dividers (wide touch target for iPad), double-click resets; prefs per device class on the server.
- Why: owner request ("resize the 3 areas and change the layout, e.g. notes as footer").
- Impact on US-12: tablet default stays the drawer (AT-12.2 unchanged); desktop default unchanged (AT-12.1);
  phone keeps tabs (AT-12.3). Replaces the earlier localStorage-only `pr.cols` splitter.
- Files: frontend/js/layout.mjs, frontend/js/workspace.js, frontend/css/app.css, backend/app/api/prefs.py,
  backend/app/domain/rules.py, backend/app/infrastructure/repo.py.
- Tests: tests/unit/js/frontend.test.mjs, tests/unit/test_rules.py, tests/integration/test_prefs.py,
  tests/system/specs/03-layout.spec.js.
