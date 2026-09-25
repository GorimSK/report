// Decide per task: create a new Asana task, or comment on the open task that
// already tracks one of its alert keys. Builds the Asana request bodies.
const cfg = $('Config').first().json;
const A = cfg.asana;
const tasks = $('Tasks In').all().map((i) => i.json).filter((t) => t.alert_keys);
const open = openTasks($('Asana Open Tasks').all(), A.fields.alert_id.gid);

const owners = {};
for (const { json: t } of $('Targets').all()) {
  if (t.asana_assignee_gid) owners[`${String(t.platform).trim().toUpperCase()}|${String(t.country).trim().toUpperCase()}`] = String(t.asana_assignee_gid).trim();
}
function assignee(t) {
  const platform = t.platform === 'BOTH' ? 'GOOGLE_ADS' : t.platform;
  return owners[`${platform}|${t.country}`] || A.default_assignee_gid || null;
}

// Due date in calendar days, moved off weekends.
function dueOn(priority) {
  let d = $today.plus({ days: A.due_days[priority] ?? 7 });
  while (d.weekday > 5) d = d.plus({ days: 1 });
  return d.toISODate();
}

function enumValue(field, key) {
  const opt = field && field.options && field.options[key];
  return opt ? { [field.gid]: opt } : {};
}

function findingLines(t) {
  return (t.findings || []).map((f) => `• [${f.severity}] ${f.title}\n  ${f.summary_line}`).join('\n');
}

function notes(t) {
  const parts = [
    `🤖 Vytvorené PPC agentom (Balabim) – ${$today.toISODate()}${t.source === 'template' ? ' – šablóna bez AI' : ''}`,
    '',
    'DIAGNÓZA',
    t.diagnosis,
    '',
    'ODPORÚČANÉ KROKY',
    ...(t.action_steps || []).map((s, i) => `${i + 1}. ${s}`),
  ];
  if (t.expected_impact) parts.push('', 'OČAKÁVANÝ DOPAD', t.expected_impact);
  parts.push(
    '', 'DÁTA', findingLines(t),
    '', '—',
    'Agent iba navrhuje, zmeny v účtoch robí PPC špecialista.',
    'Po dokončení tasku agent o 7 a 14 dní vyhodnotí dopad a pridá komentár.',
  );
  return parts.join('\n');
}

const out = [];
const usedKeys = new Set();
const comments = {}; // task_gid -> lines
let created = 0;

const sorted = tasks.slice().sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
for (const t of sorted) {
  const keys = t.alert_keys.filter((k) => !usedKeys.has(k));
  if (!keys.length) continue;
  keys.forEach((k) => usedKeys.add(k));

  const existing = open.find((o) => keys.some((k) => o.keys.has(k)));
  if (existing) {
    (comments[existing.gid] ||= { task: existing, lines: [], priority: t.priority, t }).lines.push(findingLines(t));
    continue;
  }
  if (t.priority !== 'P1' && created >= cfg.max_new_tasks_per_run) continue;
  created += 1;

  const custom_fields = {
    ...enumValue(A.fields.country, t.country),
    ...enumValue(A.fields.platform, t.platform),
    ...enumValue(A.fields.type, t.type),
    ...enumValue(A.fields.priority, t.priority),
    [A.fields.alert_id.gid]: keys.join(', '),
  };
  if (A.fields.impact && A.fields.impact.gid) custom_fields[A.fields.impact.gid] = Math.round(num(t.expected_impact_eur));

  const data = {
    name: t.title.slice(0, 120),
    notes: notes(t),
    projects: [A.project_gid],
    due_on: dueOn(t.priority),
    custom_fields,
  };
  if (A.section_new_gid) data.memberships = [{ project: A.project_gid, section: A.section_new_gid }];
  const who = assignee(t);
  if (who) data.assignee = who;

  out.push({
    json: {
      action: 'create', priority: t.priority, title: data.name, country: t.country, platform: t.platform,
      type: t.type, campaign_id: t.campaign_id || '', alert_keys: keys, source: t.source,
      ai_problem: t.ai_problem || '', asana_body: { data },
    },
  });
}

for (const [gid, c] of Object.entries(comments)) {
  out.push({
    json: {
      action: 'comment', task_gid: gid, priority: c.priority, title: c.task.name, url: c.task.url,
      country: c.t.country, platform: c.t.platform, ai_problem: c.t.ai_problem || '',
      asana_body: { data: { text: `🔁 Agent ${$today.toISODate()}: problém stále trvá.\n\n${c.lines.join('\n')}` } },
    },
  });
}
return out;
