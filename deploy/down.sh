#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash "$ROOT_DIR/deploy/resolve_env.sh"
docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml down
docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.langfuse.yml down
