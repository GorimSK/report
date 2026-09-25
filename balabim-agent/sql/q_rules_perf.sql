-- WF2: agregované metriky pre pravidlá. d = včerajšok (Europe/Bratislava).
-- Okná: 1d = d, 7d = d-6..d, p7 = d-13..d-7, b7 = d-7..d-1 (7 dní pred včerajškom, pre outage), mtd = 1. deň mesiaca..d.
-- Úrovne: country (platforma × krajina), campaign, adset (len Meta).
WITH p AS (
  SELECT DATE_SUB(CURRENT_DATE('Europe/Bratislava'), INTERVAL 1 DAY) AS d
),
base AS (
  SELECT f.*, p.d
  FROM `__DS__.v_daily_perf` f
  CROSS JOIN p
  WHERE f.date BETWEEN LEAST(DATE_SUB(p.d, INTERVAL 13 DAY), DATE_TRUNC(p.d, MONTH)) AND p.d
),
tagged AS (
  SELECT *,
    date = d AS w1,
    date BETWEEN DATE_SUB(d, INTERVAL 6 DAY) AND d AS w7,
    date BETWEEN DATE_SUB(d, INTERVAL 13 DAY) AND DATE_SUB(d, INTERVAL 7 DAY) AS wp7,
    date BETWEEN DATE_SUB(d, INTERVAL 7 DAY) AND DATE_SUB(d, INTERVAL 1 DAY) AS wb7,
    date >= DATE_TRUNC(d, MONTH) AS wmtd
  FROM base
),
metrics AS (
  SELECT
    level, platform, country, scope_id,
    ANY_VALUE(scope_name) AS scope_name,
    ANY_VALUE(campaign_id) AS campaign_id,
    ANY_VALUE(campaign_name) AS campaign_name,
    MAX(IF(w1, campaign_status, NULL)) AS campaign_status,
    MAX(IF(w1, primary_status, NULL)) AS primary_status,
    MAX(IF(w1, bidding_strategy, NULL)) AS bidding_strategy,
    SUM(IF(w1, cost_eur, 0)) AS cost_1d,
    SUM(IF(w1, conversions, 0)) AS conv_1d,
    SUM(IF(w1, conv_value_eur, 0)) AS value_1d,
    SUM(IF(w7, cost_eur, 0)) AS cost_7d,
    SUM(IF(w7, conversions, 0)) AS conv_7d,
    SUM(IF(w7, conv_value_eur, 0)) AS value_7d,
    SUM(IF(w7, clicks, 0)) AS clicks_7d,
    SUM(IF(w7, impressions, 0)) AS impr_7d,
    SUM(IF(wp7, cost_eur, 0)) AS cost_p7,
    SUM(IF(wp7, conversions, 0)) AS conv_p7,
    SUM(IF(wp7, conv_value_eur, 0)) AS value_p7,
    SUM(IF(wp7, clicks, 0)) AS clicks_p7,
    SUM(IF(wp7, impressions, 0)) AS impr_p7,
    SUM(IF(wb7, conversions, 0)) / 7 AS conv_avg_b7,
    SUM(IF(wmtd, cost_eur, 0)) AS cost_mtd,
    SUM(IF(wmtd, conversions, 0)) AS conv_mtd,
    SUM(IF(wmtd, conv_value_eur, 0)) AS value_mtd,
    AVG(IF(w7, search_lost_is_budget, NULL)) AS lost_is_budget_7d,
    AVG(IF(w7, search_lost_is_rank, NULL)) AS lost_is_rank_7d,
    AVG(IF(w7, search_is, NULL)) AS search_is_7d,
    ANY_VALUE(d) AS run_date
  FROM (
    SELECT 'country' AS level, platform, country, 'ALL' AS scope_id, country AS scope_name, * EXCEPT (platform, country) FROM tagged
    UNION ALL
    SELECT 'campaign', platform, country, campaign_id, campaign_name, * EXCEPT (platform, country) FROM tagged
    UNION ALL
    SELECT 'adset', platform, country, adset_id, adset_name, * EXCEPT (platform, country) FROM tagged WHERE platform = 'META' AND adset_id IS NOT NULL
  )
  GROUP BY level, platform, country, scope_id
)
SELECT
  *,
  EXTRACT(DAY FROM run_date) AS days_elapsed,
  EXTRACT(DAY FROM LAST_DAY(run_date)) AS days_in_month
FROM metrics
WHERE cost_7d > 0 OR cost_p7 > 0 OR cost_mtd > 0
ORDER BY level, platform, country, cost_7d DESC
