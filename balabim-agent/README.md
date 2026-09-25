# Balabim PPC agent (n8n)

Agent každý deň stiahne výkon kampaní Balabim z **Google Ads** a **Meta Ads** v 9 krajinách (SK, CZ, HU, PL, RO, BG, HR, SI, GR). Nájde problémy a príležitosti a založí k nim úlohy do **Asany** s konkrétnym odporúčaním. Po dokončení úlohy agent o 7 a 14 dní vyhodnotí jej dopad. V pondelok zverejní týždenný stav projektu.

Agent **iba číta dáta a navrhuje**. V reklamných účtoch nič nemení.

```
06:00 WF1 zber ─┬─ Google Ads API (GAQL) ─┐
                ├─ Meta Marketing API ────┼─> BigQuery (história, EUR)
                └─ kurzy ECB ─────────────┘
07:00 WF2 pravidlá ─> findings ─> WF3 AI analytik (Claude) ─> WF4 Asana: nový task / komentár / P1 e-mail
      Asana webhook ─> WF5 log dokončených taskov ─> 07:30 WF5b vyhodnotenie dopadu (komentár do tasku)
Po 08:00 WF6 týždenný report ─> Asana project status update
Chyba v ľubovoľnom WF ─> WF_error ─> e-mail
```

## Obsah

| Cesta | Čo obsahuje |
|---|---|
| `n8n/*.json` | Hotové workflowy na import do n8n, vygenerované s ukážkovými hodnotami |
| `n8n/schema.sql` | BigQuery tabuľky a pohľady |
| `code/` | JavaScript pre Code nody; `_lib.js` sa vkladá do každého nodu |
| `sql/` | GAQL pre Google Ads a BigQuery dotazy |
| `prompts/` | System prompty a JSON schéma výstupu pre Claude |
| `config/` | `settings.example.json` a šablóny záložiek Config Sheetu |
| `scripts/asana_setup.py` | Vytvorí projekt, sekcie a custom fields v Asane a vypíše ich GID |
| `build.py` | Zostaví workflowy z `code/`, `sql/` a `prompts/` a dosadí hodnoty zo settings |
| `tests/` | Testy Code nodov (spúšťajú presne ten kód, ktorý je v JSON) |

## Workflowy

| WF | Kedy | Čo robí |
|---|---|---|
| **WF1 Denný zber** | 06:00 | Google Ads: kampane × deň (posledných 7 dní, kvôli oneskoreným konverziám), search termy (30 dní), zamietnuté reklamy. Meta: ad sety × deň, 7-dňová frekvencia, learning limited, zamietnuté reklamy. Sumy prepočíta na EUR kurzom ECB a zapíše do BigQuery. |
| **WF2 Pravidlá** | 07:00 | Deterministické kontroly nad BigQuery a cieľmi z Config Sheetu. Výsledok (findings) uloží a pošle do WF3. |
| **WF3 AI analytik** | volá WF2 | Findings, ktoré už rieši otvorený task, idú rovno do WF4 ako komentár. Nové findings Claude zlúči do úloh, pridá diagnózu, kroky a odhad dopadu. Výstup je validovaný cez JSON schému. Ak AI zlyhá, úlohy vzniknú zo šablón a P1 sa nikdy nestratí. |
| **WF4 Asana** | volá WF3 | Deduplikácia cez pole Alert-ID: nový task alebo komentár do existujúceho. Nastaví assignee podľa krajiny × platformy, termín P1 +1, P2 +3 a P3 +7 dní (posunutý z víkendu na pondelok) a limit nových taskov za deň. Pri P1 pošle e-mail. |
| **WF5 Spätná väzba** | Asana webhook | Dokončené tasky zapíše do `actions_log`. |
| **WF5b Dopad** | 07:30 | 7 a 14 dní po dokončení porovná KPI pred a po zásahu a výsledok dá ako komentár do tasku. Tieto výsledky dostáva Claude ako kontext. |
| **WF6 Týždenný report** | Po 08:00 | Tabuľka KPI po krajinách, komentár od Claude a Asana status update (on track / at risk / off track). |
| **WF_error** | pri chybe | E-mail s názvom workflowu, nodu a chybou. |

### Pravidlá (WF2)

Prahy sú v `settings.json` → `rule_defaults`. Pre konkrétnu krajinu a platformu ich prepíše stĺpec v záložke `targets`.

| Pravidlo | Priorita | Podmienka | Parameter |
|---|---|---|---|
| `TRACKING_OUTAGE` | P1 | Včera je o ≥ 70 % menej konverzií ako 7-dňový priemer (ten ≥ 3/deň), hoci sa míňa | `outage_drop`, `outage_min_daily_conv` |
| `NO_DATA` | P1 | Krajina má rozpočet, ale 14 dní nemá žiadne náklady | – |
| `PACING_OVER` / `PACING_UNDER` | P1–P2 | Projekcia mesačných nákladov sa od rozpočtu odchyľuje o viac ako ±15 %, od 5. dňa v mesiaci | `pacing_tolerance` |
| `KPI_BELOW_TARGET` | P2 | ROAS alebo CPA za 7 dní je horší ako cieľ o viac ako 15 % | `kpi_tolerance`, `min_spend_7d_eur` |
| `KPI_WOW_DROP` | P2 | KPI týždeň na týždeň horší o viac ako 25 % | `wow_drop`, `wow_min_conv` |
| `WASTE_NO_CONV` | P2 | Kampaň minula ≥ 50 € (pri CPA ≥ 2× cieľové CPA) za 7 dní a nemá konverziu | `min_spend_campaign_7d_eur` |
| `POLICY` | P2 | Zamietnuté alebo problémové reklamy | – |
| `SCALE_BUDGET` | P3 | Google kampaň plní cieľ, ale stráca ≥ 20 % IS kvôli rozpočtu | `scale_lost_is_budget` |
| `CAMPAIGN_DROP` | P3 | ROAS kampane týždeň na týždeň výrazne klesol | `wow_drop` |
| `CREATIVE_FATIGUE` | P3 | Meta ad set má 7-dňovú frekvenciu nad 3 | `max_frequency` |
| `SEARCH_TERMS` | P3 | Search termy za ≥ 15 € bez konverzie za 30 dní, jeden task na krajinu a mesiac | `search_term_min_cost_eur` |
| `LEARNING_LIMITED` | P3 | Meta ad sety v stave Learning limited | – |
| `UNMAPPED` | P3 | Náklady kampaní, ktorým sa nedá priradiť krajina | – |

## Nasadenie

### 0. Prístupy (vybaviť ako prvé, developer token trvá niekoľko dní)

- **Google Ads API.** Developer token s úrovňou *Basic access*, požiadať v MCC → API Center. Ďalej OAuth klient v Google Cloud a prístup používateľa k MCC, pod ktorým sú účty Balabim.
- **Meta.** Business Manager → System User s rolou pre reklamné účty Balabim. Vygenerovať token so scope `ads_read` (bez expirácie).
- **Google Cloud.** Projekt s BigQuery a service account s rolami *BigQuery Data Editor* a *BigQuery Job User*. Rovnaký service account použije aj Google Sheets node, preto s jeho e-mailom treba zdieľať Config Sheet.
- **Asana.** Personal Access Token alebo OAuth a platený plán kvôli custom fields.
- **Anthropic.** API kľúč.
- **SMTP** pre alerty.
- **n8n** s verejnou HTTPS adresou, lebo Asana webhook (WF5) potrebuje dosiahnuť n8n zvonku. Odporúčanie: self-hosted Docker s Postgresom. Stačí aj n8n Cloud.

### 1. BigQuery

```bash
cp config/settings.example.json config/settings.json   # vyplniť gcp_project, bq_dataset, ...
python build.py --settings config/settings.json --out dist
bq mk --location=EU --dataset <projekt>:balabim_ads
bq query --use_legacy_sql=false < dist/schema.sql
```

### 2. Config Sheet (Google Sheets)

Vytvor tabuľku so záložkami `accounts` a `targets` podľa `config/accounts_template.csv` a `config/targets_template.csv`. Zdieľaj ju so service accountom a jej ID zapíš do `config_sheet_id`.

- **accounts**: jeden riadok na reklamný účet. `country` je kód krajiny. Ak jeden účet pokrýva viac krajín, zadaj `MULTI`; krajina sa potom určí z názvu kampane (napr. `HU_Prospecting`, `PMax | RO | Feed`). **Kód krajiny v názve kampane** je preto dôležitá konvencia.
- **targets**: jeden riadok na krajinu × platformu, teda 18 riadkov:
  - `monthly_budget_eur`,
  - `kpi` (`ROAS` alebo `CPA`) a k nemu `target_roas` alebo `target_cpa_eur`,
  - `asana_assignee_gid`: kto dostane tasky pre danú krajinu a platformu,
  - voliteľne prahy, ktoré prepíšu hodnoty z `rule_defaults`.

  Čísla píš bez oddeľovačov tisícov.

### 3. Asana

```bash
export ASANA_TOKEN=...
python scripts/asana_setup.py --workspace <workspace_gid> --team <team_gid>
```

Skript vytvorí projekt „Balabim – PPC optimalizácia“ so sekciami Nové / V riešení / Hotovo. Pridá polia Krajina, Platforma, Typ úlohy, Priorita, Alert-ID a Dopad (€). Vypíše JSON, ktorý vlož do `settings.json` → `asana`. Pole *Alert-ID* nikto nemá ručne meniť, podľa neho agent páruje opakované problémy.

### 4. n8n credentials

Vytvor credentials s rovnakými názvami, aké majú workflowy. Pri importe sa potom stačí preklikať:

| Názov | Typ v n8n |
|---|---|
| Google Ads OAuth (MCC) | Google Ads OAuth2 API |
| Meta System User token | Query Auth (`access_token` = token) |
| Google Service Account (BigQuery + Sheets) | Google Service Account API |
| Asana | Asana API (Access Token) |
| Anthropic API key | Header Auth (`x-api-key` = kľúč) |
| SMTP | SMTP |

### 5. Import (poradie kvôli ID pod-workflowov)

1. `python build.py --settings config/settings.json --out dist`
2. Importuj `dist/WF_error.json`, `dist/WF4_asana.json` a `dist/WF3_ai_analyst.json`. Ich ID (z URL v n8n) zapíš do `settings.json` → `workflow_ids`.
3. Znova spusti `build.py` a importuj zvyšné workflowy. WF3 a WF4 importuj ešte raz s nastaveným error workflowom.
4. V každom workflowe skontroluj credentials pri nodoch s výstražným trojuholníkom.

`dist/` a `config/settings.json` sú v `.gitignore`, lebo obsahujú developer token a ID.

### 6. Overenie pred aktiváciou

1. **WF1** spusti ručne. Náklady a konverzie za včerajšok v `v_daily_perf` porovnaj s rozhraním Google Ads a Meta pre jednu krajinu; tolerancia je pod 1 % (rozdiel môže spôsobiť iba kurz). Tento krok treba robiť v rovnakej atribúcii, akú má účet.
2. **WF2** spusti ručne s testovacím Asana projektom (iný `project_gid`). Skontroluj findings a tasky.
3. **WF2** spusti znova. Nesmú vzniknúť duplicitné tasky, iba komentáre.
4. Test task v Asane dokonči a over, že v `actions_log` pribudol riadok (WF5).
5. Aktivuj WF1, WF2, WF5, WF5b a WF6 (WF3 a WF4 sa volajú samy).
6. Prvé 1–2 týždne dolaď prahy v `targets` podľa toho, koľko šumu tím v Asane vidí.

## Prevádzka a údržba

- **Verzie API.** Google Ads vydáva novú verziu API približne každý štvrťrok, stará vydrží zhruba rok. Meta Graph API platí približne 2 roky. Verzie sú v `gads_api_version` a `meta_api_version`. Pri chybe WF1 skontroluj najprv ich.
- **Model.** Model Claude je v `anthropic_model`, hĺbka analýzy v `anthropic_effort` (`low` / `medium` / `high`). Request zapína `fallbacks: "default"`: ak model odmietne odpoveď, API ju automaticky zopakuje na záložnom modeli.
- **Náklady (odhad).** Claude pri dennej analýze asi 5–15 USD mesačne. BigQuery sa zmestí do free tieru. n8n self-host na VPS stojí asi 10–20 € mesačne.
- **Meta tokeny** System Usera neexpirujú, OAuth tokeny Google sa obnovujú samy. Keď niečo prestane fungovať, príde e-mail z WF_error.
- **Konverzie za včerajšok** sú ešte neúplné (oneskorená atribúcia). Preto pravidlo výpadku reaguje až na prepad o 70 % a WF1 každý deň znova sťahuje posledných 7 dní.

## Vývoj

Kód nodov, SQL a prompty sa upravujú v `code/`, `sql/` a `prompts/`, nie priamo v n8n. Potom:

```bash
python build.py                 # n8n/*.json s ukážkovými hodnotami (commitované)
node tests/run_tests.mjs        # testy Code nodov
```

Zmeny urobené priamo v n8n UI treba preniesť späť do repozitára, inak ich prepíše ďalší import.

## Ďalšia fáza (voliteľné)

Poloautomatické akcie so schválením: človek označí task v Asane ako „Schválené“ a n8n vykoná zmenu cez API. Napríklad pridá negatívne kľúčové slová zo SEARCH_TERMS tasku, pozastaví zamietnutú reklamu alebo upraví rozpočet v rámci limitu. Každá akcia sa zapíše do komentára tasku.
