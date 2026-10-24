#!/usr/bin/env bash
# CR-01 — installs the git hooks that run the CI gate automatically.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/* scripts/*.sh
echo "hooks installed (core.hooksPath=scripts/hooks)"
