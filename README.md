# Agora Monorepo

Estructura principal:

```text
agora/
  docker-compose.yml
  engine/
  frontend/
  observability-platform/
  nginx/
```

## Componentes

- `engine/`: backend (API, motor conversacional, tests, migraciones, plantillas de juego).
- `frontend/`: assets estáticos de la UI web (`frontend/static`).
- `observability-platform/`: servicio de observabilidad (ingesta y agregados de telemetría).
- `nginx/`: configuración de reverse proxy para exponer servicios.
- `docker-compose.yml`: infraestructura local (Postgres + telemetry service).

## Arranque rápido

1. Infraestructura:
```bash
docker compose up -d
```

Config mínima:

- cambia `AGORA_DEPLOY_TARGET` a `local` o `vps`
- en `vps`, define `AGORA_PUBLIC_URL`
- define `POSTGRES_PASSWORD`, `DEEPSEEK_API_KEY`, `AUTH_SECRET_KEY`, `AUTH_SEED_PASSWORD`, `TELEMETRY_INGEST_KEY`

El resto (URL pública derivada, URL de observabilidad, `DATABASE_URL`, `TELEMETRY_ENDPOINT`) se calcula automáticamente.

Archivo base recomendado:

- usa `.env.example` como plantilla única
- `deploy/up.*` crea automáticamente un backup previo de la base de datos si detecta un `postgres` ya en ejecución

2. Backend:
```bash
cd engine
poetry install
poetry run agora
```

Para API:
```bash
cd engine
poetry run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

## Despliegue en VPS

Guía paso a paso (clonar repo + configurar + levantar):

- [VPS_DEPLOY.md](./VPS_DEPLOY.md)
