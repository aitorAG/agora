#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
RUNTIME_ENV_FILE="$ROOT_DIR/.env.runtime"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

TARGET_RAW="${AGORA_DEPLOY_TARGET:-local}"
TARGET="$(echo "$TARGET_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$TARGET" != "local" && "$TARGET" != "vps" ]]; then
  echo "Invalid AGORA_DEPLOY_TARGET='$TARGET_RAW'. Expected: local or vps."
  exit 1
fi

LOCAL_BASE="${AGORA_BASE_URL_LOCAL:-http://localhost}"
VPS_BASE="${AGORA_BASE_URL_VPS:-http://85.17.246.141}"

if [[ "$TARGET" == "vps" ]]; then
  RESOLVED_BASE_URL="$VPS_BASE"
else
  RESOLVED_BASE_URL="$LOCAL_BASE"
fi
RESOLVED_BASE_URL="${RESOLVED_BASE_URL%/}"
RESOLVED_LANGFUSE_URL="${RESOLVED_BASE_URL}/admin/observability"

EFFECTIVE_NEXTAUTH_URL="${NEXTAUTH_URL:-$RESOLVED_LANGFUSE_URL}"
EFFECTIVE_LANGFUSE_HOST="${LANGFUSE_HOST:-$RESOLVED_LANGFUSE_URL}"

awk '!(/^AGORA_RESOLVED_BASE_URL=/ || /^NEXTAUTH_URL=/ || /^LANGFUSE_HOST=/)' "$ENV_FILE" > "$RUNTIME_ENV_FILE"
{
  echo "AGORA_RESOLVED_BASE_URL=$RESOLVED_BASE_URL"
  echo "NEXTAUTH_URL=$EFFECTIVE_NEXTAUTH_URL"
  echo "LANGFUSE_HOST=$EFFECTIVE_LANGFUSE_HOST"
} >> "$RUNTIME_ENV_FILE"

echo "Resolved env -> target=$TARGET base_url=$RESOLVED_BASE_URL"
echo "Resolved env file: $RUNTIME_ENV_FILE"
