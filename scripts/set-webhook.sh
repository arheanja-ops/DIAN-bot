#!/usr/bin/env bash
# Registra (o elimina) el webhook de Telegram apuntando al API Gateway.
# Requiere: TELEGRAM_BOT_TOKEN en el entorno (o .env) y la URL del webhook.
#
# Uso:
#   ./scripts/set-webhook.sh set <WEBHOOK_URL> <SECRET>
#   ./scripts/set-webhook.sh delete
#   ./scripts/set-webhook.sh info
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }

: "${TELEGRAM_BOT_TOKEN:?Falta TELEGRAM_BOT_TOKEN}"
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
CMD="${1:-info}"

case "$CMD" in
  set)
    URL="${2:?Falta la URL del webhook}"
    SECRET="${3:?Falta el secret}"
    curl -sS -X POST "$API/setWebhook" \
      -d "url=${URL}" \
      -d "secret_token=${SECRET}" \
      -d "allowed_updates=[\"message\"]" | python3 -m json.tool
    ;;
  delete)
    curl -sS -X POST "$API/deleteWebhook" | python3 -m json.tool
    ;;
  info)
    curl -sS "$API/getWebhookInfo" | python3 -m json.tool
    ;;
  *)
    echo "Uso: $0 {set <url> <secret>|delete|info}" >&2
    exit 1
    ;;
esac
