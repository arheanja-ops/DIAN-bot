#!/usr/bin/env bash
# Ejecuta una consulta de disponibilidad de citas DIAN.
# Uso:
#   ./scripts/run.sh            # consulta y notifica si corresponde
#   ./scripts/run.sh --dry-run  # consulta sin enviar a Telegram
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d ".venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ "${1:-}" = "--dry-run" ]; then
  exec python -m dian_bot.main --dry-run
else
  exec python -m dian_bot.main --once
fi
