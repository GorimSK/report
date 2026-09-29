"""Launcher for the Google Ads MCP server.

Credentials come either from GOOGLE_APPLICATION_CREDENTIALS (path to an ADC
JSON file, for local use) or from GOOGLE_ADS_ADC_JSON (the ADC JSON itself,
raw or base64, for Claude Code on the web where only env vars are available).
"""
import base64
import os
import stat
import tempfile

# .mcp.json passes unset variables as empty strings; google.auth treats an
# empty GOOGLE_APPLICATION_CREDENTIALS as a path, so drop them.
for name in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_ADS_ADC_JSON",
             "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_DEVELOPER_TOKEN"):
    if not os.environ.get(name, "").strip():
        os.environ.pop(name, None)

adc_json = os.environ.pop("GOOGLE_ADS_ADC_JSON", None)
if adc_json and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    adc_json = adc_json.strip()
    if not adc_json.startswith("{"):
        adc_json = base64.b64decode(adc_json).decode("utf-8")
    fd, path = tempfile.mkstemp(prefix="google-ads-adc-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(adc_json)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

from ads_mcp.server import run_server  # noqa: E402

run_server()
