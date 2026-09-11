# DIAN Bot — Documentación completa

Monitor serverless de citas de la DIAN con notificación y comandos por Telegram.
Este documento consolida **todo** lo construido e investigado.

---

## 1. Qué hace

- **Monitoreo automático** (cron): revisa disponibilidad de citas de **devolución
  de IVA** y avisa por Telegram cuando aparecen. **Lunes a Viernes, 7:00–17:00
  (America/Bogota), cada 10 minutos.**
- **Comandos a demanda** (24/7) por Telegram:
  - `/consultar` — revisa YA citas de devolución IVA.
  - `/consultar <categoría>` — revisa otra categoría (rut, aduanas, cobranzas,
    recaudo, defensoria, conferencias, naf, inconsistencias).
  - `/categorias` — lista lo consultable.
  - `/estado` — última consulta.
  - `/ayuda` — ayuda.
- **Solo notifica**: no agenda ni resuelve el reCAPTCHA (eso lo hace el usuario
  con el enlace que envía el bot).
- **Multi-ciudad**: reporta cualquier ciudad con cupo, no solo una.

## 2. Arquitectura (serverless en AWS, ~$0/mes)

```
                 EventBridge Scheduler (L-V 7-17h)
                          │  (cron)
                          ▼
Telegram  ──webhook──►  API Gateway ──►  Lambda (dianbot-scraper)
  ▲                                        │  Playwright + Chromium (imagen Docker, arm64)
  │                                        │  router: EventBridge=scrape · API GW=comando
  └────────── notificación ◄───────────────┘
                                           │ lee secretos
                                           ▼
                                   SSM Parameter Store (SecureString)
```

- **Lambda** con imagen de contenedor (Playwright trae Chromium). arm64/Graviton,
  3008 MB, timeout 120s. Un solo artefacto sirve para cron y webhook (router por
  tipo de evento en `lambda_handler.py`).
- **EventBridge Scheduler**: cron `cron(0/10 7-16 ? * MON-FRI *)` tz America/Bogota.
- **API Gateway HTTP**: recibe el webhook de Telegram (`POST /telegram`),
  validado con secret token.
- **SSM Parameter Store**: token, chat_id y webhook secret cifrados. La Lambda
  los lee en runtime (nunca en env plano).
- **`/consultar`** responde al instante y auto-invoca la Lambda async para hacer
  el scrape sin exceder el timeout del webhook.

### Flags de Chromium en Lambda
Lambda no tiene GPU, dbus ni `/dev/shm` usable, y solo `/tmp` es escribible. Se
lanzan con `--single-process --disable-gpu --disable-dev-shm-usage` etc. y
`HOME=/tmp`, `XDG_CACHE_HOME=/tmp`. Sin esto, Chromium aborta.

## 3. Cómo funciona el scraper

Sitio: `https://agendamiento.dian.gov.co/` (SPA "C-Media WebPlayer" sobre ASP.NET).
Flujo real (verificado):
1. Aceptar modal de tratamiento de datos.
2. Tarjeta "Agendar cita" → PasoUno.
3. Cascada: `TipoPersona` → `TipoAtencion` → `Categorias`.
4. El combo **`Servicios`** es un `<select>` cuyas opciones son los trámites con
   cupo AHORA (cada opción puede incluir la ciudad). Se leen todas.
5. Sin cupos → modal "No se encontraron especialidades" → no notifica.

Robustez: navegación con reintento; timeouts → `ScrapeError` (no rompe, en modo
`always` avisa "no pude verificar"); selectores centralizados; esperas activas
(`wait_for_selector`) para tolerar la SPA lenta en Lambda.

## 4. Infraestructura como código (Terraform)

Carpeta `infra/`. Recursos (prefijo `dianbot-*`, cuenta `786567028012`, us-east-1):
- `aws_ecr_repository.scraper`, lifecycle (5 imágenes)
- `aws_lambda_function.scraper` + log group (14d)
- `aws_scheduler_schedule.poll` (cron L-V 7-17h)
- `aws_apigatewayv2_*` (webhook) + `aws_lambda_permission`
- `aws_ssm_parameter.*` (token, chat_id, webhook_secret)
- `aws_iam_role.lambda` (logs + leer SSM + self-invoke)
- `aws_iam_role.github_deploy` + OIDC (deploy sin llaves)
- Backend: S3 `dianbot-tfstate-786567028012` + lock DynamoDB `dianbot-tflock`

## 5. CI/CD (GitHub Actions)

Regla: **todo por PR; el merge a `main` dispara el deploy.**

| Workflow | Disparo | Qué hace |
|---|---|---|
| `ci.yml` | push/PR | tests (rápidos, sin navegador) |
| `infra.yml` | PR / merge | `plan` en PR; `apply` en merge **con aprobación** (env `infra-apply`) |
| `app.yml` | merge (cambios de código) | build arm64 (QEMU) → push ECR → update Lambda (env `production`) |
| `dian.yml` | manual | legacy; el cron fue reemplazado por la Lambda |

- **OIDC**: los workflows asumen `dianbot-github-deploy` sin llaves estáticas.
- **Environments** `production` e `infra-apply` con *required reviewers* → deploy
  y apply piden aprobación manual.
- **Borrado de rama tras merge** activado.
- Imagen para Lambda: `--provenance=false` (manifiesto Docker v2, no OCI).

## 6. Catálogo DIAN (qué se puede consultar)

Ver `docs/CATALOGO-DIAN.md`. Resumen: el sistema de **citas** cubre RUT, Aduanas,
Cobranzas, Recaudo, Devoluciones, Conferencias, Autogestión NAF, Defensoría —
todo monitoreable/consultable por el bot. **Descargar facturas/XML, RUT,
declaraciones NO son citas**: viven en Muisca/catalogo-vpfe y requieren login con
credenciales fiscales — módulo separado a futuro (no abordado).

## 7. Seguridad

- Secretos en SSM SecureString; nunca en código ni env plano.
- Webhook validado con secret token (rechaza spoofing con 403).
- Deploy con OIDC (sin llaves estáticas). IAM de mínimo privilegio acotado a
  `dianbot-*`.
- `.env`, `.envrc`, state y logs en `.gitignore`.

## 8. Desarrollo local

```bash
./scripts/setup.sh                 # venv + deps + Chromium + .env
cp .envrc.example .envrc && direnv allow
./scripts/run.sh --dry-run         # consulta sin notificar
./scripts/test.sh                  # 24 tests
```
Ver `docs/DIRENV-SETUP.md`.

## 9. Operación

```bash
# Rotar secretos
aws ssm put-parameter --name /dianbot/telegram_bot_token --type SecureString --value "<T>" --overwrite

# Registrar/ver webhook
./scripts/set-webhook.sh info
./scripts/set-webhook.sh set <URL> <SECRET>

# Ver logs
aws logs tail /aws/lambda/dianbot-scraper --follow
```

## 10. Roadmap / pendientes

- **Generalizar cron a multi-watch** (hoy el cron solo hace devolución IVA; los
  comandos ya consultan cualquier categoría).
- **Integración con TaxOps**: TaxOps ya vive en AWS (API `api.taxopsapp.com`,
  frontend `app.taxopsapp.com`, Postgres/Neon, Lambda+SQS). El chat del bot se
  integraría vía la API de TaxOps. Pendiente de diseño.
- **Módulo transaccional** (descargar facturas/XML): requiere login fiscal —
  proyecto separado con bóveda de credenciales.
- **Migración a cuenta AWS dedicada** `dian-bot` (ver `docs/AWS-ORG-PLAN.md`):
  hoy comparte cuenta con TaxOps, lo que causó fricciones (OIDC compartido).

## 11. Nota de seguridad sobre la cuenta (acción recomendada)

La cuenta comparte recursos con TaxOps. Se observó que **TaxOps guarda sus
secretos en variables de entorno de Lambda en texto plano** (DB, API keys). Se
recomienda migrarlos a SSM/Secrets Manager (mismo patrón que este bot). No
modificado aquí por estar fuera del alcance del proyecto DIAN-bot.

## 12. Índice de documentos

- `README.md` — inicio rápido y uso.
- `docs/DOCUMENTACION-COMPLETA.md` — este documento.
- `docs/CATALOGO-DIAN.md` — catálogo de trámites DIAN.
- `docs/AWS-ORG-PLAN.md` — plan de organización multi-cuenta AWS.
- `docs/DIRENV-SETUP.md` — entorno local con direnv.
- `infra/README.md` — detalle de infraestructura y CI/CD.
