---
name: paperreader-dev
description: Mandatory development workflow for the PaperReader app. Use for ANY change in this repo (feature, fix, refactor, prompt, UI). Enforces story-first, ID-traceable development (US-NN / CR-NN), acceptance tests at unit + integration + system level, a per-story maintenance logbook, and the token-free CI gate (scripts/ci.sh).
---

# PaperReader development workflow

Goal: the app grows without regressions. Every line answers "why does it exist?" (a story ID)
and "what proves it works?" (tests that cite that ID). Everything automatable runs in
`scripts/ci.sh` — never spend LLM tokens on what a script can check.

## 0. Before touching code (consistency check)
1. Read `docs/requirements.md` and `stories/README.md` (index).
2. Identify the affected stories: `grep -rn "US-07" backend frontend tests` for each candidate ID.
3. Read each affected `stories/<ID>-*/story.md` **and** its `logbook.md`. Your change must not
   violate any acceptance test (AT) of any existing story. If it must, say so explicitly and
   update that story's ATs + logbook in the same change.

## 1. Decide the ID
- New user-visible behaviour → new `US-NN` (next free number, never reused).
- Internal change (refactor, infra, schema, CI) → new `CR-NN`.
- Change to an existing story's behaviour → reuse that ID; record it in its logbook.

## 2. Write the story first
Create `stories/<ID>-<slug>/` by copying `stories/_template/`:
- `story.md`: "As a … I want … so that …", then acceptance tests `AT-NN.k` (Given/When/Then),
  each with a `Levels:` line listing `unit`, `integration`, `system`.
- `logbook.md`: one dated entry per change (type: created | extended | fixed | refactored,
  what, why, files, tests).
- Add the row to `stories/README.md`.

## 3. Write tests that cite the ATs
| Level | Where | What | Tokens |
|---|---|---|---|
| unit | `tests/unit/test_*.py` | pure `domain/` + `application/` logic | none |
| integration | `tests/integration/test_*.py` | HTTP API + SQLite + real PDF; LLM = scripted stub (deterministic retry paths) | none |
| system | `tests/system/specs/*.spec.js` | Playwright against a real test container, **real LLM** on the 2-page fixture paper | small |

Every test names the AT it proves in its name or docstring, e.g.
`def test_quote_not_in_paper_triggers_retry():  """AT-04.2 …"""` or
`test('AT-07.1 selecting a node highlights its quotes', …)`.
`scripts/check_traceability.py` fails CI if any AT is not cited at **every** level its
`Levels:` line declares, if a test cites an unknown AT, or if a story lacks a logbook.

## 4. Implement — architecture rules (enforced by `tests/arch`)
- `backend/app/domain/` — pure Python (no fastapi, sqlite, httpx, fitz, app.infrastructure/api/application).
- `backend/app/application/` — use cases; may import domain, never `app.api`.
- `backend/app/infrastructure/` — SQLite repo, PDF (PyMuPDF), OpenRouter / Fake LLM.
- `backend/app/api/` — FastAPI routers, thin.
- Prompt text lives ONLY in `domain/prompts.py` defaults (editable in Admin → stored in DB).
- All LLM calls go through `application/llm_gateway.py` (logs every call).
- Every quote shown to the user must pass `domain/grounding.py` verification.
- Module docstrings start with the owning ID(s): `"""US-04 — …"""`.

## 5. Run the gate (no tokens)
```
scripts/ci.sh            # lint + arch + traceability + unit + integration + system
scripts/ci.sh --fast     # skip system tests (pre-commit uses this)
```
Git hooks (`scripts/install-hooks.sh`) run `--fast` on commit and full on push. Do not bypass.

## 6. Finish
- Append a logbook entry to every story you touched (CI checks code changes come with a
  logbook change: `check_traceability.py --staged`).
- One ID per commit: `US-07: <title>` + story sentence + ATs touched.
- Redeploy: `docker compose up --build -d` (served on the tailnet, see `docs/deployment.md`).
