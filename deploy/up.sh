#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash "$ROOT_DIR/deploy/resolve_env.sh"
docker network create agora_edge >/dev/null 2>&1 || true

docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.langfuse.yml up -d
docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml up -d --build

docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml ps
docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.langfuse.yml ps
