#!/bin/bash
# Installs the Google Analytics MCP server (analytics-mcp) for Claude Code on the web.
# The service account key itself is decoded at server start by .claude/ga4-mcp.sh.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

VENV="$HOME/.local/share/ga4-mcp-venv"

if [ ! -x "$VENV/bin/analytics-mcp" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --disable-pip-version-check analytics-mcp
fi

if [ -z "${GA4_SA_KEY_B64:-}" ]; then
  echo "GA4_SA_KEY_B64 is not set in the cloud environment; analytics-mcp will not be able to authenticate." >&2
fi
