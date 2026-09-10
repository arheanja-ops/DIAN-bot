#!/usr/bin/env bash
# Corre la suite de tests (no requiere navegador; usan un fake de Playwright).
# Uso: ./scripts/test.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d ".venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python -m pytest -q "$@"
