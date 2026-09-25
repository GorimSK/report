-- Balabim PPC agent – BigQuery schéma.
-- YOUR_GCP_PROJECT.balabim_ads nahradí build.py hodnotou `projekt.dataset` zo settings.json.
-- Spustiť raz v BigQuery konzole (alebo `bq query --use_legacy_sql=false < dist/schema.sql`).
--
-- Tabuľky sú append-only (n8n zapisuje cez streaming insert, ktorý neumožňuje
-- UPDATE/DELETE čerstvých riadkov). Opakované behy deduplikujú pohľady v_*,
-- ktoré berú posledný zapísaný riadok pre daný kľúč.

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.daily_perf` (
  date DATE NOT NULL,
  platform STRING NOT NULL,            -- GOOGLE_ADS | META
  account_id STRING,
  account_name STRING,
  country STRING,                      -- SK, CZ, HU, PL, RO, BG, HR, SI, GR, UNKNOWN
  campaign_id STRING,
  campaign_name STRING,
  campaign_type STRING,
  campaign_status STRING,
  adset_id STRING,                     -- Meta ad set; NULL pre Google Ads
  adset_name STRING,
  currency STRING,
  fx_rate FLOAT64,                     -- jednotiek meny za 1 EUR
  cost_eur FLOAT64,
  impressions INT64,
  clicks INT64,
  reach INT64,
  conversions FLOAT64,
  conv_value_eur FLOAT64,
  search_is FLOAT64,
  search_lost_is_budget FLOAT64,
  search_lost_is_rank FLOAT64,
  budget_daily_eur FLOAT64,
  bidding_strategy STRING,
  primary_status STRING,
  primary_status_reasons STRING,
  ingested_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY platform, country;

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.search_terms` (
  snapshot_date DATE NOT NULL,
  period_start DATE,
  platform STRING,
  account_id STRING,
  country STRING,
  campaign_id STRING,
  campaign_name STRING,
  ad_group_id STRING,
  ad_group_name STRING,
  search_term STRING,
  cost_eur FLOAT64,
  clicks INT64,
  conversions FLOAT64,
  conv_value_eur FLOAT64,
  ingested_at TIMESTAMP
)
PARTITION BY snapshot_date;

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.meta_adset_7d` (
  snapshot_date DATE NOT NULL,
  account_id STRING,
  country STRING,
  campaign_id STRING,
  campaign_name STRING,
  adset_id STRING,
  adset_name STRING,
  spend_eur FLOAT64,
  impressions INT64,
  reach INT64,
  frequency FLOAT64,
  link_clicks INT64,
  ingested_at TIMESTAMP
)
PARTITION BY snapshot_date;

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.entity_issues` (
  snapshot_date DATE NOT NULL,
  platform STRING,
  account_id STRING,
  country STRING,
  entity_level STRING,                 -- AD | ADSET
  entity_id STRING,
  entity_name STRING,
  campaign_id STRING,
  campaign_name STRING,
  issue STRING,                        -- DISAPPROVED | WITH_ISSUES | LEARNING_LIMITED
  detail STRING,
  ingested_at TIMESTAMP
)
PARTITION BY snapshot_date;

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.fx_rates` (
  date DATE NOT NULL,
  currency STRING NOT NULL,
  rate_per_eur FLOAT64,
  ingested_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.findings` (
  run_date DATE NOT NULL,
  alert_key STRING NOT NULL,
  rule STRING,
  severity STRING,                     -- P1 | P2 | P3
  platform STRING,
  country STRING,
  scope_level STRING,
  scope_id STRING,
  scope_name STRING,
  title STRING,
  summary_line STRING,
  metrics STRING,                      -- JSON
  created_at TIMESTAMP
)
PARTITION BY run_date;

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.agent_tasks` (
  task_gid STRING NOT NULL,
  created_at TIMESTAMP,
  alert_keys STRING,                   -- čiarkou oddelené
  platform STRING,
  country STRING,
  campaign_id STRING,
  type STRING,
  priority STRING,
  title STRING,
  source STRING,                       -- ai | template
  permalink_url STRING
);

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.actions_log` (
  task_gid STRING NOT NULL,
  completed_at TIMESTAMP,
  completed_by STRING,
  task_name STRING,
  logged_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `YOUR_GCP_PROJECT.balabim_ads.action_outcomes` (
  task_gid STRING NOT NULL,
  eval_day INT64,                      -- 7 | 14
  evaluated_at TIMESTAMP,
  platform STRING,
  country STRING,
  campaign_id STRING,
  type STRING,
  title STRING,
  done_date DATE,
  cost_before FLOAT64,
  value_before FLOAT64,
  conv_before FLOAT64,
  cost_after FLOAT64,
  value_after FLOAT64,
  conv_after FLOAT64,
  verdict STRING                       -- IMPROVED | NEUTRAL | WORSE | NO_DATA
);

-- Posledná verzia každého denného riadku (WF1 každý deň prepisuje posledných 7 dní,
-- aby zachytil oneskorené konverzie).
CREATE OR REPLACE VIEW `YOUR_GCP_PROJECT.balabim_ads.v_daily_perf` AS
SELECT * EXCEPT (rn)
FROM (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY date, platform, account_id, campaign_id, IFNULL(adset_id, '')
      ORDER BY ingested_at DESC
    ) AS rn
  FROM `YOUR_GCP_PROJECT.balabim_ads.daily_perf`
)
WHERE rn = 1;
