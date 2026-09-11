"""Handler de AWS Lambda para el bot DIAN.

Reutiliza `run_once` del bot. Sirve para dos disparadores:
- EventBridge Scheduler (cron): consulta programada.
- API Gateway (webhook de Telegram): comandos a demanda (fase posterior).

En esta fase de spike solo cubre la ejecución programada (evento vacío o de
EventBridge). El scraper corre headless con el Chromium empaquetado en la imagen.
"""
from __future__ import annotations

import asyncio
import logging

from dian_bot.config import Config
from dian_bot.main import run_once

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger("dian_bot.lambda")


def handler(event, context):
    """Punto de entrada de Lambda. Ejecuta una consulta y notifica según modo."""
    log.info("Lambda invocada. event keys: %s", list(event) if isinstance(event, dict) else type(event))
    cfg = Config.from_env()
    notified = asyncio.run(run_once(cfg))
    return {
        "statusCode": 200,
        "notified": bool(notified),
    }
