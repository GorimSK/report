-- WF6: týždenný súhrn (posledných 7 dní vs. predchádzajúcich 7) a MTD po platforme a krajine.
WITH p AS (
  SELECT DATE_SUB(CURRENT_DATE('Europe/Bratislava'), INTERVAL 1 DAY) AS d
)
SELECT
  f.platform, f.country,
  SUM(IF(f.date > DATE_SUB(p.d, INTERVAL 7 DAY), f.cost_eur, 0)) AS cost_7d,
  SUM(IF(f.date > DATE_SUB(p.d, INTERVAL 7 DAY), f.conv_value_eur, 0)) AS value_7d,
  SUM(IF(f.date > DATE_SUB(p.d, INTERVAL 7 DAY), f.conversions, 0)) AS conv_7d,
  SUM(IF(f.date <= DATE_SUB(p.d, INTERVAL 7 DAY), f.cost_eur, 0)) AS cost_p7,
  SUM(IF(f.date <= DATE_SUB(p.d, INTERVAL 7 DAY), f.conv_value_eur, 0)) AS value_p7,
  SUM(IF(f.date <= DATE_SUB(p.d, INTERVAL 7 DAY), f.conversions, 0)) AS conv_p7,
  ANY_VALUE(p.d) AS run_date
FROM `__DS__.v_daily_perf` f
CROSS JOIN p
WHERE f.date BETWEEN DATE_SUB(p.d, INTERVAL 13 DAY) AND p.d
GROUP BY f.platform, f.country
ORDER BY f.country, f.platform
