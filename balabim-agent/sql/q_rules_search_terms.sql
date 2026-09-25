-- WF2: search termy bez konverzií z posledného snapshotu (okno podľa settings.search_terms_lookback_days).
WITH latest AS (
  SELECT MAX(snapshot_date) AS s FROM `__DS__.search_terms`
),
dedup AS (
  SELECT t.* EXCEPT (rn) FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY account_id, campaign_id, ad_group_id, search_term ORDER BY ingested_at DESC
    ) AS rn
    FROM `__DS__.search_terms`
    WHERE snapshot_date = (SELECT s FROM latest)
  ) t
  WHERE rn = 1
)
SELECT
  country, campaign_id, campaign_name, ad_group_name, search_term,
  ROUND(cost_eur, 2) AS cost_eur, clicks, conversions, snapshot_date, period_start
FROM dedup
WHERE conversions = 0
ORDER BY country, cost_eur DESC
