#!/usr/bin/env bash
# CR-01 — the CI gate. Token-free except the system stage (real LLM on a 2-page fixture paper).
#   scripts/ci.sh          full: lint, traceability, arch+unit (py+js), integration, system
#   scripts/ci.sh --fast   everything except system tests (used by the pre-commit hook)
#   scripts/ci.sh --journey  only the CR-03 real-paper journey (arXiv paper, real LLM, ~5-10 min)
#                            JOURNEY_MODEL=openai/gpt-6-luna scripts/ci.sh --journey  → ~40x cheaper than Opus
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt"; exit 1; }

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

if [ "${1:-}" = "--journey" ]; then
  step "journey (CR-03: real arXiv paper, real LLM)"
  (cd tests/system && JOURNEY=1 npx playwright test specs/90-journey.spec.js)
  exit 0
fi

step "lint (ruff)"
"$PY" -m ruff check backend tests scripts

step "traceability (stories ↔ tests ↔ logbooks)"
"$PY" scripts/check_traceability.py

step "architecture + unit (python)"
"$PY" -m pytest -q tests/arch tests/unit

step "unit (javascript, node --test)"
node --test tests/unit/js/

step "integration (API + SQLite + real PDF, scripted LLM stub)"
"$PY" -m pytest -q tests/integration

if [ "${1:-}" != "--fast" ]; then
  step "system (Playwright, real container, real LLM)"
  (cd tests/system && npx playwright test)
fi

printf '\n\033[32mCI gate passed.\033[0m\n'
