-- WF6: čerpanie od začiatku mesiaca po platforme a krajine.
WITH p AS (
  SELECT DATE_SUB(CURRENT_DATE('Europe/Bratislava'), INTERVAL 1 DAY) AS d
)
SELECT
  f.platform, f.country,
  SUM(f.cost_eur) AS cost_mtd,
  SUM(f.conv_value_eur) AS value_mtd,
  ANY_VALUE(EXTRACT(DAY FROM p.d)) AS days_elapsed,
  ANY_VALUE(EXTRACT(DAY FROM LAST_DAY(p.d))) AS days_in_month
FROM `__DS__.v_daily_perf` f
CROSS JOIN p
WHERE f.date BETWEEN DATE_TRUNC(p.d, MONTH) AND p.d
GROUP BY f.platform, f.country
