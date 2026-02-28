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

Opcional observabilidad:

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`

## 4. Levantar stack de producción

```bash
./deploy/up.sh
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

Prepara la red compartida entre stacks (idempotente):

```bash
docker network create agora_edge || true
```

```bash
docker compose -f observability-platform/docker-compose.langfuse.yml up -d
```

### Exponer Langfuse públicamente con usuario/contraseña

1. Crea un subdominio `obs.<tu-dominio>` apuntando al VPS.
2. En `.env`, configura:

```bash
NEXTAUTH_URL=https://obs.<tu-dominio>
```

3. Crea el fichero de credenciales para Nginx:

```bash
cp nginx/.htpasswd.example nginx/.htpasswd
printf "admin:$(openssl passwd -apr1 'cambia_esta_password')\n" > nginx/.htpasswd
```

4. Levanta o reinicia el stack principal (Nginx):

```bash
./deploy/up.sh
```

Con esto, Langfuse queda accesible en `https://obs.<tu-dominio>` con Basic Auth y sin exponer `3000` públicamente.

## 6. TLS/HTTPS

El archivo `nginx/nginx.prod.conf` está preparado para proxy HTTP básico.  
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

```bash
git pull
./deploy/up.sh
```

## 9. Checklist de hardening mínimo

- No exponer `5432`, `6379`, `8123`, `9000`, etc. públicamente.
- Usar contraseñas fuertes para DB y auth seed.
- Activar firewall (`ufw`) permitiendo sólo `22/80/443`.
- Configurar fail2ban y rotación de logs.
- Programar backups (cron diario).
