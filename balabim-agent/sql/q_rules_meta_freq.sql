-- WF2: 7-dňová frekvencia Meta ad setov z posledného snapshotu.
WITH latest AS (
  SELECT MAX(snapshot_date) AS s FROM `__DS__.meta_adset_7d`
)
SELECT * EXCEPT (rn) FROM (
  SELECT m.*, ROW_NUMBER() OVER (PARTITION BY adset_id ORDER BY ingested_at DESC) AS rn
  FROM `__DS__.meta_adset_7d` m
  WHERE snapshot_date = (SELECT s FROM latest)
    AND snapshot_date >= DATE_SUB(CURRENT_DATE('Europe/Bratislava'), INTERVAL 2 DAY)
)
WHERE rn = 1
ORDER BY spend_eur DESC
