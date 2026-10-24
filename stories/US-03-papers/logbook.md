# US-03 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — extended (AT-03.5)
- What: title fallback to the largest non-rotated heading on page 1 before the filename.
- Why: found by the CR-03 journey — arXiv PDFs have no metadata title, so "1706.03762" was shown.
- Files: backend/app/infrastructure/pdf.py (`_first_page_heading`), backend/app/domain/rules.py, backend/app/api/sessions.py.
- Tests: test_rules.py, test_core_api.py.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
