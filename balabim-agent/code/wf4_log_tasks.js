// Asana create responses (same order as the IF "true" branch) -> agent_tasks rows.
const planned = $('Is New Task?').all(0);
const created = new Date().toISOString();
return $input.all().map((item, i) => {
  const p = planned[i].json;
  const task = item.json.data || item.json;
  return {
    json: {
      task_gid: String(task.gid),
      created_at: created,
      alert_keys: p.alert_keys.join(','),
      platform: p.platform,
      country: p.country,
      campaign_id: p.campaign_id,
      type: p.type,
      priority: p.priority,
      title: p.title,
      source: p.source,
      permalink_url: task.permalink_url || '',
    },
  };
});
