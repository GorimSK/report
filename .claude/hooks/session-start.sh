#!/bin/bash
set -euo pipefail

# Materializes Google Ads API OAuth credentials (Application Default
# Credentials) from the GOOGLE_ADS_ADC_JSON environment/secret variable into
# a file, so the google-ads-mcp server(s) declared in .mcp.json can find
# them via GOOGLE_APPLICATION_CREDENTIALS. Only relevant in Claude Code on
# the web, where there is no interactive browser to run
# `gcloud auth application-default login`.

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if [ -z "${GOOGLE_ADS_ADC_JSON:-}" ]; then
  # No credentials configured yet for this environment; nothing to do.
  exit 0
fi

ADC_DIR="$HOME/.config/google-ads-mcp"
ADC_PATH="$ADC_DIR/adc.json"

mkdir -p "$ADC_DIR"
printf '%s' "$GOOGLE_ADS_ADC_JSON" > "$ADC_PATH"
chmod 600 "$ADC_PATH"

echo "export GOOGLE_APPLICATION_CREDENTIALS=\"$ADC_PATH\"" >> "$CLAUDE_ENV_FILE"
