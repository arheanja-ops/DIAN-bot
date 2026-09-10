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
from .notifier import build_message, notify
from .scraper import ScrapeError, check_availability
from .state import load_last, save, should_notify

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
        return False

    log.info(
        "Resultado: disponible=%s slots=%d %s",
        current.available,
        len(current.slots),
        current.note,
    )

    prev = load_last(cfg.state_path)
    notify_now = should_notify(prev, current)
    save(cfg.state_path, current)

    if not notify_now:
        log.info("Sin cambios notificables (no hay cita nueva).")
        return False

    msg = build_message(current, cfg.url)
    if dry_run:
        log.info("[DRY-RUN] Notificaría:\n%s", msg)
        return True

    sent = await notify(cfg.telegram_token, cfg.all_chat_ids, msg)
    log.info("Notificación enviada a %d/%d chats", sent, len(cfg.all_chat_ids))
    return sent > 0


def _schedule(cfg: Config) -> None:
    scheduler = AsyncIOScheduler(timezone=cfg.timezone)
    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=cfg.poll_hour,
        minute=cfg.poll_minute,
        timezone=cfg.timezone,
    )
    scheduler.add_job(
        lambda: asyncio.create_task(run_once(cfg)),
        trigger=trigger,
        name="consulta_diaria_dian",
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info(
        "Scheduler activo: L-V %02d:%02d %s. Ctrl-C para salir.",
        cfg.poll_hour,
        cfg.poll_minute,
        cfg.timezone,
    )


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
