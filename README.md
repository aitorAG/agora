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
- `observability-platform/`: documentación y assets de despliegue de observabilidad.
- `nginx/`: configuración de reverse proxy para exponer servicios.
- `docker-compose.yml`: infraestructura local (Postgres + Langfuse stack).

## Arranque rápido

1. Infraestructura:
```bash
docker compose up -d
```

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
