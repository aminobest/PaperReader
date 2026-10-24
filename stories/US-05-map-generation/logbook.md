# US-05 — logbook

Newest first. Types: created | extended | fixed | refactored.

## 2026-10-24 — extended (AT-05.5)
- What: depth assertion — maps shallower than `min_map_depth` (Admin, default 3) get one `map_deepen` request; new prompt template + setting.
- Why: found by the CR-03 journey — GPT-6 Luna returned a valid but 2-level map of a 15-page paper, violating "high level → tiny details".
- Files: backend/app/domain/mindmap.py (`depth_of`, `merge_deeper`), backend/app/domain/prompts.py, backend/app/application/map_service.py, backend/app/application/settings.py, frontend/js/admin.js.
- Tests: test_mindmap.py, test_maps.py, 90-journey.spec.js (checks depth ≥ 3).

## 2026-10-24 — fixed (AT-05.4)
- What: OpenRouter client retries transient failures (timeout/429/5xx/402 in-flight budget) with backoff honouring Retry-After.
- Why: found by the CR-03 journey — a chat job failed on `402 in_flight_budget_exhausted, Retry-After 120` right after a large map generation.
- Files: backend/app/infrastructure/llm.py.
- Tests: tests/unit/test_llm_retry.py, tests/integration/test_llm_client.py.

## 2026-10-24 — extended (AT-05.1)
- What: AT-05.1 now also asserts the default prompt asks for high→low levels, a background branch and plain explanations.
- Why: requirement "understand papers even without the background" had no test.
- Tests: test_rules.py.

## 2026-10-24 — created
- What: initial implementation of all acceptance tests above.
- Why: initial requirements (docs/requirements.md).
- Files: see story.md › Main files.
- Tests: every AT cited at its declared levels (scripts/check_traceability.py).
