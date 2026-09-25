// Claude response -> validated task list. Falls back to rule-based tasks if the call
// failed or returned something unusable, so P1 problems always reach Asana.
const cfg = $('Config').first().json;
const { fresh, covered, has_new } = $('Build Request').first().json;
const byKey = Object.fromEntries(fresh.map((f) => [f.alert_key, f]));
const res = $input.first().json || {};

let aiTasks = null;
let summary = '';
let problem = '';
if (has_new) {
  if (res.error) problem = `HTTP chyba: ${JSON.stringify(res.error).slice(0, 300)}`;
  else if (res.stop_reason === 'refusal') problem = 'Model odmietol požiadavku (refusal).';
  else if (res.stop_reason === 'max_tokens') problem = 'Odpoveď bola orezaná (max_tokens).';
  else {
    try {
      const text = (res.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('');
      const parsed = JSON.parse(text);
      summary = parsed.summary || '';
      aiTasks = (parsed.tasks || [])
        .map((t) => ({ ...t, alert_keys: [...new Set((t.alert_keys || []).filter((k) => byKey[k]))] }))
        .filter((t) => t.alert_keys.length > 0)
        .map((t) => ({ ...t, source: 'ai', findings: t.alert_keys.map((k) => byKey[k]) }));
    } catch (e) {
      problem = `Nevalidný JSON: ${e.message}`;
    }
  }
}

let tasks = [];
if (aiTasks) {
  tasks = aiTasks;
  // Guarantee: every P1 finding ends up in some task.
  const used = new Set(tasks.flatMap((t) => t.alert_keys));
  for (const f of fresh) if (f.severity === 'P1' && !used.has(f.alert_key)) tasks.push(taskFromFinding(f, 'template'));
} else if (has_new) {
  // Fallback: one task per finding, P1 + P2 first, capped.
  tasks = fresh
    .slice()
    .sort((a, b) => PRIORITY_ORDER[a.severity] - PRIORITY_ORDER[b.severity])
    .filter((f, i) => f.severity === 'P1' || i < cfg.max_new_tasks_per_run)
    .map((f) => taskFromFinding(f, 'template'));
}

// Findings already tracked in Asana become comment updates on their task (handled in WF4).
tasks.push(...covered.map((f) => taskFromFinding(f, 'update')));

return tasks.map((t) => ({ json: { ...t, run_summary: summary, ai_problem: problem } }));
