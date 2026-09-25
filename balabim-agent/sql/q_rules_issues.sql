-- WF2: zamietnuté reklamy a ad sety s obmedzeným učením z posledného snapshotu.
WITH latest AS (
  SELECT platform, MAX(snapshot_date) AS s FROM `__DS__.entity_issues` GROUP BY platform
)
SELECT DISTINCT
  i.platform, i.country, i.entity_level, i.entity_id, i.entity_name,
  i.campaign_id, i.campaign_name, i.issue, i.detail, i.snapshot_date
FROM `__DS__.entity_issues` i
JOIN latest l ON l.platform = i.platform AND l.s = i.snapshot_date
WHERE i.snapshot_date >= DATE_SUB(CURRENT_DATE('Europe/Bratislava'), INTERVAL 2 DAY)
ORDER BY i.platform, i.country, i.issue
