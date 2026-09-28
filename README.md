# Reporting agent – Google Ads, Meta Ads a ďalšie zdroje

Agent načíta marketingové dáta z Google Sheetu, zjednotí ich, spočíta KPI a Claude z nich napíše report
v slovenčine (zhrnutie, kanály, čo sa zmenilo a prečo, rozpočet, anomálie, 3 odporúčania).

```
Google Ads ─┐  (Google Ads Scripts / Make /     ┌──────────────┐   ┌────────────────────┐   report.md
Meta Ads   ─┼─  Supermetrics / Windsor.ai)  ──► │ Google Sheet │──►│ agent.py + Claude  │──► záložka AI_Report
Iné zdroje ─┘                                   │ (záložka/zdroj)│  │ (tool use nad KPI) │   GitHub summary
                                                └──────────────┘   └────────────────────┘
```

## Štruktúra

| Súbor | Čo robí |
|---|---|
| `agent.py` | CLI; Claude tool runner s nástrojmi `list_sources`, `get_kpis`, `compare_periods`, `detect_anomalies`, `budget_pacing` |
| `reporting/sheets.py` | pripojenie k Google Sheets cez service account (kľúč z env premennej) |
| `reporting/normalize.py` | mapovanie stĺpcov každého zdroja do jednej schémy, parsovanie `€ 1 234,56` a pod. |
| `reporting/metrics.py` | CTR, CPC, CVR, CPA, ROAS, porovnanie období, anomálie (z-score), čerpanie rozpočtu |
| `config.example.json` | Sheet, rozpočty, mapovanie stĺpcov per zdroj |

Jednotná schéma: `date | source | campaign | spend | impressions | clicks | conversions | revenue`.

## Nastavenie

1. **Service account** v Google Cloud → vytvor JSON kľúč, **necommituj ho** (`.gitignore` ignoruje `*.json`).
   Sheet zdieľaj s e-mailom service accountu (stačí Viewer; Editor ak chceš `--write-sheet`).
2. **Dáta do Sheetu** – jedna záložka na zdroj, prvý riadok = hlavička, jeden riadok = deň × kampaň:
   - *Google Ads*: Google Ads Script (denný export do Sheetu) alebo Make modul Google Ads → Google Sheets.
   - *Meta Ads*: Make scenár „Facebook Insights → Google Sheets“ (level campaign, time_increment 1),
     alebo Supermetrics / Windsor.ai / Coupler.io.
   - *Ďalší zdroj*: pridaj záložku a nový blok do `sources` v configu.
3. `cp config.example.json config.json` a uprav názvy záložiek/stĺpcov a rozpočty.
4. Premenné prostredia:
   ```bash
   export ANTHROPIC_API_KEY=...
   export GOOGLE_APPLICATION_CREDENTIALS=/cesta/mimo/repa/service-account.json
   # alebo GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
   ```

## Spustenie

```bash
pip install -r requirements.txt

python agent.py --period last_7_days                  # report do konzoly
python agent.py --period last_month --out reports/sep.md --write-sheet
python agent.py --csv tests/fixtures/unified.csv --as-of 2026-09-20 --config config.example.json --dry-run
```

Obdobia: `yesterday`, `last_7_days`, `last_30_days`, `last_week`, `mtd`, `last_month`.
`--as-of` = posledný deň s dátami (default včera). `--dry-run` nevolá Claude, len vypíše výstupy nástrojov.

## Automatický týždenný report

`.github/workflows/weekly-report.yml` beží každý pondelok ráno (a ručne cez *Run workflow*).
V repozitári nastav secrets: `ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON` (celý JSON kľúča)
a `REPORT_CONFIG` (obsah `config.json`). Report sa zapíše do záložky `AI_Report` a do súhrnu behu.

## Testy

```bash
python -m pytest -q
```
