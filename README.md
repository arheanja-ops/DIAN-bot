# DIAN Citas Bot

Bot que consulta **de lunes a viernes** la disponibilidad de citas en el sistema
de agendamiento de la DIAN (https://agendamiento.dian.gov.co/) para el trámite de
**devolución/compensación de IVA** por **Videoatención** y, cuando aparece una
cita, **te avisa por Telegram**.

El bot **solo notifica**: no agenda ni resuelve el reCAPTCHA. Cuando recibas la
alerta, entras al enlace y completas el agendamiento tú mismo (el captcha está en
el paso final de confirmación, fuera del alcance de la consulta).

## Cómo funciona

1. Abre el sitio con un navegador headless (Playwright + Chromium).
2. Recorre el flujo real: acepta el consentimiento → *Agendar cita* →
   `Persona Natural` → `Videoatención` → `Devoluciones` → ciudad `Medellín`.
3. Determina disponibilidad:
   - Modal *"No se encontraron especialidades…"* o *ModalSinCitas* → **no hay**.
   - Fechas/horas presentes → **hay** (extrae los horarios).
4. Compara con la última consulta guardada (`state/`) y **solo notifica si hay
   una cita nueva**, evitando ruido diario.

## Requisitos

- Python 3.12+
- macOS o Linux

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configuración

1. Crea un bot con [@BotFather](https://t.me/BotFather) y copia el token.
2. Obtén tu `chat_id` escribiéndole a [@userinfobot](https://t.me/userinfobot).
3. Copia el ejemplo y complétalo:

```bash
cp .env.example .env
# edita .env con tu TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
```

Variables principales (ver `.env.example` para todas):

| Variable | Descripción | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (obligatorio) | — |
| `TELEGRAM_CHAT_ID` | Chat destino (obligatorio) | — |
| `DIAN_TIPO_ATENCION` | `Videoatención` o `Presencial` | `Videoatención` |
| `DIAN_CATEGORIA` | Categoría del combo | `Devoluciones` |
| `DIAN_CIUDAD` | Ciudad | `Medellín` |
| `POLL_HOUR` / `POLL_MINUTE` | Hora local de la consulta diaria | `8` / `0` |
| `TZ` | Zona horaria | `America/Bogota` |
| `HEADLESS` | `false` para ver el navegador (debug) | `true` |

## Uso

```bash
# Consulta única y sin enviar a Telegram (imprime lo que notificaría)
python -m dian_bot.main --dry-run

# Consulta única y notifica si corresponde
python -m dian_bot.main --once

# Deja el scheduler corriendo (L-V a la hora configurada)
python -m dian_bot.main
```

## Ejecución permanente en macOS (launchd)

Para que consulte automáticamente L-V sin dejar una terminal abierta, usa el
`launchd` incluido. Edita las rutas si tu proyecto no está en el mismo sitio:

```bash
cp launchd/com.dianbot.citas.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dianbot.citas.plist
# para detenerlo:
# launchctl unload ~/Library/LaunchAgents/com.dianbot.citas.plist
```

El plist lanza `python -m dian_bot.main --once` a las 08:00 de lunes a viernes.

## Ejecución en GitHub Actions (recomendado)

Corre L-V aunque tu equipo esté apagado, gratis y sin servidor.

1. Crea el repo en GitHub y haz push de este proyecto.
2. En el repo: **Settings → Secrets and variables → Actions → New repository secret**, crea:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Listo. El workflow `.github/workflows/dian.yml` corre L-V a las 13:00 UTC
   (08:00 `America/Bogota`). Puedes lanzarlo manualmente desde la pestaña
   **Actions → Consulta citas DIAN → Run workflow** (con opción `dry-run`).

El estado (para no re-notificar) se persiste entre corridas con `actions/cache`,
así que no se commitea al repo. El workflow `ci.yml` corre los tests en cada push.

> Nota sobre el cron: GitHub puede retrasar los cron programados varios minutos
> en horas pico. Para un chequeo diario es irrelevante. Si algún día cambia el
> horario de verano de tu zona, ajusta el `cron` en `dian.yml`.


## Tests

```bash
python -m pytest
```

Cubren la lógica de decisión (cuándo notificar), la persistencia de estado y la
detección de "sin disponibilidad" en los modales del sitio (con un fake de
Playwright, sin abrir navegador).

## Notas legales

Herramienta personal de **monitoreo de disponibilidad** (solo lectura). No
automatiza el agendamiento ni elude el reCAPTCHA. Respeta los términos de uso del
portal de la DIAN. La frecuencia por defecto es una consulta diaria por día hábil.

## Estructura

```
dian_bot/
  config.py     # carga y valida configuración (.env)
  scraper.py    # navegación Playwright + detección de disponibilidad
  state.py      # persistencia JSON + regla de diff/notificación
  notifier.py   # envío por Telegram
  main.py       # CLI (--once/--dry-run) + scheduler L-V
tests/          # tests de lógica pura y de detección de modales
launchd/        # agente para ejecución programada en macOS
```

## Mantenimiento

El sitio de la DIAN es una SPA propietaria (C-Media WebPlayer). Si cambian su
estructura, el scraper lanzará `ScrapeError` y verás el error en los logs sin
enviar notificaciones falsas. Los selectores clave (`[nombre='...']`,
`[pantalla='ModalError'|'ModalSinCitas']`) están centralizados en `scraper.py`.
```
