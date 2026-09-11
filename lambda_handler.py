"""Handler de AWS Lambda para el bot DIAN.

Una sola Lambda con router por tipo de evento:

- **EventBridge Scheduler** (o invocación directa con {"action":"scrape"}):
  ejecuta el scraping y notifica según NOTIFY_MODE.
- **API Gateway** (webhook de Telegram): parsea el comando del mensaje y
  responde. `/consultar` dispara un scrape asíncrono (auto-invoca esta misma
  Lambda con action=scrape) para no exceder el timeout del webhook.

Los secretos (token/chat_id) se leen de SSM Parameter Store en Lambda, con
fallback a variables de entorno para pruebas locales.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("dian_bot.lambda")


def _load_secrets_from_ssm() -> None:
    token_param = os.getenv("SSM_TOKEN_PARAM")
    chat_param = os.getenv("SSM_CHAT_ID_PARAM")
    if not (token_param or chat_param):
        return
    import boto3

    ssm = boto3.client("ssm")

    def _get(name: str) -> str:
        return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]

    if token_param and not os.getenv("TELEGRAM_BOT_TOKEN"):
        os.environ["TELEGRAM_BOT_TOKEN"] = _get(token_param)
    if chat_param and not os.getenv("TELEGRAM_CHAT_ID"):
        os.environ["TELEGRAM_CHAT_ID"] = _get(chat_param)

    secret_param = os.getenv("SSM_WEBHOOK_SECRET_PARAM")
    if secret_param and not os.getenv("TELEGRAM_WEBHOOK_SECRET"):
        try:
            os.environ["TELEGRAM_WEBHOOK_SECRET"] = _get(secret_param)
        except Exception:  # noqa: BLE001 - si no está, el webhook queda sin validar
            log.warning("No se pudo leer el webhook secret de SSM")


# --------------------------- acción: scraping ---------------------------

def _run_scrape() -> dict:
    from dian_bot.config import Config
    from dian_bot.main import run_once

    cfg = Config.from_env()
    notified = asyncio.run(run_once(cfg))
    return {"statusCode": 200, "notified": bool(notified)}


# --------------------------- acción: webhook ---------------------------

_HELP = (
    "🤖 *Bot de citas DIAN*\n\n"
    "Comandos:\n"
    "• /consultar — revisa YA si hay citas de devolución\n"
    "• /estado — última consulta registrada\n"
    "• /ayuda — este mensaje\n\n"
    "Además te aviso automático L-V de 7am a 5pm."
)


async def _send(chat_id: str, text: str) -> None:
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    async with bot:
        await bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )


def _self_invoke_scrape() -> None:
    """Auto-invoca esta Lambda en modo async para hacer el scrape sin bloquear
    el webhook (el scraping tarda más que el timeout de respuesta a Telegram)."""
    import boto3

    boto3.client("lambda").invoke(
        FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
        InvocationType="Event",  # async
        Payload=json.dumps({"action": "scrape", "forced": True}).encode(),
    )


def _handle_webhook(event: dict) -> dict:
    # Validar el secret token del webhook de Telegram (anti-spoofing).
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if expected:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        got = headers.get("x-telegram-bot-api-secret-token")
        if got != expected:
            log.warning("Webhook con secret inválido")
            return {"statusCode": 403, "body": "forbidden"}

    body = event.get("body") or "{}"
    try:
        update = json.loads(body)
    except json.JSONDecodeError:
        return {"statusCode": 200, "body": "ok"}  # ignora ruido

    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip().lower()
    chat_id = str((msg.get("chat") or {}).get("id") or os.environ["TELEGRAM_CHAT_ID"])

    if text.startswith("/consultar"):
        asyncio.run(_send(chat_id, "🔎 Consultando la DIAN ahora mismo, te aviso en unos segundos…"))
        _self_invoke_scrape()
    elif text.startswith("/estado"):
        asyncio.run(_send(chat_id, _estado_text()))
    else:  # /ayuda, /start o cualquier otra cosa
        asyncio.run(_send(chat_id, _HELP))

    return {"statusCode": 200, "body": "ok"}


def _estado_text() -> str:
    """Lee el último estado persistido (si existe en /tmp) para /estado."""
    import json as _json
    from pathlib import Path

    p = Path(os.getenv("STATE_PATH", "/tmp/last.json"))
    if not p.exists():
        return "ℹ️ Aún no hay una consulta registrada en esta instancia."
    try:
        d = _json.loads(p.read_text(encoding="utf-8"))
        estado = "hay citas ✅" if d.get("available") else "sin citas"
        return f"📊 Última consulta: {estado}\n_{d.get('checked_at', '')}_"
    except (ValueError, OSError):
        return "ℹ️ No pude leer el último estado."


# --------------------------- router ---------------------------

def handler(event, context):
    _load_secrets_from_ssm()

    # API Gateway (webhook): el evento trae 'requestContext'/'body'.
    if isinstance(event, dict) and (
        "requestContext" in event or "rawPath" in event or "httpMethod" in event
    ):
        return _handle_webhook(event)

    # Por defecto (EventBridge / invocación directa): scraping.
    return _run_scrape()
