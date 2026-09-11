# Infraestructura (Terraform) y CI/CD

El monitoreo corre en **AWS Lambda** (imagen Docker con Playwright+Chromium),
disparado por **EventBridge Scheduler** de **Lunes a Viernes, 07:00–17:00
America/Bogota, cada 10 min**. Todo en la cuenta `786567028012` (us-east-1),
con prefijo `dianbot-*`.

## Recursos (en `infra/`)

| Recurso | Qué es |
|---|---|
| `aws_ecr_repository.scraper` | Imagen del scraper (`dianbot-scraper`) |
| `aws_lambda_function.scraper` | Función `dianbot-scraper` (arm64, 3008 MB, 120s) |
| `aws_scheduler_schedule.poll` | Cron L-V 7am-5pm cada 10 min |
| `aws_ssm_parameter.*` | Token y chat_id de Telegram (SecureString) |
| `aws_iam_role.lambda` | Rol de la Lambda (logs + leer SSM) |
| `aws_iam_role.github_deploy` | Rol que asumen los Actions vía OIDC |

Los **secretos NO están en el código ni en env plano**: viven en SSM Parameter
Store cifrados, y la Lambda los lee en tiempo de ejecución.

### Backend de state
S3 `dianbot-tfstate-786567028012` + lock DynamoDB `dianbot-tflock`.

## CI/CD (dos pipelines separados)

Regla: **todo entra por PR; el merge a `main` dispara el deploy.**

### `app.yml` — despliegue de la app
- Se dispara al mergear a `main` cambios en `dian_bot/`, `Dockerfile`, etc.
- Build+push de la imagen a ECR y `update-function-code` de la Lambda.
- Usa OIDC (sin llaves estáticas).

### `infra.yml` — Terraform
- En **PR**: `fmt` + `validate` + `plan` (se comenta el plan).
- En **merge a main**: `apply` **con aprobación manual** (GitHub Environment
  `infra-apply` con required reviewers).

### `ci.yml` — tests
- Corre en cada push/PR. Rápido, sin navegador.

### `dian.yml` — legacy (manual)
- El cron automático fue **reemplazado por la Lambda**. Queda solo para
  ejecución manual puntual.

## Cargar/rotar secretos

```bash
aws ssm put-parameter --name /dianbot/telegram_bot_token --type SecureString \
  --value "<TOKEN>" --overwrite --region us-east-1
aws ssm put-parameter --name /dianbot/telegram_chat_id --type SecureString \
  --value "<CHAT_ID>" --overwrite --region us-east-1
```

## Configuración pendiente en GitHub (una vez)
- Crear Environments `production` y `infra-apply` con **required reviewers**
  (para que el apply/deploy exija tu aprobación).
- Secrets ya cargados: `AWS_DEPLOY_ROLE_ARN`, `AWS_INFRA_ROLE_ARN`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Nota sobre la cuenta
Esto vive hoy en la cuenta de TaxOps (management account de la org). El OIDC
provider de GitHub ya existía (compartido). Ver `docs/AWS-ORG-PLAN.md` para la
migración futura a una cuenta `dian-bot` dedicada.
