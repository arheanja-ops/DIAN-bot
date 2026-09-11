"""Punto de entrada: orquesta consulta -> diff -> notificación, y agenda L-V.

Modos:
  python -m dian_bot.main --once       Ejecuta una consulta y sale.
  python -m dian_bot.main --dry-run    Consulta pero NO envía a Telegram (imprime).
  python -m dian_bot.main               Arranca el scheduler (L-V a la hora configurada).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Config, ConfigError
from .notifier import (
    build_error_message,
    build_message,
    build_no_availability_message,
    notify,
)
from .scraper import ScrapeError, check_availability
from .state import append_history, load_last, save, should_notify

log = logging.getLogger("dian_bot")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run_once(cfg: Config, *, dry_run: bool = False) -> bool:
    """Una iteración: consulta, compara y (si aplica) notifica.

    Devuelve True si notificó (o hubiera notificado en dry-run).
    """
    try:
        current = await check_availability(cfg)
    except ScrapeError as e:
        log.error("Scrape falló (estructura del sitio): %s", e)
        # En modo always avisamos que no se pudo verificar (evita silencio).
        if cfg.notify_mode == "always" and not dry_run:
            await notify(
                cfg.telegram_token,
                cfg.all_chat_ids,
                build_error_message(str(e)),
            )
        return False

    log.info(
        "Resultado: disponible=%s slots=%d %s",
        current.available,
        len(current.slots),
        current.note,
    )

    prev = load_last(cfg.state_path)
    is_new_hit = should_notify(prev, current)
    save(cfg.state_path, current)
    append_history(cfg.history_path, current)

    # Decidir qué (y si) notificar según el modo:
    #  - Hay cita nueva -> siempre mensaje URGENTE (en cualquier modo).
    #  - No hay cita:
    #      only_hits -> callar.
    #      always    -> mensaje informativo "sin citas".
    if current.available and is_new_hit:
        msg = build_message(current, cfg.url)
    elif current.available and not is_new_hit:
        # Hay citas pero ya te avisé de estas mismas; en 'always' reafirmo, en 'only_hits' callo.
        if cfg.notify_mode == "always":
            msg = build_message(current, cfg.url)
        else:
            log.info("Citas ya notificadas antes; sin cambios.")
            return False
    else:  # no hay citas
        if cfg.notify_mode == "always":
            msg = build_no_availability_message(current)
        else:
            log.info("Sin citas; modo only_hits, no se notifica.")
            return False

    if dry_run:
        log.info("[DRY-RUN] Notificaría:\n%s", msg)
        return True

    sent = await notify(cfg.telegram_token, cfg.all_chat_ids, msg)
    log.info("Notificación enviada a %d/%d chats", sent, len(cfg.all_chat_ids))
    return sent > 0


def _schedule(cfg: Config) -> None:
    scheduler = AsyncIOScheduler(timezone=cfg.timezone)
    if cfg.poll_interval_min > 0:
        # Modo intervalo: consulta cada N minutos (útil para monitoreo local).
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = IntervalTrigger(minutes=cfg.poll_interval_min, timezone=cfg.timezone)
        desc = f"cada {cfg.poll_interval_min} min"
    else:
        # Modo diario: L-V a la hora configurada.
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=cfg.poll_hour,
            minute=cfg.poll_minute,
            timezone=cfg.timezone,
        )
        desc = f"L-V {cfg.poll_hour:02d}:{cfg.poll_minute:02d}"

    scheduler.add_job(
        run_once,
        args=[cfg],
        trigger=trigger,
        name="consulta_dian",
        misfire_grace_time=600,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    log.info("Scheduler activo: %s %s. Ctrl-C para salir.", desc, cfg.timezone)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Monitor de citas DIAN (devolución IVA).")
    ap.add_argument("--once", action="store_true", help="Ejecuta una vez y sale.")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta pero no envía a Telegram (imprime el mensaje).",
    )
    return ap.parse_args(argv)


async def _amain(argv: list[str]) -> int:
    args = _parse_args(argv)
    try:
        cfg = Config.from_env()
    except ConfigError as e:
        # En dry-run permitimos tokens dummy para probar el scraper sin Telegram.
        if args.dry_run:
            import os

            os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dry-run-token")
            os.environ.setdefault("TELEGRAM_CHAT_ID", "0")
            cfg = Config.from_env()
        else:
            print(f"Error de configuración: {e}", file=sys.stderr)
            return 2

    _setup_logging(cfg.log_level)

    if args.once or args.dry_run:
        await run_once(cfg, dry_run=args.dry_run)
        return 0

    _schedule(cfg)
    # Mantener el loop vivo para el scheduler.
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Detenido por el usuario.")
        return 0


def main() -> int:
    return asyncio.run(_amain(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
