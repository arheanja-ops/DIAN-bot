# direnv: entorno automático de este proyecto

**Qué resuelve:** al entrar a `DIAN-bot/`, [direnv](https://direnv.net/) activa
automáticamente el virtualenv, carga las variables de `.env` (token de Telegram,
filtros DIAN) y aísla la config de GitHub CLI de este proyecto. Al salir de la
carpeta, todo se desactiva — no interfiere con otras terminales ni proyectos.

A diferencia de un `.envrc` con secretos hardcodeados, aquí **los secretos viven
solo en `.env`** (ignorado por git). El `.envrc` únicamente los *carga*.

## Qué configura el `.envrc`

| Acción | Detalle |
|---|---|
| Activa `.venv` | `source .venv/bin/activate` si existe |
| Carga `.env` | `dotenv .env` (token de Telegram, `DIAN_*`, etc.) |
| Aísla `gh` | `GH_CONFIG_DIR=$HOME/.config/gh-dianbot` (cuenta del repo, no la de trabajo) |

## Requisitos

```bash
brew install direnv
# agrega el hook a tu shell (una sola vez):
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc   # o bash/fish equivalente
```

## Primera vez

```bash
cp .envrc.example .envrc
direnv allow           # autoriza la ejecución del .envrc
```

Por seguridad, direnv **nunca ejecuta un `.envrc` nuevo o modificado sin
autorización explícita**. Si lo editas, volverá a pedir `direnv allow` — es
intencional.

## Verificar

```bash
cd DIAN-bot
# direnv: loading .../DIAN-bot/.envrc
echo "$VIRTUAL_ENV"          # → .../DIAN-bot/.venv
echo "$GH_CONFIG_DIR"        # → ~/.config/gh-dianbot
python -c "import os; print(bool(os.getenv('TELEGRAM_BOT_TOKEN')))"  # → True si .env está listo
```

## GitHub CLI aislada

La primera vez, autentica `gh` en el directorio aislado del proyecto:

```bash
./scripts/gh-login.sh
```

Esto abre el navegador y guarda la sesión en `$GH_CONFIG_DIR`, separada de tu
`gh` de trabajo o de otros proyectos.

## Troubleshooting

| Síntoma | Causa | Fix |
|---|---|---|
| `$VIRTUAL_ENV` vacío dentro de la carpeta | Falta el hook, o no hay `.venv` | `source ~/.zshrc` / `./scripts/setup.sh` |
| `.envrc is blocked` | Primera vez o el archivo cambió | `direnv allow` |
| `gh` usa la cuenta equivocada | `GH_CONFIG_DIR` no cargó | verifica que estás dentro de `DIAN-bot/` y corriste `direnv allow` |
