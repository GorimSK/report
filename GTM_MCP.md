# GTM MCP

Vlastný read-only server nad [Tag Manager API v2](https://developers.google.com/tag-platform/tag-manager/api/v2)
(`scripts/gtm_mcp.py`, launcher `.claude/gtm-mcp.sh`), nakonfigurovaný v `.mcp.json` ako `gtm`.
Claude Code ho načíta automaticky pri otvorení repa. Na webe ho nainštaluje SessionStart hook.

Tools: `list_accounts`, `list_containers`, `find_container` (podľa `GTM-XXXXXXX`),
`list_workspaces`, `workspace_status` (nepublikované zmeny), `list_entities`
(tags / triggers / variables …), `get_entity`, `live_version`, `list_versions`.
Scope `tagmanager.readonly` – server nič nemení ani nepublikuje.

## Prihlásenie

Service account JSON, prvý nájdený vyhráva:

| Zdroj | Kde |
| --- | --- |
| `GTM_SA_KEY_B64` | Web: base64 JSON kľúča v nastaveniach environmentu |
| `GA4_SA_KEY_B64` | Web: fallback – rovnaký účet ako pre GA4 (`ga4-mcp@groow-reporting…`) |
| `GTM_APPLICATION_CREDENTIALS` | Lokálne: cesta ku kľúču |
| `~/.config/gtm-mcp/sa-key.json` | Lokálne: default umiestnenie |
| `GOOGLE_APPLICATION_CREDENTIALS` | Posledný fallback |

## Postup

1. V GCP projekte `groow-reporting` zapni [Tag Manager API](https://console.cloud.google.com/apis/library/tagmanager.googleapis.com).
2. V GTM → Admin → Správa používateľov pridaj e-mail service accountu
   (napr. `ga4-mcp@groow-reporting.iam.gserviceaccount.com`) s rolou **Čítanie**
   na účet alebo konkrétny kontajner.
3. Nová session / `/mcp` ukáže server `gtm`.
