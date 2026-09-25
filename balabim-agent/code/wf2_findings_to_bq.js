// findings -> BigQuery rows (nested objects serialized to JSON strings).
const created = new Date().toISOString();
return $input.all().map(({ json: f }) => ({
  json: {
    run_date: f.run_date,
    alert_key: f.alert_key,
    rule: f.rule,
    severity: f.severity,
    platform: f.platform,
    country: f.country,
    scope_level: f.scope_level,
    scope_id: f.scope_id,
    scope_name: f.scope_name,
    title: f.title,
    summary_line: f.summary_line,
    metrics: JSON.stringify(f.metrics || {}),
    created_at: created,
  },
}));
