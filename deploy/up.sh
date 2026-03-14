#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash "$ROOT_DIR/deploy/resolve_env.sh"
docker network create agora_edge >/dev/null 2>&1 || true

POSTGRES_CONTAINER_ID="$(docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml ps -q postgres 2>/dev/null || true)"
if [[ -n "$POSTGRES_CONTAINER_ID" ]]; then
  POSTGRES_RUNNING="$(docker inspect -f '{{.State.Running}}' "$POSTGRES_CONTAINER_ID" 2>/dev/null || echo false)"
  if [[ "$POSTGRES_RUNNING" == "true" ]]; then
    echo "Creating pre-deploy database backup..."
    if ! bash "$ROOT_DIR/deploy/backup_db.sh" "$ROOT_DIR/backups/predeploy"; then
      echo "Warning: pre-deploy database backup failed; continuing with deploy."
    fi
  fi
fi

docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.telemetry.yml up -d --build --remove-orphans
docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml up -d --force-recreate nginx

docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml ps
docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.telemetry.yml ps
