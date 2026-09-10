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
    """Construye el mensaje de alerta en Markdown."""
    slots = "\n".join(f"  • {s}" for s in av.slots[:15]) or "  • (ver en el sitio)"
    return (
        f"🔔 *Citas DIAN disponibles*\n"
        f"*Trámite:* {av.servicio}\n"
        f"*Ciudad:* {av.ciudad}\n"
        f"*Cuándo:*\n{slots}\n\n"
        f"Agenda aquí (requiere completar el captcha):\n{url}\n\n"
        f"_Consultado: {av.checked_at}_"
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
