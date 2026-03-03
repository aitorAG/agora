#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash "$ROOT_DIR/deploy/resolve_env.sh"
docker compose --env-file "$ROOT_DIR/.env.runtime" -f docker-compose.prod.yml logs -f --tail=200 "${@:-}" &
MAIN_PID=$!
docker compose --env-file "$ROOT_DIR/.env.runtime" -f observability-platform/docker-compose.telemetry.yml logs -f --tail=200 "${@:-}" &
OBS_PID=$!

trap 'kill "$MAIN_PID" "$OBS_PID" 2>/dev/null || true' EXIT INT TERM
wait "$MAIN_PID" "$OBS_PID"
