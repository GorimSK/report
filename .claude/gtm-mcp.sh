#!/bin/bash
# Starts the read-only GTM MCP server (stdio, scripts/gtm_mcp.py).
# Credentials, first match wins:
#   GTM_SA_KEY_B64 / GA4_SA_KEY_B64 (cloud, base64 service account JSON, written outside the repo),
#   GTM_APPLICATION_CREDENTIALS (path), ~/.config/gtm-mcp/sa-key.json, GOOGLE_APPLICATION_CREDENTIALS.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HOME/.local/share/gtm-mcp-venv"
KEY_FILE="$HOME/.config/gtm-mcp/sa-key.json"
KEY_B64="${GTM_SA_KEY_B64:-${GA4_SA_KEY_B64:-}}"

if [ -n "$KEY_B64" ]; then
  mkdir -p "$(dirname "$KEY_FILE")"
  umask 077
  printf '%s' "$KEY_B64" | base64 -d > "$KEY_FILE"
  export GOOGLE_APPLICATION_CREDENTIALS="$KEY_FILE"
elif [ -n "${GTM_APPLICATION_CREDENTIALS:-}" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$GTM_APPLICATION_CREDENTIALS"
elif [ -f "$KEY_FILE" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$KEY_FILE"
fi

if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  echo "gtm-mcp: set GTM_SA_KEY_B64 (cloud), GTM_APPLICATION_CREDENTIALS or ~/.config/gtm-mcp/sa-key.json" >&2
  exit 1
fi

if [ -x "$VENV/bin/python" ]; then
  exec "$VENV/bin/python" "$DIR/scripts/gtm_mcp.py"
fi
exec uv run --quiet --script "$DIR/scripts/gtm_mcp.py"
