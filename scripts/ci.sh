#!/usr/bin/env bash
# CR-01 — the CI gate. Token-free except the system stage (real LLM on a 2-page fixture paper).
#   scripts/ci.sh          full: lint, traceability, arch+unit (py+js), integration, system
#   scripts/ci.sh --fast   everything except system tests (used by the pre-commit hook)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Missing .venv — run: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt"; exit 1; }

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

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
