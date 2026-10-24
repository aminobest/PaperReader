# CR-01 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — extended
- What: system tests and the journey run on `TEST_MODEL` (default `openai/gpt-6-luna`, ~40x cheaper than Opus);
  Playwright `actionTimeout` 30 s so a stuck click fails fast instead of hanging for the whole test timeout.
- Why: real-LLM tests must stay cheap ("it's fine if it is not that much"); the OpenRouter balance ran low.
- Files: tests/system/start-server.sh, tests/system/playwright.config.js.

## 2026-10-24 — extended
- What: `scripts/ci.sh --journey` runs the CR-03 real-paper journey; default runs exclude it.
- Files: scripts/ci.sh, tests/system/playwright.config.js.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
