#!/usr/bin/env bash
# CR-01 — fresh, isolated server for system tests (own DATA_DIR, test users, real OpenRouter key from .env).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="$ROOT/.tmp/system"
rm -rf "$DATA" && mkdir -p "$DATA"
cp "$ROOT/tests/fixtures/users.json" "$DATA/"
set -a; . "$ROOT/.env"; set +a
# CR-01: system tests use a cheap model by default (Opus stays the app default); override with TEST_MODEL.
DEFAULT_MODEL="${TEST_MODEL:-openai/gpt-6-luna}"
cd "$ROOT/backend"
exec env DATA_DIR="$DATA" DEFAULT_MODEL="$DEFAULT_MODEL" "$ROOT/.venv/bin/uvicorn" app.main:create_app --factory --host 127.0.0.1 --port "${PORT:-7420}"
