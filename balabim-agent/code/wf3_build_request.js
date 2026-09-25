// Split findings into those already tracked by an open Asana task (-> comment update,
// no AI needed) and new ones (-> Claude groups them into tasks).
const cfg = $('Config').first().json;
const findings = $('Findings In').all().map((i) => i.json).filter((f) => f.alert_key);
const open = openTasks($('Asana Open Tasks').all(), cfg.asana.fields.alert_id.gid);
const outcomes = rows($('BQ Outcomes').all());

const trackedKeys = new Set(open.flatMap((t) => [...t.keys]));
const covered = findings.filter((f) => trackedKeys.has(f.alert_key));
const fresh = findings.filter((f) => !trackedKeys.has(f.alert_key));

const compact = (f) => ({
  alert_key: f.alert_key, severity: f.severity, rule: f.rule, platform: f.platform, country: f.country,
  scope: f.scope_level === 'country' ? 'celá krajina' : `${f.scope_level}: ${f.scope_name}`,
  title: f.title, summary: f.summary_line, metrics: f.metrics,
});

const userContent = [
  `Dátum dát: ${cfg.yesterday} (včerajšok). Počet nových findings: ${fresh.length}.`,
  '',
  '## Nové findings',
  JSON.stringify(fresh.map(compact), null, 1),
  '',
  '## Otvorené tasky v Asane (už sa riešia, nezakladaj duplicitne)',
  open.length ? open.map((t) => `- ${t.name} [${[...t.keys].join(', ')}]`).join('\n') : '(žiadne)',
  '',
  '## Výsledky minulých zásahov (posledných 90 dní)',
  outcomes.length ? JSON.stringify(outcomes, null, 1) : '(zatiaľ žiadne)',
].join('\n');

const body = {
  model: cfg.anthropic_model,
  max_tokens: 16000,
  thinking: { type: 'adaptive' },
  output_config: {
    effort: cfg.anthropic_effort,
    format: { type: 'json_schema', schema: cfg.analyst_schema },
  },
  fallbacks: 'default',
  system: cfg.analyst_system.replaceAll('{{max_tasks}}', String(cfg.max_new_tasks_per_run)),
  messages: [{ role: 'user', content: userContent }],
};

return [{ json: { has_new: fresh.length > 0, fresh, covered, body } }];
