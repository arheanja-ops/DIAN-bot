"""Configuración del bot DIAN. Carga variables de entorno y valida al arranque.

Falla temprano y ruidosamente si falta configuración crítica (fail-securely).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Configuración inválida o incompleta."""


def _get(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise ConfigError(f"Falta la variable de entorno obligatoria: {name}")
    return val or ""


@dataclass(frozen=True)
class Config:
    """Configuración inmutable del bot.

    Los secretos (token) se leen de entorno, nunca se hardcodean.
    """

    telegram_token: str
    telegram_chat_id: str
    # Filtros de búsqueda
    servicio: str = "Devolución"  # texto a matchear en el combo Servicios
    ciudad: str = "Medellín"
    tipo_atencion: str = "Videoatención"  # Presencial | Videoatención
    categoria: str = "Devoluciones"  # categoría del combo Categorias
    # Operación
    url: str = "https://agendamiento.dian.gov.co/"
    poll_hour: int = 8  # hora local (L-V) para la consulta diaria
    poll_minute: int = 0
    timezone: str = "America/Bogota"
    headless: bool = True
    nav_timeout_ms: int = 45000
    state_path: str = "state/last_availability.json"
    history_path: str = "state/history.jsonl"
    notify_mode: str = "only_hits"  # only_hits | always
    log_level: str = "INFO"
    extra_chat_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        token = _get("TELEGRAM_BOT_TOKEN", required=True)
        chat_id = _get("TELEGRAM_CHAT_ID", required=True)
        extra = [c.strip() for c in _get("TELEGRAM_EXTRA_CHAT_IDS").split(",") if c.strip()]
        return cls(
            telegram_token=token,
            telegram_chat_id=chat_id,
            extra_chat_ids=extra,
            servicio=_get("DIAN_SERVICIO", "Devolución"),
            ciudad=_get("DIAN_CIUDAD", "Medellín"),
            tipo_atencion=_get("DIAN_TIPO_ATENCION", "Videoatención"),
            categoria=_get("DIAN_CATEGORIA", "Devoluciones"),
            url=_get("DIAN_URL", "https://agendamiento.dian.gov.co/"),
            poll_hour=int(_get("POLL_HOUR", "8")),
            poll_minute=int(_get("POLL_MINUTE", "0")),
            timezone=_get("TZ", "America/Bogota"),
            headless=_get("HEADLESS", "true").lower() != "false",
            state_path=_get("STATE_PATH", "state/last_availability.json"),
            history_path=_get("HISTORY_PATH", "state/history.jsonl"),
            notify_mode=_get("NOTIFY_MODE", "only_hits").lower(),
            log_level=_get("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def all_chat_ids(self) -> list[str]:
        return [self.telegram_chat_id, *self.extra_chat_ids]
