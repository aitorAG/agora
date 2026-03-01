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
cp ".env.prod copy.example" .env
nano .env
```

Variables mínimas que debes rellenar:

- `POSTGRES_PASSWORD`
- `DATABASE_URL` (coherente con el password)
- `DEEPSEEK_API_KEY`
- `AUTH_SEED_PASSWORD`
- `AGORA_DEPLOY_TARGET=vps`
- `AGORA_BASE_URL_VPS=https://<tu-dominio>` (o `http://85.17.246.141` temporal)

Para admin bootstrap (creado automáticamente incluso si recreas DB):

- `AUTH_SEED_USERNAME=admin`
- `AUTH_SEED_PASSWORD=4dmin` (cámbiala en producción)
- `AUTH_SEED_ROLE=admin`

Opcional observabilidad:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (si lo dejas vacío se autocalcula)

## 4. Levantar stack de producción

```bash
./deploy/up.sh
```

En Windows (PowerShell, para pruebas locales):

```powershell
.\deploy\up.ps1
```

Comprobar salud:

```bash
./deploy/healthcheck.sh
```

Logs:

```bash
./deploy/logs.sh
```

Parar stack:

```bash
./deploy/down.sh
```

## 5. Observabilidad en servidor (Langfuse)
Con `./deploy/up.sh` se levanta también observabilidad y se autocalculan:

- `NEXTAUTH_URL`
- `LANGFUSE_HOST`

en función de:

- `AGORA_DEPLOY_TARGET=local|vps`
- `AGORA_BASE_URL_LOCAL`
- `AGORA_BASE_URL_VPS`

Acceso:
- Usuario admin autenticado en Agora: `https://<tu-dominio>/admin/observability/`
- Usuario no admin: `403`

## 6. TLS/HTTPS

El archivo `nginx/nginx.prod.conf` está preparado para proxy vía autorización admin (`/authz/admin`).  
En producción real debes activar HTTPS (Let's Encrypt con certbot o usar Caddy).

## 7. Backups de base de datos

Crear backup:

```bash
./deploy/backup_db.sh
```

Restaurar backup:

```bash
./deploy/restore_db.sh /ruta/al/backup.sql.gz
```

## 8. Actualización del servicio

Linux:

```bash
git pull
./deploy/up.sh
```

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
