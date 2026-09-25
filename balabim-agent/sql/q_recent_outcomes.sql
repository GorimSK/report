-- WF3: čo v minulosti fungovalo – vyhodnotené zásahy za posledných 90 dní (kontext pre Claude).
SELECT
  o.type, o.platform, o.country, o.title, o.eval_day, o.verdict,
  ROUND(SAFE_DIVIDE(o.value_before, o.cost_before), 2) AS roas_before,
  ROUND(SAFE_DIVIDE(o.value_after, o.cost_after), 2) AS roas_after,
  ROUND(o.cost_before, 0) AS cost_before,
  ROUND(o.cost_after, 0) AS cost_after
FROM `__DS__.action_outcomes` o
WHERE o.evaluated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
ORDER BY o.evaluated_at DESC
LIMIT 40
