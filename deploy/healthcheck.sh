#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-localhost}"
curl -fsS "http://${HOST}/health" && echo
