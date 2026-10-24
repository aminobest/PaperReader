# PaperReader — instructions for AI coding agents

**Before any change, load and follow the `paperreader-dev` skill** (`.github/skills/paperreader-dev/SKILL.md`).
Non-negotiable summary:

1. **Consistency first:** read `docs/requirements.md`, `stories/README.md`, and the `story.md` +
   `logbook.md` of every story your change touches (`grep -rn "US-NN"`). Never break an existing AT.
2. **Story first:** new behavior → new `US-NN` (internal → `CR-NN`) from `stories/_template/`,
   with Given/When/Then ATs that each declare `Levels: unit, integration, system`.
3. **Tests cite ATs** (`AT-NN.k` in test name/docstring) at every declared level.
4. **Logbook:** append a dated entry to every story you touch (the pre-commit hook enforces it).
5. **Gate:** `scripts/ci.sh --fast` before commit, `scripts/ci.sh` (incl. real-LLM system tests)
   before push. Hooks: `scripts/install-hooks.sh`. Never bypass with `--no-verify`.
6. **Architecture:** `domain` pure → `application` (no I/O) → `infrastructure` / `api`. Prompts
   only in `domain/prompts.py` (editable in Admin). All LLM calls via `application/llm_gateway.py`.
   Every AI quote must pass `domain/grounding.py`.
7. **One ID per commit:** `US-NN: title` + story sentence + ATs touched.
8. **Deploy:** `docker compose up --build -d` (see `docs/deployment.md`).

Test accounts (fixtures only): `test` / `test123456789` (admin), `reader` / `reader123456` (user).
