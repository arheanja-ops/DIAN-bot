"""Notificaciones vía Telegram Bot API.

Solo notifica; no agenda. El usuario completa el agendamiento manualmente
(incluye reCAPTCHA) usando el enlace incluido en el mensaje.
"""
from __future__ import annotations

import logging

from telegram import Bot
from telegram.constants import ParseMode

from .state import Availability

log = logging.getLogger(__name__)


def build_message(av: Availability, url: str) -> str:
    """Mensaje URGENTE cuando hay citas disponibles: 'entra YA' + trámites/ciudades + URL."""
    items = "\n".join(f"  • {s}" for s in av.slots[:20]) or "  • (ver en el sitio)"
    return (
        f"🚨🚨 *¡HAY CITAS EN LA DIAN — ENTRA YA!* 🚨🚨\n\n"
        f"*Categoría:* {av.servicio}\n"
        f"*Trámites/ciudades con cupo ahora:*\n{items}\n\n"
        f"👉 *Agenda ahora mismo* (debes completar el captcha):\n{url}\n\n"
        f"_Las citas vuelan (duran minutos). Consultado: {av.checked_at}_"
    )


def build_no_availability_message(av: Availability) -> str:
    """Mensaje informativo cuando NO hay citas (modo always / heartbeat)."""
    return (
        f"🔍 Consulta DIAN: *sin citas* de {av.servicio} por ahora "
        f"(ninguna ciudad).\n"
        f"_Consultado: {av.checked_at}_ — te aviso apenas aparezca una."
    )


def build_error_message(detail: str) -> str:
    """Mensaje cuando la consulta falló (timeout/sitio caído). Solo modo always."""
    return (
        f"⚠️ Consulta DIAN: *no pude verificar* esta vez.\n"
        f"Motivo: {detail}\n"
        f"_Reintentaré en la próxima ronda._"
    )


async def notify(token: str, chat_ids: list[str], text: str) -> int:
    """Envía `text` a cada chat_id. Devuelve cuántos envíos tuvieron éxito.

    No propaga errores de envío individuales: registra y continúa, para que
    un chat inválido no bloquee a los demás.
    """
    bot = Bot(token=token)
    ok = 0
    async with bot:
        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                ok += 1
            except Exception as e:  # noqa: BLE001 - un chat no debe tumbar el resto
                log.error("Fallo enviando a chat %s: %s", chat_id, type(e).__name__)
    return ok
