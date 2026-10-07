# Plan de ampliación — DIAN-bot (más trámites de la DIAN)

> Fecha: 2026-10-07. Estado: planificado, pendiente de implementar.
> Objetivo: pasar de monitorear 1 trámite (devolución IVA / Videoatención / Medellín)
> a monitorear N trámites de la DIAN en paralelo (RUT, firma, devoluciones, etc.).

## Cuenta / infra
- Cuenta AWS: **ai-platform (080891698277)**, perfil `ai-platform`, región us-east-1.
- Lambda container `dianbot-scraper` (Python + Playwright + Chromium). Backend tfstate
  `dianbot-tfstate-080891698277` (use_lockfile). Repo GitHub: `arheanja-ops/DIAN-bot`
  (gh config `$HOME/.config/gh-dianbot`). Notifica por Telegram, NO agenda (reCAPTCHA fuera de alcance).

---

## 1. Estado actual del código (qué es configurable)

### Ya configurable por env (sin tocar código) — en `dian_bot/config.py` + `.env`
| Variable env | Campo Config | Default | Efecto real |
|---|---|---|---|
| `DIAN_TIPO_ATENCION` | `tipo_atencion` | Videoatención | **dirige el flujo** (`_pick TipoAtencion`) |
| `DIAN_CATEGORIA` | `categoria` | Devoluciones | **dirige el flujo** (`_pick Categorias`) |
| `DIAN_SERVICIO` | `servicio` | Devolución | solo etiqueta en `Availability` (NO filtra) |
| `DIAN_CIUDAD` | `ciudad` | Medellín | solo etiqueta (NO filtra; el scraper es city-agnostic) |

**Clave:** cambiar `DIAN_CATEGORIA` / `DIAN_TIPO_ATENCION` ya cambia qué monitorea. El combo de
trámites (`_read_service_options`) se lee COMPLETO y se reporta todo (ya es multi-ciudad implícito).

### Hardcodeado (requiere código)
- **TipoPersona = "Natural"** fijo en `scraper.py` (`_pick(page,"TipoPersona","Natural")`). Jurídica no soportada.
- `check_availability(cfg)` ejecuta **UNA** combinación por corrida (abre/cierra browser).
- Estado (`state/last_availability.json`, `history.jsonl`) es **archivo único sin clave por combinación**
  → monitorear varias combinaciones se pisaría el estado entre sí.

### Selectores (centralizados en scraper.py, SPA C-Media/ASP.NET WebForms)
`[nombre='...']`, `.boton`, `[pantalla='ModalError'|'ModalSinCitas']`. Frágiles si la DIAN cambia el front.

---

## 2. Catálogo de trámites DIAN (fuentes oficiales dian.gov.co)

Flujo: TipoPersona → TipoAtención → Categoría/grupo → trámite específico (solo muestra lo que tiene cupo).

### Videoatención (no presencial)
- **RUT**: inscripción/actualización persona natural; jurídica; sucesiones líquidas; jurídica sin NIT
  (consorcios, uniones temporales, JAC, propiedad horizontal).
- Cancelación RUT (sucesión liquidada, sin firma electrónica).
- Autogestión servicios en línea con NAF.
- Corrección de errores en declaraciones/recibos (solo Grandes Contribuyentes).
- **Devoluciones/compensaciones** (IVA, renta, saldos a favor) ← lo que monitorea hoy.

### Presencial
- RUT (natural/jurídica/sucesiones/sin NIT), correcciones declaraciones (sin restricción),
  retiro IVA/consumo, libros contabilidad, kiosco autogestión, orientación TAC.
- **Aduaneros**: correcciones SYGA importación, cuenta SYGA, garantías aduaneras, equipaje no
  acompañado, plan canguro Mipyme-expo zona franca.

### Dónde el bot aporta MÁS valor (demanda / escasez de cupos)
1. **Inscripción/actualización RUT persona natural** — altísima demanda, cupos vuelan (Bogotá/Medellín/Cali). MÁXIMO valor.
2. **Firma electrónica / instrumento de firma** — cuello de botella recurrente (validar si es agendable o solo autogestión online).
3. **Devoluciones/compensaciones** (actual) — media-alta, crítico por plazos.
4. **RUT persona jurídica** — media.

---

## 3. Roadmap de ampliación (priorizado)

| ID | Qué | Esfuerzo | Valor | Cambios |
|----|-----|----------|-------|---------|
| **B** | Persona Jurídica configurable | BAJO (1 línea + config) | ALTO | config.py: `DIAN_TIPO_PERSONA` (default Natural); scraper.py: `_pick("TipoPersona", cfg.tipo_persona)` |
| **C** | Otras categorías (RUT, firma, obligaciones) | BAJO (ya soportado por config) | ALTO | setear `DIAN_CATEGORIA`; VALIDAR labels reales antes (ver modo descubrimiento) |
| **A** | Multi-trámite en paralelo (varias combinaciones/corrida) | MEDIO | 🚀 MÁXIMO | ver detalle abajo |
| **D** | Filtro multi-ciudad real | BAJO | MEDIO | scraper.py: filtrar `services` por `cfg.ciudad` (opt-in, fallback reporta todo) |

### Detalle A (multi-trámite) — el gran multiplicador
- **config.py**: `DIAN_TARGETS` (lista JSON de `{tipo_persona, tipo_atencion, categoria, ciudad?}`) → `targets: list[Target]`.
- **scraper.py**: refactor menor de `check_availability` para aceptar un `Target` en vez de leer `cfg` directo.
  REUSAR un solo browser/contexto e iterar los N targets (ahorra tiempo, reduce rate-limiting).
- **state.py**: segmentar estado por `signature = (tipo_persona, tipo_atencion, categoria)`.
  Hoy es archivo único → migrar a dict keyed o archivo por target.
- **main.py**: `run_once` itera targets, notifica por cada hit.

### Orden recomendado
1. **B + C** (desbloquea cobertura inmediata, casi gratis).
2. **A** (multi-target con estado segmentado) — el verdadero salto.
3. **D** (filtro ciudad, reduce ruido).

### PASO 0 OBLIGATORIO antes de ampliar: "modo descubrimiento"
Una corrida que liste TODAS las categorías / tipos de atención / trámites que la DIAN ofrece AHORA,
para capturar los **labels exactos** del combo (ej. ¿"RUT" o "Inscripción RUT"?). Adivinar el label
causa `ScrapeError`. Implementar un flag (ej. `--discover`) que imprima los `.boton` disponibles por paso.

---

## 4. Riesgos
- **Selectores frágiles**: la SPA C-Media/WebForms puede cambiar `nombre=`/`.boton`/`pantalla=`. Mitigado:
  centralizados + `ScrapeError` evita falsos negativos. Añadir alerta cuando el flujo rompa.
- **Labels de categoría inexactos** → `ScrapeError`. Resolver con modo descubrimiento.
- **Rate-limiting**: multi-target multiplica navegaciones. Reusar un browser/corrida, espaciar, no bajar
  de ~1 corrida/día por target en combinaciones poco urgentes.
- **No todo tiene Videoatención**: aduaneros/varios son solo presenciales. Validar matriz
  tipoAtención×trámite para no confundir "no existe por este canal" con "no hay cupo".
- **Captcha/confirmación**: fuera de alcance (el bot solo consulta disponibilidad).

---

## 5. Decisiones PENDIENTES del usuario (antes de implementar)
- [ ] ¿Qué trámites concretos monitorear además de devolución IVA? (RUT natural / RUT jurídica / firma / otros)
- [ ] ¿En qué ciudades?
- [ ] ¿Presencial además de Videoatención, o solo video?

## 6. Base técnica ya lista (PR aparte)
- PR #10 (arheanja-ops/DIAN-bot): fix de timeouts del scraper (quitar --single-process/--no-zygote,
  timeout en launch, cierre protegido) + poll de 10min→5min. Checks verdes (test+plan pass).
  **Pendiente mergear.** Es la base estable sobre la que se construye la ampliación.
