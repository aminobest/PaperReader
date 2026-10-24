# CR-01 — Token-free CI gate

As the developer (human or AI), I want every change to be checked automatically against all previous stories, so that the app grows without regressions.

## Acceptance tests
- **AT-C01.1** Given stories and tests, the traceability check fails on an uncovered AT, an unknown AT, or a missing logbook — Levels: unit
- **AT-C01.2** Given the backend, the domain layer is pure, the application layer does no I/O and never imports api/infrastructure, the API never calls the LLM client directly, and prompt text lives only in `domain/prompts.py` — Levels: unit
- **AT-C01.3** Given staged code changes, the pre-commit check fails unless a story logbook is staged too — Levels: unit

## Main files
- `scripts/ci.sh`
- `scripts/check_traceability.py`
- `scripts/hooks/*`
- `tests/arch/*`
