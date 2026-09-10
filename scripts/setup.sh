#!/usr/bin/env bash
# Prepara el entorno local: crea el venv, instala dependencias y el navegador.
# Uso: ./scripts/setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "→ Creando virtualenv en .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Instalando dependencias ..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "→ Instalando Chromium para Playwright ..."
python -m playwright install chromium

if [ ! -f ".env" ]; then
  echo "→ No existe .env; copiando plantilla desde .env.example ..."
  cp .env.example .env
  echo "  ⚠️  Edita .env con tu TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID."
fi

echo "✅ Setup completo. Si usas direnv: 'cp .envrc.example .envrc && direnv allow'."
