# Plan de organización multi-cuenta AWS

> Estado: **propuesta** — pendiente de validar contra la cuenta real (requiere
> `aws sso login` para inspeccionar Organizations). Autor: sesión de plataforma
> 2026-09-11.

## Objetivo

Pasar de "una cuenta AWS que hace de todo" a una **estructura multi-cuenta bajo
AWS Organizations**, con una cuenta por proyecto, aislamiento de blast radius,
facturación separada por proyecto y un modelo de acceso centralizado.

Premisa dura del dueño: **costo ~$0**. AWS Organizations, SSO (IAM Identity
Center), SCPs y consolidated billing **no tienen costo**. El gasto solo aparece
por los recursos que cada proyecto consuma (y buscamos que caigan en free tier).

## Estado actual (VALIDADO 2026-09-11 vía AWS CLI)

- **Organization YA existe:** `o-k27om02vsy`, FeatureSet `ALL`, SCPs habilitados.
  No hay que crearla.
- **Management account = `786567028012` ("TaxOpsA", `taxopsa@gmail.com`)** — es la
  ÚNICA cuenta de la org, y ahí vive TaxOps-11 a la vez que hace de raíz.
  ⚠️ Anti-patrón confirmado: workload de producción en la management account.
- **Solo la raíz `r-j9f1`**, sin OUs ni SCPs aplicadas todavía.
- IAM Identity Center (SSO) ya activo: `jaime.admin` con `AdministratorAccess`.

### Implicación
- "Activar Organizations" se OMITE (ya está).
- Sacar TaxOps a una cuenta hija es deseable pero es migración de producción →
  plan aparte, no ahora.
- **DIAN-bot** se despliega temporalmente en la cuenta actual (decisión del
  dueño), con salvaguardas: prefijo `dianbot-*`, tags `Project=dian-bot`,
  Terraform state aislado. Al existir la cuenta hija `dian-bot`, se migra
  (trivial: casi stateless).

## Proyectos candidatos a cuenta propia

Del inventario del equipo (carpeta `arheanja/`):

| Proyecto | Cuenta propuesta (alias) | Prioridad | Notas |
|---|---|---|---|
| TaxOps-11 | `taxops-prod` (+ `taxops-dev`) | Alta | Ya en AWS; separar prod/dev |
| investment-self-saas | `investment-self` | Media | SaaS activo |
| matchstack | `matchstack` | Media | Tiene infra/ |
| DIAN-bot | `dian-bot` | Baja | Hoy en taxops; migrar luego |
| kubefin | `kubefin` | Media | FinOps K8s |
| trip-coveñas | `trip-covenas` | Baja | Lambda + infra |
| tesla-tracker | `tesla-tracker` | Baja | Dockerizado |

> No todos necesitan cuenta desde el día 1. La estructura se crea una vez y las
> cuentas se van sumando conforme cada proyecto lo amerite.

## Estructura de Organization propuesta

```
Root (Organization)
│
├── Management Account (SOLO facturación + org + SSO; NADA de workloads)
│     · Aquí NUNCA se despliegan recursos de proyectos.
│     · Consolidated billing de todas las cuentas hijas.
│
├── OU: Workloads
│    ├── taxops-prod
│    ├── taxops-dev
│    ├── investment-self
│    ├── matchstack
│    ├── dian-bot
│    ├── kubefin
│    └── ...
│
├── OU: Sandbox
│    └── labs / experimentos (LABS/, DevX-Terraform-Sandbox)
│
└── OU: Security (opcional, futuro)
     └── log-archive / audit (CloudTrail centralizado)
```

### Principio clave: la management account no corre workloads

Hoy `taxops-admin` mezcla facturación + workloads de TaxOps. **Riesgo alto**: si
esa cuenta es la raíz de la org, un error ahí afecta a todas. El plan separa:
la cuenta raíz solo administra; TaxOps se mueve a su propia cuenta hija
`taxops-prod`.

## Modelo de acceso: IAM Identity Center (SSO)

- **Una sola identidad** (tu usuario) con acceso a todas las cuentas vía SSO,
  eligiendo cuenta+rol al entrar. Reemplaza los access keys estáticos.
- Permission sets:
  - `AdminAccess` → cuentas propias (tú).
  - `ReadOnly` → auditoría.
- Encaja con el patrón `.envrc` actual: cada proyecto exporta su
  `AWS_PROFILE` apuntando al perfil SSO de su cuenta
  (`export AWS_PROFILE=dian-bot`, `=matchstack`, etc.).

## Guardrails: SCPs (Service Control Policies) — gratis

Aplicadas a la OU `Workloads` para blindar el "todo gratis":

- **Denegar regiones** distintas de `us-east-1` (evita gasto accidental en otras
  regiones y simplifica).
- **Denegar servicios caros** por defecto (ej. `ec2` de familias grandes, `rds`
  instancias grandes, `sagemaker`) salvo excepción explícita por cuenta.
- **Exigir tags** `Project` y `Owner` en creación de recursos.
- **Denegar** salida de la Organization / cambios de billing desde cuentas hijas.

## Control de costos (premisa "gratis")

- **AWS Budgets**: un budget de $1 con alerta al 80% por cada cuenta → te avisa
  por email/Telegram si algo se sale del free tier. (Budgets: 2 gratis por
  cuenta).
- **Cost Anomaly Detection**: gratis, alerta gastos raros.
- **Free tier alerts** activadas en la management account.
- Revisar mensualmente el Cost Explorer consolidado (una vista, todas las cuentas).

## Fases de implementación

### Fase 0 — Validación (requiere `aws sso login`)
- Confirmar si `taxops-admin` ya es management account o cuenta suelta.
- Inventariar recursos actuales de TaxOps (para no romper nada al reorganizar).

### Fase 1 — Fundación de la Organization (gratis)
- Activar AWS Organizations (si no está) en la cuenta management.
- Activar IAM Identity Center (SSO).
- Crear OUs: `Workloads`, `Sandbox`.
- Aplicar SCPs base (región lock + tags obligatorios + deny billing changes).
- Configurar Budgets + alertas de free tier.

### Fase 2 — Cuentas nuevas bajo demanda (gratis crear)
- Crear cuentas hijas vía Organizations (email por cuenta:
  `aws+<proyecto>@tudominio`). Empezar por las de prioridad alta.
- Cada cuenta con su permission set SSO y su `.envrc` (`AWS_PROFILE`).

### Fase 3 — Migración de workloads existentes
- **TaxOps**: mover de la cuenta actual a `taxops-prod`. Es la migración más
  delicada (tiene prod). Estrategia: recrear infra vía Terraform en la cuenta
  nueva, migrar datos, cortar DNS. Plan detallado aparte antes de tocar.
- **DIAN-bot**: recrear con Terraform (ya nace como IaC) en cuenta `dian-bot`.
  Trivial porque es stateless salvo el histórico.
- Demás proyectos: conforme se activen.

### Fase 4 — Todo como código
- Un repo `aws-org` con Terraform que declara la Organization, OUs, SCPs, SSO y
  las cuentas. La creación de una cuenta nueva = un PR.

## Herramienta recomendada para gestionar esto

- **Terraform** con el provider `aws` + módulo `aws-organizations`, o
- **Control Tower** (más opinado, landing zone automática) — pero Control Tower
  crea recursos que pueden salir del free tier (config, cloudtrail). Para
  "gratis absoluto", **Organizations + Terraform manual** es más barato que
  Control Tower.

## Riesgos y decisiones pendientes

1. **¿Emails por cuenta?** Cada cuenta AWS necesita un email único. Recomiendo
   alias `aws+proyecto@tudominio` (Gmail soporta `+`).
2. **Migrar TaxOps es delicado** (producción). No se hace sin un plan de
   migración dedicado y ventana de mantenimiento.
3. **MFA en la root** de la management account: obligatorio, guardar con cuidado.
4. Confirmar que el "todo gratis" aguanta: la mayoría del free tier es **por
   cuenta**, así que multi-cuenta incluso **multiplica** el free tier disponible
   (cada cuenta nueva trae su propio free tier de Lambda, DynamoDB, etc.).

## Beneficio neto

- Aislamiento real por proyecto (un error no cruza cuentas).
- Facturación y free tier por proyecto (más free tier total).
- Acceso unificado por SSO, sin keys estáticas.
- Base para que cada proyecto (incluido este bot) crezca sin pisar a los demás.
