#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${1:-$ROOT_DIR/backups}"
mkdir -p "$OUT_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/agora_${TS}.sql.gz"

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-agora_user}" -d "${POSTGRES_DB:-agora}" \
  | gzip > "$OUT_FILE"

echo "Backup created: $OUT_FILE"
