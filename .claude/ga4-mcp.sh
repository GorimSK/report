#!/bin/bash
# Starts analytics-mcp (stdio). In cloud sessions the service account key comes
# from the GA4_SA_KEY_B64 environment variable and is written outside the repo.
set -euo pipefail

VENV="$HOME/.local/share/ga4-mcp-venv"
KEY_FILE="$HOME/.config/ga4/sa-key.json"

if [ -n "${GA4_SA_KEY_B64:-}" ]; then
  mkdir -p "$(dirname "$KEY_FILE")"
  umask 077
  printf '%s' "$GA4_SA_KEY_B64" | base64 -d > "$KEY_FILE"
  export GOOGLE_APPLICATION_CREDENTIALS="$KEY_FILE"
fi

if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  echo "analytics-mcp: set GA4_SA_KEY_B64 (cloud) or GOOGLE_APPLICATION_CREDENTIALS" >&2
  exit 1
fi

if [ -z "${GOOGLE_PROJECT_ID:-}" ]; then
  GOOGLE_PROJECT_ID="$(python3 -c 'import json,os;print(json.load(open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]))["project_id"])')"
  export GOOGLE_PROJECT_ID
fi

if [ -x "$VENV/bin/analytics-mcp" ]; then
  exec "$VENV/bin/analytics-mcp"
fi
exec uvx analytics-mcp
