"""Handler de AWS Lambda para el bot DIAN.

Reutiliza `run_once` del bot. Los secretos (token/chat_id de Telegram) se leen
de SSM Parameter Store cuando corre en Lambda (nombres en SSM_TOKEN_PARAM /
SSM_CHAT_ID_PARAM), con fallback a variables de entorno para pruebas locales.

Disparadores:
- EventBridge Scheduler (cron): consulta programada.
- API Gateway (webhook de Telegram): comandos a demanda (fase posterior).
"""
from __future__ import annotations

import asyncio
import logging
import os

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("dian_bot.lambda")


def _load_secrets_from_ssm() -> None:
    """Si hay nombres de parámetros SSM configurados, carga el token y chat_id
    en el entorno para que Config.from_env los tome. No falla si ya están en env.
    """
    token_param = os.getenv("SSM_TOKEN_PARAM")
    chat_param = os.getenv("SSM_CHAT_ID_PARAM")
    if not (token_param or chat_param):
        return  # modo local: se usan las env vars directas

    import boto3  # disponible en el runtime de Lambda

    ssm = boto3.client("ssm")

    def _get(name: str) -> str:
        return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]

    if token_param and not os.getenv("TELEGRAM_BOT_TOKEN"):
        os.environ["TELEGRAM_BOT_TOKEN"] = _get(token_param)
    if chat_param and not os.getenv("TELEGRAM_CHAT_ID"):
        os.environ["TELEGRAM_CHAT_ID"] = _get(chat_param)


def handler(event, context):
    """Punto de entrada de Lambda. Ejecuta una consulta y notifica según modo."""
    log.info("Lambda invocada.")
    _load_secrets_from_ssm()

    from dian_bot.config import Config
    from dian_bot.main import run_once

    cfg = Config.from_env()
    notified = asyncio.run(run_once(cfg))
    return {"statusCode": 200, "notified": bool(notified)}
