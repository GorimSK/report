// Rows from "Format Outcome" (same order as the comment requests) -> action_outcomes.
const evaluated = new Date().toISOString();
return $('Format Outcome').all().map(({ json: r }) => ({
  json: {
    task_gid: String(r.task_gid),
    eval_day: num(r.eval_day),
    evaluated_at: evaluated,
    platform: r.platform,
    country: r.country,
    campaign_id: r.campaign_id || '',
    type: r.type,
    title: r.title,
    done_date: String(r.done_date).slice(0, 10),
    cost_before: num(r.cost_before),
    value_before: num(r.value_before),
    conv_before: num(r.conv_before),
    cost_after: num(r.cost_after),
    value_after: num(r.value_after),
    conv_after: num(r.conv_after),
    verdict: r.verdict,
  },
}));
