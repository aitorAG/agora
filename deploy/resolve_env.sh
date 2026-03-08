#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
RUNTIME_ENV_FILE="$ROOT_DIR/.env.runtime"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

normalize_env_value() {
  local value
  value="$(trim "$1")"
  if [[ "$value" == *" #"* ]]; then
    value="${value%% \#*}"
    value="$(trim "$value")"
  fi
  if [[ ${#value} -ge 2 ]]; then
    if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi
  printf '%s' "$value"
}

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

> "$RUNTIME_ENV_FILE"
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line="$(trim "$raw_line")"
  if [[ -z "$line" || "${line:0:1}" == "#" || "$line" != *=* ]]; then
    continue
  fi
  key="$(trim "${line%%=*}")"
  if [[ "$key" == "AGORA_RESOLVED_BASE_URL" || "$key" == "AGORA_OBSERVABILITY_URL" || "$key" == "AGORA_RUNTIME_CONTEXT" || "$key" == "NEXTAUTH_URL" || "$key" == "LANGFUSE_HOST" ]]; then
    continue
  fi
  value="$(normalize_env_value "${line#*=}")"
  printf '%s=%s\n' "$key" "$value" >> "$RUNTIME_ENV_FILE"
done < "$ENV_FILE"
{
  echo "AGORA_RUNTIME_CONTEXT=docker"
  echo "AGORA_RESOLVED_BASE_URL=$RESOLVED_BASE_URL"
  echo "AGORA_OBSERVABILITY_URL=$RESOLVED_OBSERVABILITY_URL"
} >> "$RUNTIME_ENV_FILE"

echo "Resolved env -> target=$TARGET base_url=$RESOLVED_BASE_URL"
echo "Resolved env file: $RUNTIME_ENV_FILE"

required_values=("POSTGRES_PASSWORD")
bootstrap_seed_raw="${AUTH_BOOTSTRAP_SEED:-true}"
bootstrap_seed="$(echo "$bootstrap_seed_raw" | tr '[:upper:]' '[:lower:]')"
if [[ "$TARGET" == "vps" ]]; then
  required_values+=("AUTH_SECRET_KEY" "TELEMETRY_INGEST_KEY")
  if [[ "$bootstrap_seed" != "0" && "$bootstrap_seed" != "false" && "$bootstrap_seed" != "no" && "$bootstrap_seed" != "off" ]]; then
    required_values+=("AUTH_SEED_USERNAME" "AUTH_SEED_PASSWORD")
  fi
fi

missing_values=()
for key in "${required_values[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing_values+=("$key")
  fi
done

if [[ ${#missing_values[@]} -gt 0 ]]; then
  echo "Resolved runtime environment is missing required values: ${missing_values[*]}" >&2
  exit 1
fi

if [[ "$TARGET" == "vps" ]]; then
  invalid_values=()
  [[ "${AUTH_SECRET_KEY:-}" == "dev-only-change-me" || "${AUTH_SECRET_KEY:-}" == "change_me_super_secret" ]] && invalid_values+=("AUTH_SECRET_KEY")
  [[ "${TELEMETRY_INGEST_KEY:-}" == "change_me_ingest_key" || "${TELEMETRY_INGEST_KEY:-}" == "admin" ]] && invalid_values+=("TELEMETRY_INGEST_KEY")
  if [[ "$bootstrap_seed" != "0" && "$bootstrap_seed" != "false" && "$bootstrap_seed" != "no" && "$bootstrap_seed" != "off" ]]; then
    [[ "${AUTH_SEED_PASSWORD:-}" == "agora123" || "${AUTH_SEED_PASSWORD:-}" == "admin" || "${AUTH_SEED_PASSWORD:-}" == "change_me_admin_password" ]] && invalid_values+=("AUTH_SEED_PASSWORD")
  fi
  if [[ ${#invalid_values[@]} -gt 0 ]]; then
    echo "Resolved runtime environment has insecure placeholder values: ${invalid_values[*]}" >&2
    exit 1
  fi
fi
