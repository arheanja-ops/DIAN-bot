# Organización AWS multi-cuenta — Plan maestro

> Estado: **propuesta ejecutable**, basada en el estado REAL verificado el
> 2026-09-12 vía AWS CLI. Cubre todos los proyectos, no solo DIAN-bot.
> **Premisa transversal: costo ~$0.** Todo lo aquí propuesto usa servicios sin
> costo o dentro del free tier; cada excepción se marca explícitamente.

---

## 1. Estado actual (verificado, no asumido)

- **Organization existente**: `o-k27om02vsy`, FeatureSet `ALL`, SCP habilitado.
- **UNA sola cuenta**: `786567028012` ("TaxOpsA", `taxopsa@gmail.com`), que es a
  la vez la **management account** (raíz/billing) **y** donde corren TODOS los
  workloads. ⚠️ Anti-patrón.
- **Sin OUs**. Única SCP: `FullAWSAccess` (o sea, sin guardrails).
- **IAM Identity Center (SSO)** activo: `jaime.admin` con `AdministratorAccess`.
- **CloudTrail**: `taxops-trail` (de TaxOps).

### Proyectos que YA conviven en esa cuenta (mezclados)

| Proyecto | Huella detectada |
|---|---|
| **TaxOps** | `taxops-api-prod`, `taxops-worker-prod` (Lambdas), buckets `taxops-job-artifacts-prod`, `taxops-renta-docs-prod`, `taxops11-tfstate`, SQS `taxops-jobs-prod`, Postgres en Neon, CloudTrail |
| **DIAN-bot** | `dianbot-scraper` (Lambda), API `dianbot-webhook`, `dianbot-tfstate`, EventBridge, SSM |
| **trip-coveñas** | `covenas-dashboard` (Lambda), API `covenas-dashboard-api`, bucket frontend |
| **investment-self** | `investment-self-dev` (Lambda), API `investment-self-dev-api`, `investment-self-tfstate` |

**Riesgo:** blast radius compartido (un error de IAM/Terraform puede cruzar
proyectos), facturación indistinguible por proyecto, y el OIDC provider de GitHub
es compartido (ya causó fricción al configurar DIAN-bot).

---

## 2. Objetivo y principios

Migrar a **una cuenta AWS por proyecto/entorno** bajo AWS Organizations, con:
- Aislamiento de blast radius y de facturación.
- Acceso unificado por SSO (sin llaves estáticas).
- Guardrails por SCP.
- Free tier **multiplicado** (cada cuenta trae su propio free tier).

Principios:
1. **La management account NO corre workloads.** Solo billing + org + SSO.
2. **Todo como código** (Terraform) y por PR.
3. **Mínimo privilegio** por proyecto.
4. **Gratis por defecto**; cualquier gasto se aprueba explícitamente.

---

## 3. Estructura objetivo

```
Root (o-k27om02vsy)
│
├── Management Account (786567028012)  ← SOLO billing/org/SSO/CloudTrail org
│     · NO workloads. Se "vacía" migrando TaxOps a su cuenta.
│
├── OU: Workloads
│    ├── taxops-prod          (nueva)
│    ├── taxops-dev           (nueva)
│    ├── dian-bot             (nueva)
│    ├── investment-self      (nueva)
│    ├── trip-covenas         (nueva)
│    └── kubefin / otros      (bajo demanda)
│
├── OU: Sandbox
│    └── labs                 (experimentos, LABS/, DevX-Terraform-Sandbox)
│
└── OU: Security
     └── log-archive          (CloudTrail org centralizado, opcional)
```

> **Costo de crear cuentas y OUs: $0.** Organizations no cobra. Consolidated
> billing agrupa todo bajo el mismo medio de pago sin fee.

---

## 4. Guardrails (SCPs) — gratis

Aplicadas a la OU `Workloads`:

1. **Region lock** — denegar todo fuera de `us-east-1` (evita gasto accidental y
   simplifica). Excepción: servicios globales (IAM, CloudFront, Route53).
2. **Denegar servicios caros por defecto** — EC2 familias grandes, RDS, NAT
   Gateway, Redshift, SageMaker, Elasticsearch. (Se habilitan por excepción y con
   aprobación consciente, porque rompen el "gratis".)
3. **Exigir tags** `Project` y `Owner` al crear recursos.
4. **Proteger la organización** — denegar `organizations:Leave`, cambios de
   billing y borrado de CloudTrail desde cuentas hijas.

En `Sandbox`: SCP más laxa pero con region lock y un **Budget de $1** que apaga
alarmas si algo se dispara.

---

## 5. Control de costos (para garantizar el "gratis")

- **AWS Budgets**: 1 budget de **$1/mes** por cuenta con alerta al 80% y 100%
  (email + opcional Telegram vía el mismo patrón del bot). Budgets: 2 gratis/cuenta.
- **Free Tier Alerts** activadas en la management account.
- **Cost Anomaly Detection** (gratis) a nivel organización.
- **Cost Explorer** consolidado: una vista, desglose por cuenta = por proyecto.
- Revisión mensual de 10 min.

> Lo único que hoy cuesta centavos: **ECR** por imágenes >500MB tras el año 1
> (~$0.10/mes por proyecto con imagen Docker). Mitigable con lifecycle policies
> (ya aplicada en DIAN-bot: máx 5 imágenes).

---

## 6. Acceso: IAM Identity Center (SSO)

- Una identidad (tú) → acceso a todas las cuentas eligiendo cuenta+rol al entrar.
- **Permission sets**:
  - `AdminAccess` → cuentas propias (tú).
  - `ReadOnly` → auditoría.
  - `Billing` → solo en management.
- Integra con el patrón `.envrc` que ya usas: cada proyecto exporta su
  `AWS_PROFILE` SSO (`AWS_PROFILE=dian-bot`, `=taxops-prod`, etc.).
- **Elimina las llaves estáticas.** Deploys por OIDC (como DIAN-bot).

---

## 7. Implementación por fases

### Fase 0 — Preparación (gratis, sin riesgo)
- [ ] Definir emails por cuenta: alias `aws+<proyecto>@tudominio` (Gmail/Outlook
      soportan `+`). Ej: `aws+dianbot@...`.
- [ ] Repo nuevo `aws-org` (Terraform) para gestionar org, OUs, SCPs, cuentas,
      SSO. Por PR, con OIDC.
- [ ] MFA en el root de la management account (obligatorio).

### Fase 1 — Fundación (gratis)
- [ ] Crear OUs: `Workloads`, `Sandbox`, `Security`.
- [ ] Definir permission sets en SSO.
- [ ] Aplicar SCPs base (region lock, deny servicios caros, tags, protección org).
- [ ] Budgets + Free Tier alerts + Cost Anomaly Detection.

### Fase 2 — Cuentas nuevas (gratis crear)
Crear vía Terraform `aws_organizations_account`. Orden sugerido por facilidad:
1. `dian-bot` (más fácil: casi stateless, ya es IaC).
2. `investment-self` (dev).
3. `trip-covenas`.
4. `taxops-dev`.
5. `taxops-prod` (última: es producción, la más delicada).

### Fase 3 — Migración de workloads (ver sección 8)

### Fase 4 — Vaciar la management account
Una vez TaxOps migrado, la cuenta `786567028012` queda solo como
billing/org/SSO. Se retira cualquier workload residual.

---

## 8. Guías de migración por proyecto

Estrategia general: **recrear con Terraform en la cuenta destino** (no "mover"
recursos, que AWS no permite entre cuentas para la mayoría). Patrón:

1. `terraform init` con backend en el bucket tfstate de la **cuenta nueva**.
2. `terraform apply` recrea la infra (idéntica, otro account).
3. Migrar datos (si hay estado).
4. Cortar DNS/tráfico a la cuenta nueva.
5. Destruir en la cuenta vieja.

### 8.1 DIAN-bot (fácil — casi stateless)
- Recrear ECR + Lambda + EventBridge + API GW + SSM en cuenta `dian-bot`.
- Migrar: solo re-cargar secretos en el SSM de la cuenta nueva (`put-parameter`).
- El histórico (`/tmp`) es efímero, no requiere migración.
- Re-registrar el webhook de Telegram al nuevo API Gateway.
- Riesgo: bajo. Downtime: minutos.

### 8.2 investment-self / trip-coveñas (medio)
- Recrear Lambdas/APIs vía su Terraform apuntando a la cuenta nueva.
- Migrar buckets S3 con `aws s3 sync` cuenta-a-cuenta (bucket policy temporal
  cross-account, gratis).
- Actualizar DNS.

### 8.3 TaxOps (delicado — PRODUCCIÓN)
Requiere **ventana de mantenimiento** y plan dedicado. Puntos críticos:
- **Base de datos en Neon** (externa a AWS): no migra, solo se re-apunta
  `DATABASE_URL` desde la nueva cuenta. Cero downtime de datos.
- Buckets `taxops-*-prod`: `s3 sync` a la cuenta nueva.
- SQS `taxops-jobs-prod`: recrear; drenar la vieja antes de cortar.
- Lambdas (imagen): re-push a ECR de la cuenta nueva.
- CloudTrail: mover a la OU Security o recrear.
- DNS (`api.taxopsapp.com`, `app.taxopsapp.com`): cortar al final.
- **Prerrequisito de seguridad** (ver sección 9): migrar secretos a SSM/Secrets
  Manager ANTES de migrar (no arrastrar el anti-patrón actual).

---

## 9. Seguridad

### Hallazgos actuales (verificados)
- ⚠️ **TaxOps guarda secretos en variables de entorno de Lambda en texto plano**
  (`DATABASE_URL` con password de Neon, `SECRET_KEY`, `GROQ_API_KEY`,
  `GOOGLE_CLIENT_SECRET`, `BOOTSTRAP_SECRET`). Visibles con solo `lambda:GetFunction`.
  **Acción: migrar a SSM SecureString / Secrets Manager** (patrón ya implementado
  en DIAN-bot). Hacerlo antes o durante la migración de cuenta.
- OIDC provider de GitHub compartido entre proyectos → cada cuenta debe tener el
  suyo tras la migración.

### Estándar de seguridad por cuenta (objetivo)
- Secretos en **SSM SecureString** (gratis) o Secrets Manager (~$0.40/secreto/mes
  → preferir SSM para mantener gratis).
- Deploys por **OIDC**, sin llaves estáticas.
- IAM de **mínimo privilegio** acotado por prefijo de proyecto.
- **CloudTrail** a nivel organización (una traza para todas las cuentas) en la OU
  Security. CloudTrail: el primer trail de gestión es gratis.
- MFA en root; root sin uso operativo.
- SCPs como red de contención.

---

## 10. Guía operativa (día a día, post-migración)

```bash
# Entrar a un proyecto (direnv setea el perfil SSO)
cd ~/.../DIAN-bot          # .envrc -> export AWS_PROFILE=dian-bot
aws sso login --profile dian-bot   # si expiró

# Crear una cuenta nueva (desde el repo aws-org, por PR)
#   1. Añadir aws_organizations_account + email alias
#   2. PR -> plan -> merge -> apply (con aprobación)

# Ver costos por proyecto
aws ce get-cost-and-usage --time-period Start=...,End=... \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=LINKED_ACCOUNT

# Auditar secretos de una cuenta (que no haya env vars sensibles)
aws lambda list-functions --query 'Functions[].FunctionName' | ...
```

Reglas de oro:
- Nunca desplegar workloads en la management account.
- Todo cambio de infra por PR + aprobación.
- Antes de habilitar un servicio fuera del free tier, confirmar costo.

---

## 11. Herramienta: Organizations + Terraform (no Control Tower)

Se recomienda **Organizations + Terraform manual**, NO AWS Control Tower:
- Control Tower crea recursos que **rompen el gratis** (Config, CloudTrail
  multi-región, buckets de log) — puede costar varios USD/mes.
- Organizations + Terraform da el mismo aislamiento a **$0**, con control total.

Repo `aws-org` declara: organización, OUs, SCPs, cuentas, SSO permission sets.
Crear una cuenta = un PR.

---

## 12. Resumen de costos del plan

| Ítem | Costo |
|---|---|
| Organizations, OUs, SCPs, consolidated billing | $0 |
| Cuentas nuevas (N cuentas) | $0 |
| IAM Identity Center (SSO) | $0 |
| Budgets / Cost Anomaly / Free Tier alerts | $0 |
| CloudTrail (1 trail org de gestión) | $0 |
| Free tier | **× N cuentas** (más gratis total) |
| ECR imágenes Docker >500MB (tras año 1) | ~$0.10/mes por proyecto con imagen |
| **Total esperado** | **~$0 (centavos)** |

Lo que rompería el gratis (evitar salvo necesidad y aprobación): RDS, NAT
Gateway, ECS/Fargate/App Runner always-on, EC2, Control Tower.

---

## 13. Próximos pasos concretos

1. Confirmar dominio para emails de cuentas (`aws+proyecto@...`).
2. Crear repo `aws-org` (Terraform + CI/CD por PR, patrón DIAN-bot).
3. Fase 1 (fundación: OUs + SCPs + SSO + budgets).
4. Migrar `dian-bot` como piloto (el más fácil) → validar el patrón end-to-end.
5. Migrar el resto por prioridad; TaxOps al final con ventana.
6. Vaciar y blindar la management account.

> Este documento se versiona en el repo. La ejecución real de cada fase requiere
> confirmación explícita (crea/mueve recursos), siguiendo la premisa gratis y
> la política de aprobación.
