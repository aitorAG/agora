# Infraestructura y Operación

## Alcance

Este documento describe la infraestructura actual de `Agora`, cómo arrancarla en local, cómo operarla y cómo diagnosticar incidencias frecuentes.

## Componentes desplegados

- **Aplicación Python** (entrypoint `main.py`)
  - Modo `terminal` (CLI)
  - Modo `api` (FastAPI + Uvicorn)
- **UI web estática** montada en `/ui` cuando `UI_TEST=true`
- **Persistencia DB-only** en PostgreSQL
- **PostgreSQL en Docker** (`docker-compose.yml`)
- **Templates estándar** en `game_templates/`
- **Sistema de logs** en carpeta `logs/`

## Variables de entorno operativas

Variables relevantes en `.env`:

- `INTERFACE_MODE=api|terminal`
- `UI_TEST=true|false`
- `AGORA_API_HOST`, `AGORA_API_PORT`
- `DATABASE_URL=postgresql://...` (obligatoria)
- `DEEPSEEK_API_KEY=...`

## Arquitectura runtime (alto nivel)

```mermaid
flowchart LR
  User[Usuario]
  UI[UI Browser /ui]
  API[FastAPI src/api]
  Engine[GameEngine src/core/engine.py]
  Provider[DatabasePersistenceProvider]
  Templates[game_templates]
  Pg[(PostgreSQL Docker)]

  User --> UI
  UI --> API
  API --> Engine
  Engine --> Provider
  Provider --> Pg
  API --> Templates
```

## Flujo de inicialización

```mermaid
flowchart TD
  Start[Iniciar app]
  ReadEnv[Leer .env]
  Db[DatabasePersistenceProvider]
  Migrate[Ejecutar migraciones]
  EnsureUser[Garantizar usuario fijo usuario]
  Boot[Aplicación lista]
  Fail[Abortar inicio con error]

  Start --> ReadEnv --> Db --> Migrate --> EnsureUser --> Boot
  Db -->|sin DATABASE_URL o driver/DB| Fail
```

## Arranque local (PostgreSQL en Docker)

1. Levantar base de datos:
   - `docker compose up -d`
2. Configurar en `.env`:
   - `DATABASE_URL=postgresql://agora_user:agora_pass@localhost:5432/agora`
3. Instalar driver en entorno Python:
   - `poetry add "psycopg[binary]"`
4. Arrancar app:
   - `poetry run agora`
5. Verificación:
   - La app debe iniciar solo si conexión y migración son correctas.

## Datos y almacenamiento

- **Partidas y usuarios**
  - Persisten en PostgreSQL (volumen Docker `agora_pg_data`)
- **Plantillas estándar**
  - Se leen desde `game_templates/<template_id>/`

## Operación diaria

- Ver estado de contenedores:
  - `docker compose ps`
- Ver logs de PostgreSQL:
  - `docker compose logs -f postgres`
- Parar DB:
  - `docker compose stop`
- Borrar DB y volumen:
  - `docker compose down -v`

## Troubleshooting

- **Error: `DATABASE_URL no configurada`**
  - Revisar `.env` y formato de URL.
- **Error: falta `psycopg`**
  - Ejecutar `poetry add "psycopg[binary]"`.
- **Puerto 5432 ocupado**
  - Cambiar mapeo en `docker-compose.yml` y ajustar `DATABASE_URL`.
- **Fallan migraciones al inicio**
  - Revisar conectividad y permisos del usuario DB.
- **UI en blanco**
  - Verificar `UI_TEST=true` y abrir `http://localhost:8000/ui/`.

## Referencias

- `README.md`
- `docker-compose.yml`
- `.env`
- `src/persistence/`
- `migrations/`
