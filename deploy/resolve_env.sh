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

PUBLIC_URL="${AGORA_PUBLIC_URL:-}"
LOCAL_BASE="${AGORA_BASE_URL_LOCAL:-http://localhost}"
LEGACY_VPS_BASE="${AGORA_BASE_URL_VPS:-http://85.17.246.141}"

if [[ "$TARGET" == "vps" ]]; then
  if [[ -n "${PUBLIC_URL// }" ]]; then
    RESOLVED_BASE_URL="$PUBLIC_URL"
  else
    RESOLVED_BASE_URL="$LEGACY_VPS_BASE"
  fi
else
  RESOLVED_BASE_URL="$LOCAL_BASE"
fi
RESOLVED_BASE_URL="${RESOLVED_BASE_URL%/}"
RESOLVED_OBSERVABILITY_URL="${RESOLVED_BASE_URL}/admin/observability"

awk '!(/^AGORA_RESOLVED_BASE_URL=/ || /^AGORA_OBSERVABILITY_URL=/ || /^AGORA_RUNTIME_CONTEXT=/ || /^NEXTAUTH_URL=/ || /^LANGFUSE_HOST=/)' "$ENV_FILE" > "$RUNTIME_ENV_FILE"
{
  echo "AGORA_RUNTIME_CONTEXT=docker"
  echo "AGORA_RESOLVED_BASE_URL=$RESOLVED_BASE_URL"
  echo "AGORA_OBSERVABILITY_URL=$RESOLVED_OBSERVABILITY_URL"
} >> "$RUNTIME_ENV_FILE"

echo "Resolved env -> target=$TARGET base_url=$RESOLVED_BASE_URL"
echo "Resolved env file: $RUNTIME_ENV_FILE"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  "$PYTHON_BIN" "$ROOT_DIR/deploy/fetch_infisical.py" || true
fi
