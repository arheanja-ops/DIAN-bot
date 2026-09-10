"""Scraper de disponibilidad de citas DIAN usando Playwright.

Flujo real verificado en https://agendamiento.dian.gov.co/ (SPA C-Media
WebPlayer sobre ASP.NET WebForms). Los controles del framework se identifican
por el atributo `nombre=` y sus opciones son hijos con clase `.boton`.

Secuencia:
  1. Home -> aceptar modal de tratamiento de datos ("Si").
  2. Tarjeta "Agendar cita" (div con texto "Programe cita").
  3. PasoUno (cascada, cada selección revela el siguiente control):
       TipoPersona   -> "Natural"
       TipoAtencion  -> "Videoatención"  (las devoluciones IVA son no presenciales)
       Categorias    -> "Devoluciones"
     Si aparece ModalError "No se encontraron especialidades" -> sin disponibilidad.
       (combo de trámite específico)  -> opción que matchee cfg.servicio
     btnSiguienteBlock -> PasoDos.
  4. PasoDos: seleccionar Ciudad (Medellín) y leer fecha/horas.
       ModalSinCitas visible -> sin disponibilidad.
       Fechas/horas presentes -> disponible; se listan.

NO resuelve el reCAPTCHA ni confirma cita: el captcha vive en el paso final de
confirmación, fuera del alcance de la consulta de disponibilidad.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from playwright.async_api import (
    Page,
    TimeoutError as PWTimeout,
    async_playwright,
)

from .config import Config
from .state import Availability

log = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Frases que, si aparecen en un modal, indican ausencia de disponibilidad.
_NO_AVAILABILITY_HINTS = (
    "no se encontraron especialidades",
    "no hay citas",
    "no se encontraron citas",
    "sin disponibilidad",
    "no existen citas",
)


class ScrapeError(RuntimeError):
    """Error estructural: el sitio cambió y el flujo no pudo completarse."""


async def _accept_consent(page: Page) -> None:
    try:
        cb = page.locator("label:has-text('Acepto') input[type=checkbox]").first
        if await cb.count() and not await cb.is_checked():
            await cb.check(timeout=4000)
    except PWTimeout:
        pass
    for label in ("Si", "Sí", "Aceptar", "Continuar"):
        btn = page.get_by_role("button", name=label, exact=True)
        try:
            if await btn.count() and await btn.first.is_visible():
                await btn.first.click(timeout=3000)
                await page.wait_for_timeout(1000)
                return
        except PWTimeout:
            continue


async def _enter_agendar(page: Page) -> None:
    for sel in (
        "div:has-text('Programe cita')",
        "[nombre='btnSolicitarCita']",
        "text=Agendar cita",
    ):
        try:
            loc = page.locator(sel).first
            await loc.scroll_into_view_if_needed(timeout=3000)
            await loc.click(timeout=5000)
            await page.wait_for_timeout(1500)
            return
        except PWTimeout:
            continue
    raise ScrapeError("No se pudo entrar a 'Agendar cita'")


async def _pick(page: Page, control: str, option: str) -> bool:
    """Selecciona una opción (hijo .boton o cualquier hoja con el texto) dentro
    del control identificado por nombre=. Devuelve True si hizo clic.
    """
    for sel in (
        f"[nombre='{control}'] .boton:has-text('{option}')",
        f"[nombre='{control}'] >> text={option}",
    ):
        try:
            await page.locator(sel).first.click(timeout=4000)
            await page.wait_for_timeout(1500)
            log.debug("pick %s -> %s", control, option)
            return True
        except PWTimeout:
            continue
    log.warning("No se pudo seleccionar '%s' en control '%s'", option, control)
    return False


async def _modal_no_availability(page: Page) -> bool:
    """True si hay un modal (Error o SinCitas) visible cuyo texto indica que no
    hay disponibilidad. Cierra el modal si lo encuentra.
    """
    for pantalla in ("ModalError", "ModalSinCitas"):
        nodes = page.locator(f"[pantalla='{pantalla}']")
        try:
            count = await nodes.count()
        except PWTimeout:
            continue
        visible = False
        text = ""
        # El framework duplica nodos del modal; el texto puede estar en cualquiera.
        for i in range(count):
            node = nodes.nth(i)
            try:
                if await node.is_visible():
                    visible = True
                    node_text = (await node.inner_text()).strip().lower()
                    if node_text and len(node_text) > len(text):
                        text = node_text
            except PWTimeout:
                continue
        if not visible:
            continue
        log.info("%s visible: %s", pantalla, text[:80] or "(sin texto)")
        no_avail = (
            pantalla == "ModalSinCitas"
            or any(h in text for h in _NO_AVAILABILITY_HINTS)
            or (pantalla == "ModalError" and not text)
        )
        if no_avail:
            for name in ("Aceptar", "Cerrar"):
                btn = page.locator(f"[pantalla='{pantalla}']").get_by_role(
                    "button", name=name
                )
                try:
                    if await btn.count():
                        await btn.first.click(timeout=2500)
                        break
                except PWTimeout:
                    continue
            return True
    return False


async def _read_slots(page: Page) -> list[str]:
    """Extrae fechas/horas disponibles del PasoDos (combo Horas + campo txtFecha)."""
    slots: list[str] = []
    fecha = page.locator("[nombre='txtFecha']").first
    try:
        if await fecha.count():
            val = (await fecha.input_value()).strip()
            if val:
                slots.append(val)
    except PWTimeout:
        pass
    horas = page.locator("[nombre='Horas']").first
    try:
        if await horas.count():
            await horas.click(timeout=3000)
            await page.wait_for_timeout(600)
            opts = await page.evaluate(
                """() => {
                    const h=document.querySelector("[nombre='Horas']");
                    if(!h) return [];
                    return [...h.querySelectorAll('*')]
                        .map(e => (e.innerText||'').trim())
                        .filter(t => t && t.length < 20);
                }"""
            )
            for o in opts:
                if o.lower() not in ("horas", "seleccione") and o not in slots:
                    slots.append(o)
    except PWTimeout:
        pass
    return slots


async def check_availability(cfg: Config) -> Availability:
    """Ejecuta el flujo y devuelve la disponibilidad. Solo lanza ScrapeError
    ante fallos estructurales (no ante "no hay citas", que es un resultado).
    """
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def result(available: bool, slots: list[str], note: str = "") -> Availability:
        return Availability(
            available=available,
            servicio=cfg.servicio,
            ciudad=cfg.ciudad,
            slots=slots,
            checked_at=now,
            note=note,
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless)
        ctx = await browser.new_context(user_agent=_UA, locale="es-CO")
        page = await ctx.new_page()
        page.set_default_timeout(cfg.nav_timeout_ms)
        try:
            await page.goto(cfg.url, wait_until="networkidle", timeout=cfg.nav_timeout_ms)
            await page.wait_for_timeout(2500)

            await _accept_consent(page)
            await _enter_agendar(page)

            # PasoUno en cascada
            if not await _pick(page, "TipoPersona", "Natural"):
                raise ScrapeError("PasoUno: no se pudo seleccionar tipo de persona")
            await _pick(page, "TipoAtencion", cfg.tipo_atencion)
            if not await _pick(page, "Categorias", cfg.categoria):
                raise ScrapeError("PasoUno: no se pudo seleccionar la categoría")

            # Tras elegir categoría puede aparecer un modal de "sin especialidades"
            await page.wait_for_timeout(1500)
            if await _modal_no_availability(page):
                return result(False, [], note="sin especialidades para devoluciones")

            # Trámite específico (si el framework lo pide como combo aparte)
            await _pick(page, "Servicios", cfg.servicio)

            # Avanzar a PasoDos
            try:
                await page.locator("[nombre='btnSiguienteBlock']").first.click(timeout=5000)
                await page.wait_for_timeout(2500)
            except PWTimeout:
                # Si no avanza y no hubo modal, tratamos como sin disponibilidad.
                if await _modal_no_availability(page):
                    return result(False, [], note="sin disponibilidad en PasoUno")
                raise ScrapeError("No se pudo avanzar a PasoDos")

            # PasoDos: ciudad + disponibilidad
            await _pick(page, "Ciudades", cfg.ciudad)
            await page.wait_for_timeout(1500)

            if await _modal_no_availability(page):
                return result(False, [], note="ModalSinCitas en PasoDos")

            slots = await _read_slots(page)
            return result(len(slots) > 0, slots)
        finally:
            await browser.close()
