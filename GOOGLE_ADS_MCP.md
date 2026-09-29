# Google Ads MCP

Oficiálny server [googleads/google-ads-mcp](https://github.com/googleads/google-ads-mcp)
je nakonfigurovaný v `.mcp.json` (spúšťa sa cez `uvx`, verzia `0.0.4`,
launcher `scripts/google_ads_mcp.py`).
Claude Code ho načíta automaticky pri otvorení repa.

Tools: `customers_list_accessible_customers`, `search_search` (GAQL reporty),
`metadata_get_resource_metadata`. Server je iba na čítanie.

## Potrebné premenné prostredia

Tajné hodnoty necommituj – nastav ich v prostredí (lokálne shell / v Claude Code
on the web v nastaveniach environmentu).

| Premenná | Popis |
| --- | --- |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token z Google Ads → Nástroje → API Center (min. Explorer access) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Lokálne: cesta k ADC JSON so scope `https://www.googleapis.com/auth/adwords` |
| `GOOGLE_ADS_ADC_JSON` | Web: obsah toho istého ADC JSON (raw alebo base64) – použije sa, ak nie je nastavená cesta vyššie |
| `GOOGLE_PROJECT_ID` | GCP projekt (default `groow-reporting`) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | ID MCC účtu bez pomlčiek (default `6816575574`) |

Lokálne stačí mať súbory v `~/.config/google-ads-mcp/` – launcher ich nájde sám:

- `adc.json` – ADC z kroku 3 nižšie,
- `developer_token` – developer token (jeden riadok).

## Postup

1. V GCP projekte zapni [Google Ads API](https://console.cloud.google.com/apis/library/googleads.googleapis.com).
2. Vytvor OAuth klienta (Desktop app) a stiahni jeho JSON.
3. Vygeneruj ADC s Google Ads scope:
   ```shell
   gcloud auth application-default login \
     --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform \
     --client-id-file=CLIENT_JSON
   ```
   Cestu z výpisu `Credentials saved to file: [...]` daj do `GOOGLE_APPLICATION_CREDENTIALS`.
4. Nastav `GOOGLE_ADS_DEVELOPER_TOKEN` (a prípadne `GOOGLE_ADS_LOGIN_CUSTOMER_ID`).
5. Spusti `claude` v repe a schváľ server `google-ads` (`/mcp` ukáže stav).

Pozn.: service account `budget-report@…` sám o sebe do Google Ads nemá prístup –
Google Ads API vyžaduje používateľa s prístupom k účtu (OAuth) alebo service
account pridaný ako používateľ v Google Ads.
