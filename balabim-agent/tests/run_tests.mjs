// Runs the Code-node JavaScript exactly as shipped in n8n/*.json against mocked
// n8n globals ($, $input, $today). Usage: node tests/run_tests.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const fixture = (f) => JSON.parse(readFileSync(join(ROOT, 'tests', 'fixtures', f), 'utf8'));

// Minimal Luxon DateTime stand-in (only what the nodes use).
class LDate {
  constructor(iso) { this.d = new Date(`${iso}T00:00:00Z`); }
  static of(date) { return new LDate(date.toISOString().slice(0, 10)); }
  plus({ days }) { const n = new Date(this.d); n.setUTCDate(n.getUTCDate() + days); return LDate.of(n); }
  minus({ days }) { return this.plus({ days: -days }); }
  toISODate() { return this.d.toISOString().slice(0, 10); }
  get weekday() { return this.d.getUTCDay() || 7; }
}

const items = (arr) => arr.map((json) => ({ json }));

function run(wfFile, nodeName, { input = [], nodes = {}, today = '2026-09-25', branches = {} } = {}) {
  const wf = JSON.parse(readFileSync(join(ROOT, 'n8n', wfFile), 'utf8'));
  const node = wf.nodes.find((n) => n.name === nodeName);
  assert.ok(node, `node ${nodeName} not found in ${wfFile}`);
  const lookup = (name) => {
    const data = nodes[name];
    if (!data) throw new Error(`test did not mock $('${name}')`);
    return {
      all: (branch) => (branch !== undefined && branches[name] ? branches[name][branch] : data),
      first: () => data[0],
    };
  };
  const fn = new Function('$input', '$', '$today', node.parameters.jsCode);
  return fn({ all: () => input, first: () => input[0] }, lookup, new LDate(today));
}

let passed = 0;
function test(name, body) {
  try { body(); passed += 1; console.log(`✓ ${name}`); } catch (e) { console.error(`✗ ${name}\n  ${e.stack}`); process.exitCode = 1; }
}

const settings = JSON.parse(readFileSync(join(ROOT, 'config', 'settings.example.json'), 'utf8'));
const fx = { rates: { '2026-09-22': { CZK: 24.5, HUF: 390, PLN: 4.25, RON: 4.97 }, '2026-09-24': { CZK: 24.4, HUF: 392, PLN: 4.26, RON: 4.98 } } };
const accounts = items([
  { platform: 'GOOGLE_ADS', account_id: '123-456-7891', country: 'CZ', currency: 'CZK', active: 'TRUE' },
  { platform: 'GOOGLE_ADS', account_id: '123-456-7890', country: 'SK', currency: 'EUR', active: 'TRUE' },
  { platform: 'META', account_id: 'act_1000000000000001', country: 'MULTI', currency: 'EUR', active: 'TRUE' },
  { platform: 'META', account_id: 'act_999', country: 'HU', currency: 'HUF', active: 'FALSE' },
]);

// ------------------------------------------------------------------ WF1
test('WF1 Config computes date windows and fills GAQL', () => {
  const [{ json: c }] = run('WF1_ingest.json', 'Config');
  assert.equal(c.until, '2026-09-24');
  assert.equal(c.since, '2026-09-18');
  assert.equal(c.st_since, '2026-08-26');
  assert.match(c.gaql_campaigns, /BETWEEN '2026-09-18' AND '2026-09-24'/);
  assert.doesNotMatch(c.gaql_search_terms, /\{/);
  assert.deepEqual(JSON.parse(c.meta_time_range), { since: '2026-09-18', until: '2026-09-24' });
});

test('WF1 account filters respect platform and active flag', () => {
  assert.equal(run('WF1_ingest.json', 'Google Accounts', { input: accounts }).length, 2);
  assert.equal(run('WF1_ingest.json', 'Meta Accounts', { input: accounts }).length, 1);
});

test('WF1 Google Ads rows are converted to EUR and mapped to country', () => {
  const out = run('WF1_ingest.json', 'Normalize GAds Perf', {
    input: items(fixture('gads_campaigns.json')),
    nodes: { FX: items([fx]), Accounts: accounts },
  }).map((i) => i.json);
  assert.equal(out.length, 2);
  const cz = out.find((r) => r.country === 'CZ');
  assert.equal(cz.fx_rate, 24.5); // 2026-09-23 has no fixing -> last one on or before (09-22)
  assert.equal(cz.cost_eur, 100);
  assert.equal(cz.conv_value_eur, 1000);
  assert.equal(cz.search_lost_is_budget, 0.31);
  assert.equal(cz.account_id, '1234567891');
  const sk = out.find((r) => r.country === 'SK');
  assert.equal(sk.cost_eur, 50);
  assert.equal(sk.search_is, null);
});

test('WF1 Meta rows pick one purchase action type and resolve MULTI account by campaign name', () => {
  const out = run('WF1_ingest.json', 'Normalize Meta Perf', {
    input: items([fixture('meta_insights.json')]),
    nodes: { Config: run('WF1_ingest.json', 'Config'), FX: items([fx]), Accounts: accounts },
  }).map((i) => i.json);
  assert.equal(out.length, 2);
  const hu = out.find((r) => r.country === 'HU');
  assert.equal(hu.conversions, 4); // omni_purchase wins over purchase (no double count)
  assert.equal(hu.conv_value_eur, 400);
  assert.equal(hu.clicks, 30);
  assert.equal(out.find((r) => r.adset_id === '222').country, 'RO');
});

test('WF1 Meta issues: learning limited ad sets and problem ads', () => {
  const cfg = run('WF1_ingest.json', 'Config');
  const adsets = run('WF1_ingest.json', 'Normalize Meta Issues', {
    input: items([{ data: [
      { id: '1', name: 'HU | Broad', account_id: '1000000000000001', campaign_id: '9', campaign: { name: 'HU_Prospecting' }, learning_stage_info: { status: 'FAIL' } },
      { id: '2', name: 'HU | LAL', account_id: '1000000000000001', campaign_id: '9', campaign: { name: 'HU_Prospecting' }, learning_stage_info: { status: 'SUCCESS' } },
    ] }]),
    nodes: { Config: cfg, Accounts: accounts },
  });
  assert.equal(adsets.length, 1);
  assert.equal(adsets[0].json.issue, 'LEARNING_LIMITED');
  const ads = run('WF1_ingest.json', 'Normalize Meta Issues', {
    input: items([{ data: [{ id: '5', name: 'Video 1', account_id: '1000000000000001', adset_id: '1', campaign_id: '9', campaign: { name: 'SK_Retargeting' }, effective_status: 'DISAPPROVED', issues_info: [{ error_summary: 'Policy' }] }] }]),
    nodes: { Config: cfg, Accounts: accounts },
  });
  assert.equal(ads[0].json.country, 'SK');
  assert.equal(ads[0].json.detail, 'Policy');
});

test('WF1 missing FX rate fails loudly instead of writing wrong EUR values', () => {
  assert.throws(() => run('WF1_ingest.json', 'Normalize GAds Perf', {
    input: items(fixture('gads_campaigns.json')),
    nodes: { FX: items([{ rates: {} }]), Accounts: accounts },
  }), /Chýba kurz/);
});

// ------------------------------------------------------------------ WF2
const targets = items([
  { country: 'SK', platform: 'GOOGLE_ADS', active: 'TRUE', monthly_budget_eur: '3000', kpi: 'ROAS', target_roas: '4', asana_assignee_gid: 'u-sk-g' },
  { country: 'SK', platform: 'META', active: 'TRUE', monthly_budget_eur: '1 500', kpi: 'ROAS', target_roas: '3,5', asana_assignee_gid: 'u-sk-m' },
  { country: 'CZ', platform: 'GOOGLE_ADS', active: 'TRUE', monthly_budget_eur: '2000', kpi: 'CPA', target_cpa_eur: '20' },
  { country: 'HU', platform: 'META', active: 'TRUE', monthly_budget_eur: '1000', kpi: 'ROAS', target_roas: '3', max_frequency: '' },
  { country: 'PL', platform: 'GOOGLE_ADS', active: 'FALSE', monthly_budget_eur: '1000' },
]);

function rulesRun() {
  const s = fixture('rules_scenario.json');
  return run('WF2_rules.json', 'Rules', {
    nodes: {
      Config: run('WF2_rules.json', 'Config'),
      Targets: targets,
      'BQ Perf': items(s.perf),
      'BQ Search Terms': items(s.search_terms),
      'BQ Issues': items(s.issues),
      'BQ Meta Freq': items([{}]), // empty BigQuery result = one empty item
    },
  }).map((i) => i.json);
}

test('WF2 rules detect outage, pacing, KPI, waste, missing data, search terms, policy', () => {
  const f = rulesRun();
  const by = (rule, country) => f.filter((x) => x.rule === rule && (!country || x.country === country));
  assert.equal(by('TRACKING_OUTAGE', 'SK')[0].severity, 'P1');
  assert.equal(by('PACING_OVER', 'SK')[0].severity, 'P2'); // +25 % vs tolerance 15 %
  assert.equal(by('KPI_BELOW_TARGET', 'SK').length, 1);
  assert.equal(by('WASTE_NO_CONV', 'SK')[0].scope_id, 'c-waste');
  assert.equal(by('NO_DATA', 'SK')[0].platform, 'META');
  assert.equal(by('SEARCH_TERMS', 'SK')[0].metrics.count, 2);
  assert.equal(by('POLICY', 'SK')[0].severity, 'P2');
  assert.equal(by('SCALE_BUDGET', 'CZ').length, 1);
  assert.equal(by('UNMAPPED').length, 1);
  assert.equal(by('NO_DATA', 'PL').length, 0, 'inactive target rows are ignored');
  assert.equal(f[0].severity, 'P1', 'sorted by severity');
});

test('WF2 alert keys are stable and unique', () => {
  const f = rulesRun();
  assert.equal(new Set(f.map((x) => x.alert_key)).size, f.length);
  assert.ok(f.find((x) => x.alert_key === 'GOOGLE_ADS|SK|ALL|PACING_OVER|2026-09'));
  assert.ok(f.find((x) => x.alert_key === 'GOOGLE_ADS|SK|c-waste|WASTE_NO_CONV'));
});

test('WF2 CPA country in target produces no KPI finding', () => {
  assert.equal(rulesRun().filter((x) => x.country === 'CZ' && x.rule.startsWith('KPI')).length, 0);
});

test('WF2 findings are serialized for BigQuery', () => {
  const out = run('WF2_rules.json', 'Findings to BQ', { input: items(rulesRun()) });
  assert.equal(typeof out[0].json.metrics, 'string');
  assert.ok(!('suggested_steps' in out[0].json));
});

// ------------------------------------------------------------------ WF3
const asanaSettings = {
  ...settings.asana,
  project_gid: 'proj',
  section_new_gid: 'sec-new',
  default_assignee_gid: 'u-default',
  fields: {
    country: { gid: 'f-country', options: { SK: 'o-sk', CZ: 'o-cz', ALL: 'o-all' } },
    platform: { gid: 'f-platform', options: { GOOGLE_ADS: 'o-g', META: 'o-m', BOTH: 'o-b' } },
    type: { gid: 'f-type', options: { TRACKING: 'o-tr', BUDGET: 'o-bu', PERFORMANCE: 'o-pe', WASTE: 'o-wa' } },
    priority: { gid: 'f-prio', options: { P1: 'o-p1', P2: 'o-p2', P3: 'o-p3' } },
    alert_id: { gid: 'f-alert' },
    impact: { gid: 'f-impact' },
  },
};
const openAsana = items([{ data: [
  { gid: 't-open', name: 'SK Google Ads: search termy', permalink_url: 'https://app.asana.com/t-open',
    custom_fields: [{ gid: 'f-alert', text_value: 'GOOGLE_ADS|SK|ALL|SEARCH_TERMS|2026-09' }, { gid: 'f-prio', enum_value: { name: 'P3' } }] },
], next_page: null }]);

function wf3Config() {
  const [{ json: c }] = run('WF3_ai_analyst.json', 'Config');
  return items([{ ...c, asana: asanaSettings }]);
}

test('WF3 splits already-tracked findings from new ones and builds a structured-output request', () => {
  const findings = rulesRun();
  const [{ json: b }] = run('WF3_ai_analyst.json', 'Build Request', {
    nodes: { Config: wf3Config(), 'Findings In': items(findings), 'Asana Open Tasks': openAsana, 'BQ Outcomes': items([{}]) },
  });
  assert.equal(b.covered.length, 1);
  assert.equal(b.fresh.length, findings.length - 1);
  assert.equal(b.body.output_config.format.type, 'json_schema');
  assert.equal(b.body.thinking.type, 'adaptive');
  assert.match(b.body.system, /Maximálne 10 úloh/);
  assert.match(b.body.messages[0].content, /SK Google Ads: search termy/);
});

function parseWith(response) {
  const findings = rulesRun();
  const config = wf3Config();
  const build = run('WF3_ai_analyst.json', 'Build Request', {
    nodes: { Config: config, 'Findings In': items(findings), 'Asana Open Tasks': openAsana, 'BQ Outcomes': items([{}]) },
  });
  return run('WF3_ai_analyst.json', 'Parse Tasks', {
    input: items([response]),
    nodes: { Config: config, 'Build Request': build },
  }).map((i) => i.json);
}

test('WF3 parse keeps valid AI tasks, drops invented keys and backfills uncovered P1', () => {
  const ai = {
    summary: 'Test',
    tasks: [{
      alert_keys: ['GOOGLE_ADS|SK|ALL|KPI_BELOW_TARGET', 'GOOGLE_ADS|SK|c-waste|WASTE_NO_CONV', 'INVENTED|KEY'],
      title: 'SK Google Ads: ROAS pod cieľom', country: 'SK', platform: 'GOOGLE_ADS', type: 'PERFORMANCE',
      priority: 'P2', diagnosis: 'd', action_steps: ['a'], expected_impact: 'x', expected_impact_eur: 500, campaign_id: '',
    }, {
      alert_keys: ['ONLY|INVENTED'], title: 'bad', country: 'SK', platform: 'META', type: 'OTHER', priority: 'P3',
      diagnosis: '', action_steps: [], expected_impact: '', expected_impact_eur: 0, campaign_id: '',
    }],
  };
  const tasks = parseWith({ stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify(ai) }] });
  const aiTasks = tasks.filter((t) => t.source === 'ai');
  assert.equal(aiTasks.length, 1);
  assert.deepEqual(aiTasks[0].alert_keys, ['GOOGLE_ADS|SK|ALL|KPI_BELOW_TARGET', 'GOOGLE_ADS|SK|c-waste|WASTE_NO_CONV']);
  const p1 = tasks.filter((t) => t.source === 'template').map((t) => t.priority);
  assert.deepEqual(p1, ['P1', 'P1'], 'outage + missing Meta data are backfilled');
  assert.equal(tasks.filter((t) => t.source === 'update').length, 1);
});

test('WF3 parse falls back to rule-based tasks on API error / refusal', () => {
  for (const res of [{ error: { message: 'timeout' } }, { stop_reason: 'refusal', content: [] }, { stop_reason: 'end_turn', content: [{ type: 'text', text: 'not json' }] }]) {
    const tasks = parseWith(res);
    const templ = tasks.filter((t) => t.source === 'template');
    assert.ok(templ.length >= 2 && templ.length <= 10 + 2);
    assert.ok(tasks[0].ai_problem);
  }
});

// ------------------------------------------------------------------ WF4
function wf4Plan(tasks, today = '2026-09-25') {
  const [{ json: c }] = run('WF4_asana.json', 'Config');
  return run('WF4_asana.json', 'Plan Actions', {
    today,
    nodes: {
      Config: items([{ ...c, asana: asanaSettings }]),
      'Tasks In': items(tasks),
      Targets: targets,
      'Asana Open Tasks': openAsana,
    },
  }).map((i) => i.json);
}

test('WF4 creates new tasks with custom fields and comments on tracked ones', () => {
  const tasks = parseWith({ error: { message: 'x' } });
  const plan = wf4Plan(tasks);
  const comments = plan.filter((p) => p.action === 'comment');
  assert.equal(comments.length, 1);
  assert.equal(comments[0].task_gid, 't-open');
  const outage = plan.find((p) => p.action === 'create' && p.alert_keys[0].includes('TRACKING_OUTAGE'));
  const d = outage.asana_body.data;
  assert.equal(d.custom_fields['f-prio'], 'o-p1');
  assert.equal(d.custom_fields['f-country'], 'o-sk');
  assert.equal(d.custom_fields['f-type'], 'o-tr');
  assert.equal(d.custom_fields['f-alert'], outage.alert_keys.join(', '));
  assert.equal(d.assignee, 'u-sk-g');
  assert.equal(d.due_on, '2026-09-28', 'P1 due Saturday -> moved to Monday');
  assert.deepEqual(d.memberships, [{ project: 'proj', section: 'sec-new' }]);
  assert.match(d.notes, /ODPORÚČANÉ KROKY/);
});

test('WF4 caps new non-P1 tasks per run but never drops P1', () => {
  const many = Array.from({ length: 15 }, (_, i) => ({
    alert_keys: [`GOOGLE_ADS|SK|c${i}|WASTE_NO_CONV`], title: `t${i}`, country: 'SK', platform: 'GOOGLE_ADS',
    type: 'WASTE', priority: i < 2 ? 'P1' : 'P3', diagnosis: '', action_steps: [], expected_impact_eur: 0, findings: [],
  }));
  const plan = wf4Plan(many);
  assert.equal(plan.filter((p) => p.action === 'create').length, 10);
  assert.equal(plan.filter((p) => p.priority === 'P1').length, 2);
});

test('WF4 log rows pair Asana responses with planned tasks', () => {
  const planned = wf4Plan(parseWith({ error: {} })).filter((p) => p.action === 'create');
  const out = run('WF4_asana.json', 'Log Created Tasks', {
    input: items(planned.map((p, i) => ({ data: { gid: `new-${i}`, permalink_url: `u${i}` } }))),
    nodes: { 'Is New Task?': items(planned) },
    branches: { 'Is New Task?': [items(planned), []] },
  }).map((i) => i.json);
  assert.equal(out[0].task_gid, 'new-0');
  assert.equal(out[0].alert_keys, planned[0].alert_keys.join(','));
});

test('WF4 P1 digest e-mail only when needed', () => {
  assert.equal(run('WF4_asana.json', 'P1 Digest', { input: items([{ priority: 'P2', ai_problem: '' }]) }).length, 0);
  const [{ json: m }] = run('WF4_asana.json', 'P1 Digest', {
    input: items([{ priority: 'P1', title: 'Výpadok', country: 'SK', platform: 'META', action: 'create', ai_problem: '' }]),
  });
  assert.match(m.subject, /1× P1/);
});

// ------------------------------------------------------------------ WF5
test('WF5 extracts completed-task events once per task', () => {
  const out = run('WF5_feedback_webhook.json', 'Completed Events', {
    input: items([
      { action: 'changed', resource: { gid: '1', resource_type: 'task' }, change: { field: 'completed' } },
      { action: 'changed', resource: { gid: '1', resource_type: 'task' }, change: { field: 'completed' } },
      { action: 'changed', resource: { gid: '2', resource_type: 'task' }, change: { field: 'name' } },
      { action: 'added', resource: { gid: '3', resource_type: 'story' } },
    ]),
  });
  assert.deepEqual(out.map((i) => i.json.task_gid), ['1']);
  const log = run('WF5_feedback_webhook.json', 'To actions_log', {
    input: items([{ data: { gid: '1', completed: true, completed_at: '2026-09-20T10:00:00Z', completed_by: { name: 'Jana' } } }, { data: { gid: '2', completed: false } }]),
  });
  assert.equal(log.length, 1);
  assert.equal(log[0].json.completed_by, 'Jana');
});

test('WF5b verdicts and comment text', () => {
  const out = run('WF5b_impact_eval.json', 'Format Outcome', {
    input: items([
      { task_gid: 'a', eval_day: 7, type: 'PERFORMANCE', platform: 'GOOGLE_ADS', country: 'SK', campaign_id: '', done_date: '2026-09-10',
        cost_before: 1000, value_before: 3000, conv_before: 30, cost_after: 1000, value_after: 4000, conv_after: 40 },
      { task_gid: 'b', eval_day: 7, type: 'WASTE', platform: 'META', country: 'HU', campaign_id: '1', done_date: '2026-09-10',
        cost_before: 500, value_before: 0, conv_before: 0, cost_after: 100, value_after: 0, conv_after: 0 },
      { task_gid: 'c', eval_day: 14, type: 'PERFORMANCE', platform: 'META', country: 'RO', campaign_id: '', done_date: '2026-09-01',
        cost_before: 0, value_before: 0, conv_before: 0, cost_after: 0, value_after: 0, conv_after: 0 },
    ]),
  }).map((i) => i.json);
  assert.deepEqual(out.map((o) => o.verdict), ['IMPROVED', 'IMPROVED', 'NO_DATA']);
  assert.match(out[0].comment_text, /ROAS: 3 → 4/);
  const rowsOut = run('WF5b_impact_eval.json', 'To Outcomes', { nodes: { 'Format Outcome': items(out) } });
  assert.equal(rowsOut[2].json.eval_day, 14);
});

// ------------------------------------------------------------------ WF6
test('WF6 weekly status: table, status type and Asana body', () => {
  const [{ json: c }] = run('WF6_weekly_report.json', 'Config', { today: '2026-09-28' });
  const config = items([{ ...c, asana: asanaSettings }]);
  const build = run('WF6_weekly_report.json', 'Build Weekly', {
    nodes: {
      Config: config,
      'BQ Weekly': items([
        { platform: 'GOOGLE_ADS', country: 'SK', cost_7d: 700, value_7d: 1400, conv_7d: 20, cost_p7: 700, value_p7: 2800, conv_p7: 30 },
        { platform: 'META', country: 'HU', cost_7d: 300, value_7d: 600, conv_7d: 5, cost_p7: 300, value_p7: 900, conv_p7: 6 },
      ]),
      'BQ MTD': items([{ platform: 'GOOGLE_ADS', country: 'SK', cost_mtd: 2800, days_elapsed: 27, days_in_month: 30 }]),
      Targets: targets,
      'Asana Open Tasks': openAsana,
    },
  });
  const b = build[0].json;
  assert.equal(b.status_type, 'at_risk'); // SK ROAS 2 vs 4 and HU 2 vs 3
  assert.equal(b.table.length, 2);
  const [{ json: out }] = run('WF6_weekly_report.json', 'Compose Status', {
    input: items([{ stop_reason: 'end_turn', content: [{ type: 'text', text: '• Celkovo: test' }] }]),
    nodes: { Config: config, 'Build Weekly': build },
  });
  assert.equal(out.status_body.data.parent, 'proj');
  assert.match(out.status_body.data.text, /Celkovo: test/);
  assert.match(out.status_body.data.text, /SK Google Ads/);
});

// ------------------------------------------------------------------ error handler
test('Error handler formats an alert', () => {
  const [{ json: e }] = run('WF_error.json', 'Format Error', {
    input: items([{ workflow: { name: 'WF1' }, execution: { lastNodeExecuted: 'FX', error: { message: 'boom' } } }]),
  });
  assert.match(e.subject, /WF1/);
  assert.match(e.text, /boom/);
});


console.log(`\n${passed} testov prešlo${process.exitCode ? ', niektoré zlyhali' : ''}.`);
