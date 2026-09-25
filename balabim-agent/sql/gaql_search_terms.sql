SELECT
  customer.id,
  customer.currency_code,
  campaign.id,
  campaign.name,
  ad_group.id,
  ad_group.name,
  search_term_view.search_term,
  metrics.cost_micros,
  metrics.clicks,
  metrics.conversions,
  metrics.conversions_value
FROM search_term_view
WHERE segments.date BETWEEN '{st_since}' AND '{until}'
  AND metrics.cost_micros > 0
ORDER BY metrics.cost_micros DESC
LIMIT 2000
