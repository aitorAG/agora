# Despliegue En VPS (Clonando El Repo)

Sí: el despliegue está pensado para hacerse **clonando este repositorio en el VPS**.

## 1. Requisitos del VPS

- Ubuntu 22.04+ (recomendado 24.04)
- Docker + Docker Compose plugin
- Git
- Dominio apuntando al VPS (A record)
- Puertos abiertos: `80` (y `443` cuando actives TLS)

Instalación base:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Reinicia sesión para que aplique el grupo `docker`.

## 2. Clonar repo

```bash
git clone <TU_REPO_URL> agora
cd agora
```

## 3. Preparar variables de entorno

```bash
cp .env.example .env
nano .env
```

`.env.example` es la plantilla canónica del repo.

### `.env` mínimo recomendado y de dónde sale cada valor

Variables obligatorias:

- `AGORA_DEPLOY_TARGET=vps`
  - Lo defines tú.
  - En tu PC usa `local`; en el VPS usa `vps`.
- `AGORA_PUBLIC_URL=https://<tu-dominio>`
  - Sale de tu dominio público.
  - Si todavía no tienes dominio, usa temporalmente `http://85.17.246.141`.
- `POSTGRES_PASSWORD=<password fuerte>`
  - Lo defines tú.
  - Recomendado: `openssl rand -hex 24`.
- `DEEPSEEK_API_KEY=<tu clave>`
  - Sale del panel de DeepSeek.
- `AUTH_SEED_USERNAME=admin`
  - Lo defines tú.
- `AUTH_SEED_PASSWORD=<password admin fuerte>`
  - Lo defines tú.
  - Recomendado: no dejar `4dmin` en producción.
- `AUTH_SEED_ROLE=admin`
  - Lo defines tú.
- `TELEMETRY_ENABLED=true`
  - Lo defines tú.
- `TELEMETRY_INGEST_KEY=<clave fuerte>`
  - Lo defines tú.
  - Recomendado: `openssl rand -hex 24`.

Variables opcionales pero recomendadas:

- `DATABASE_URL`
  - Solo si quieres sobrescribir la BBDD interna y apuntar a una externa.
  - Si no, se calcula automáticamente.
- `TELEMETRY_ENDPOINT`
  - Solo si quieres sobrescribir el endpoint de ingesta.
  - Si no, se calcula automáticamente.
- `DEEPSEEK_INPUT_COST_PER_1M_TOKENS`
- `DEEPSEEK_OUTPUT_COST_PER_1M_TOKENS`
  - Salen de la tabla de pricing del proveedor LLM.
  - Se usan para calcular coste en el dashboard.

Este repo usa solo `.env` como fuente de configuración.  
`deploy/up.sh` genera un `.env.runtime` derivado y saneado antes de levantar contenedores, pero no consulta ningún gestor externo de secretos.

### Copiar tu `.env` local al VPS

Ejecuta este comando en tu **ordenador local** (no dentro de la sesión SSH):

```bash
scp "C:\Users\PC\Proyectos\Agora\.env" st4bros@85.17.246.141:/srv/agora/.env
```

En la VPS, verifica:

```bash
cd /srv/agora
ls -l .env
```

Para escribir/actualizar variables directamente en `.env`:

```bash
cd /srv/agora
grep -q '^AGORA_DEPLOY_TARGET=' .env \
  && sed -i 's/^AGORA_DEPLOY_TARGET=.*/AGORA_DEPLOY_TARGET=vps/' .env \
  || echo 'AGORA_DEPLOY_TARGET=vps' >> .env

grep -q '^TELEMETRY_INGEST_KEY=' .env \
  && sed -i 's/^TELEMETRY_INGEST_KEY=.*/TELEMETRY_INGEST_KEY=change_me_ingest_key/' .env \
  || echo 'TELEMETRY_INGEST_KEY=change_me_ingest_key' >> .env

grep -q '^AGORA_PUBLIC_URL=' .env \
  && sed -i 's#^AGORA_PUBLIC_URL=.*#AGORA_PUBLIC_URL=http://85.17.246.141#' .env \
  || echo 'AGORA_PUBLIC_URL=http://85.17.246.141' >> .env
```

Variables mínimas que debes rellenar:

- `POSTGRES_PASSWORD`
- `DEEPSEEK_API_KEY`
- `AUTH_SEED_PASSWORD`
- `AGORA_DEPLOY_TARGET=vps`
- `AGORA_PUBLIC_URL=https://<tu-dominio>` (o `http://85.17.246.141` temporal)
- `TELEMETRY_ENABLED=true`
- `TELEMETRY_INGEST_KEY=<clave fuerte>`

Para admin bootstrap (creado automáticamente incluso si recreas DB):

- `AUTH_SEED_USERNAME=admin`
- `AUTH_SEED_PASSWORD=4dmin` (cámbiala en producción)
- `AUTH_SEED_ROLE=admin`

## 4. Levantar stack de producción

```bash
bash ./deploy/up.sh
```

Qué hace:

- Si ya existe un `postgres` en ejecución, crea un backup previo en `backups/predeploy/`
- Genera `.env.runtime` a partir de `.env`
- Resuelve URLs según `AGORA_DEPLOY_TARGET`
- Valida que el entorno tenga las variables críticas necesarias antes de arrancar
- Levanta observabilidad
- Levanta backend + nginx

En Windows (PowerShell, para pruebas locales):

```powershell
.\deploy\up.ps1
```

Comprobar salud:

```bash
bash ./deploy/healthcheck.sh
```

Logs:

```bash
bash ./deploy/logs.sh
```

Parar stack:

```bash
bash ./deploy/down.sh
```

## 5. Observabilidad en servidor
Con `bash ./deploy/up.sh` se levanta también el servicio de telemetría.

en función de:

- `AGORA_DEPLOY_TARGET=local|vps`
- `AGORA_PUBLIC_URL` (solo en VPS)

Acceso:
- Usuario admin autenticado en Agora: `https://<tu-dominio>/admin/observability/`
- Usuario no admin: `403`

La telemetría muestra:

- tiempos por llamada
- tokens por llamada
- costes por llamada
- agregados por usuario, partida, turno y agente

## 6. TLS/HTTPS

El archivo `nginx/nginx.prod.conf` está preparado para proxy vía autorización admin (`/authz/admin`).  
En producción real debes activar HTTPS (Let's Encrypt con certbot o usar Caddy).

## 7. Backups de base de datos

Crear backup:

```bash
bash ./deploy/backup_db.sh
```

En Windows (PowerShell):

```powershell
.\deploy\backup_db.ps1
```

Restaurar backup:

```bash
bash ./deploy/restore_db.sh /ruta/al/backup.sql.gz
```

## 8. Actualización del servicio

Linux:

```bash
git pull
bash ./deploy/up.sh
```

### Forzar modo VPS y recrear servicios sin perder BBDD

En la VPS (`/srv/agora`):

```bash
# 1) Forzar target vps en .env
grep -q '^AGORA_DEPLOY_TARGET=' .env \
  && sed -i 's/^AGORA_DEPLOY_TARGET=.*/AGORA_DEPLOY_TARGET=vps/' .env \
  || echo 'AGORA_DEPLOY_TARGET=vps' >> .env

# 2) (Opcional) base URL pública
grep -q '^AGORA_PUBLIC_URL=' .env \
  && sed -i 's#^AGORA_PUBLIC_URL=.*#AGORA_PUBLIC_URL=https://<tu-dominio>#' .env \
  || echo 'AGORA_PUBLIC_URL=https://<tu-dominio>' >> .env

# 3) Regenerar servicios sin destruir datos (no usa down -v)
bash ./deploy/up.sh
```

Notas:
- `bash ./deploy/up.sh` recrea contenedores según cambios de imagen/env, manteniendo volúmenes.
- **No ejecutes** `docker compose down -v` en producción si quieres conservar PostgreSQL.
- Si cambias secrets en Infisical, basta con volver a ejecutar `bash ./deploy/up.sh`; regenerará `.env.runtime` y recreará contenedores sin borrar volúmenes.

Windows (PowerShell):

```powershell
git pull
.\deploy\up.ps1
```

## 9. Checklist de hardening mínimo

- No exponer `5432`, `6379`, `8123`, `9000`, etc. públicamente.
- Usar contraseñas fuertes para DB y auth seed.
- Activar firewall (`ufw`) permitiendo sólo `22/80/443`.
- Configurar fail2ban y rotación de logs.
- Programar backups (cron diario).
