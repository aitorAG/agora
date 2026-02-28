#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.sql.gz>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

gunzip -c "$BACKUP_FILE" | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-agora_user}" -d "${POSTGRES_DB:-agora}"

echo "Restore completed from: $BACKUP_FILE"
