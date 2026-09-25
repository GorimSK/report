-- WF5b: tasky dokončené pred 7 alebo 14 dňami, ktoré ešte nemajú vyhodnotenie.
-- Porovnáva N dní pred dokončením s N dňami po ňom v rozsahu tasku (platforma / krajina / kampaň).
WITH p AS (
  SELECT CURRENT_DATE('Europe/Bratislava') AS today
),
tasks AS (
  SELECT task_gid,
    ANY_VALUE(platform) AS platform, ANY_VALUE(country) AS country,
    ANY_VALUE(campaign_id) AS campaign_id, ANY_VALUE(type) AS type, ANY_VALUE(title) AS title
  FROM `__DS__.agent_tasks`
  GROUP BY task_gid
),
done AS (
  SELECT t.*, MIN(DATE(a.completed_at, 'Europe/Bratislava')) AS done_date
  FROM tasks t
  JOIN `__DS__.actions_log` a USING (task_gid)
  GROUP BY t.task_gid, t.platform, t.country, t.campaign_id, t.type, t.title
),
due AS (
  SELECT d.*, n AS eval_day
  FROM done d
  CROSS JOIN UNNEST([7, 14]) AS n
  CROSS JOIN p
  WHERE DATE_ADD(d.done_date, INTERVAL n + 1 DAY) <= p.today
    AND DATE_ADD(d.done_date, INTERVAL n DAY) >= DATE_SUB(p.today, INTERVAL 10 DAY)
    AND NOT EXISTS (
      SELECT 1 FROM `__DS__.action_outcomes` o
      WHERE o.task_gid = d.task_gid AND o.eval_day = n
    )
)
SELECT
  due.task_gid, due.eval_day, due.platform, due.country, due.campaign_id, due.type, due.title, due.done_date,
  SUM(IF(f.date < due.done_date, f.cost_eur, 0)) AS cost_before,
  SUM(IF(f.date < due.done_date, f.conv_value_eur, 0)) AS value_before,
  SUM(IF(f.date < due.done_date, f.conversions, 0)) AS conv_before,
  SUM(IF(f.date > due.done_date, f.cost_eur, 0)) AS cost_after,
  SUM(IF(f.date > due.done_date, f.conv_value_eur, 0)) AS value_after,
  SUM(IF(f.date > due.done_date, f.conversions, 0)) AS conv_after
FROM due
LEFT JOIN `__DS__.v_daily_perf` f
  ON (due.platform IN ('BOTH', '') OR due.platform IS NULL OR f.platform = due.platform)
 AND (due.country IN ('ALL', '') OR due.country IS NULL OR f.country = due.country)
 AND (IFNULL(due.campaign_id, '') = '' OR f.campaign_id = due.campaign_id)
 AND f.date BETWEEN DATE_SUB(due.done_date, INTERVAL due.eval_day DAY)
                AND DATE_ADD(due.done_date, INTERVAL due.eval_day DAY)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
