// Shared helpers. build.py prepends this file to every Code node, so keep it
// free of top-level side effects and never redeclare these names in node code.
const COUNTRIES = ['SK', 'CZ', 'HU', 'PL', 'RO', 'BG', 'HR', 'SI', 'GR'];
const PLATFORM_LABEL = { GOOGLE_ADS: 'Google Ads', META: 'Meta Ads', BOTH: 'Google + Meta' };

// Accepts numbers, API strings ("123.45") and sheet values ("3,5", "1 200 €").
function num(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(String(v).replace(/[\s€%]/g, '').replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}
const round = (v, d = 2) => Math.round(num(v) * 10 ** d) / 10 ** d;
const safeDiv = (a, b) => (num(b) === 0 ? null : num(a) / num(b));
const pct = (v) => (v === null || v === undefined ? 'n/a' : `${round(v * 100, 1)} %`);
const eur = (v) => `${round(v, 0).toLocaleString('sk-SK')} €`;
const fmt = (v, d = 2) => (v === null || v === undefined ? 'n/a' : String(round(v, d)));
const normId = (id) => String(id ?? '').replace(/^act_/, '').replace(/-/g, '').trim();
const isActive = (v) => !['FALSE', 'NIE', '0', 'NO'].includes(String(v ?? 'TRUE').trim().toUpperCase());

// Country from campaign name: SK_Search_Brand, "PMax | HU | Feed", "Meta-RO-Prospecting"...
function countryFromName(name) {
  const m = String(name || '').toUpperCase().match(/(?:^|[^A-Z])(SK|CZ|HU|PL|RO|BG|HR|SI|GR)(?=[^A-Z]|$)/);
  return m ? m[1] : 'UNKNOWN';
}

// Rows of the "accounts" sheet -> { 'GOOGLE_ADS|1234567890': {country, currency, name} }
function buildAccountMap(items) {
  const map = {};
  for (const { json: r } of items) {
    if (!isActive(r.active)) continue;
    const platform = String(r.platform || '').trim().toUpperCase();
    map[`${platform}|${normId(r.account_id)}`] = {
      country: String(r.country || '').trim().toUpperCase(),
      currency: String(r.currency || '').trim().toUpperCase(),
      name: r.account_name || '',
    };
  }
  return map;
}

// Account-level country wins; accounts marked MULTI fall back to the campaign name.
function resolveCountry(accountMap, platform, accountId, campaignName) {
  const acc = accountMap[`${platform}|${normId(accountId)}`];
  if (acc && COUNTRIES.includes(acc.country)) return acc.country;
  return countryFromName(campaignName);
}

// fx = Frankfurter time series response {rates: {'YYYY-MM-DD': {CZK: 24.3, ...}}}, base EUR.
// Returns units of `currency` per 1 EUR, using the latest rate on or before `date`.
function fxRate(fx, currency, date) {
  const cur = String(currency || 'EUR').toUpperCase();
  if (cur === 'EUR') return 1;
  if (cur === 'BGN') return 1.95583; // fixed conversion rate, BG uses EUR since 2026-01-01
  const rates = (fx && fx.rates) || {};
  const dates = Object.keys(rates).sort();
  let rate = null;
  for (const d of dates) if (d <= date && rates[d][cur]) rate = rates[d][cur];
  if (rate === null) for (const d of dates) if (rates[d][cur]) { rate = rates[d][cur]; break; }
  if (!rate) throw new Error(`Chýba kurz ECB pre ${cur} k ${date}`);
  return rate;
}

// n8n HTTP node may emit one item per array element or one item wrapping the array.
function unwrap(items, key) {
  const out = [];
  for (const { json } of items) {
    const parts = Array.isArray(json) ? json : [json];
    for (const p of parts) {
      if (p && Array.isArray(p[key])) out.push(...p[key]);
    }
  }
  return out;
}

// Rule -> Asana task type (used when a task is built from a finding without AI).
const RULE_TYPE = {
  TRACKING_OUTAGE: 'TRACKING', NO_DATA: 'DATA_QUALITY', UNMAPPED: 'DATA_QUALITY',
  PACING_OVER: 'BUDGET', PACING_UNDER: 'BUDGET',
  KPI_BELOW_TARGET: 'PERFORMANCE', KPI_WOW_DROP: 'PERFORMANCE', CAMPAIGN_DROP: 'PERFORMANCE',
  WASTE_NO_CONV: 'WASTE', SCALE_BUDGET: 'SCALE', CREATIVE_FATIGUE: 'CREATIVE',
  SEARCH_TERMS: 'SEARCH_TERMS', POLICY: 'POLICY', LEARNING_LIMITED: 'LEARNING',
};
const PRIORITY_ORDER = { P1: 0, P2: 1, P3: 2 };

// BigQuery nodes run with "Always Output Data", so an empty result is one empty item.
const rows = (items) => items.map((i) => i.json).filter((j) => j && Object.keys(j).length > 0);

// Alert-ID custom field text -> Set of alert keys.
const parseKeys = (text) => new Set(String(text || '').split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean));

// Open tasks of the Asana project (paginated HTTP output) -> [{gid, name, url, keys:Set, priority}]
function openTasks(items, alertFieldGid, priorityFieldGid) {
  return unwrap(items, 'data').map((t) => {
    const cf = (gid) => (t.custom_fields || []).find((c) => c.gid === gid);
    const alert = cf(alertFieldGid);
    const prio = priorityFieldGid ? cf(priorityFieldGid) : null;
    return {
      gid: t.gid,
      name: t.name,
      url: t.permalink_url,
      keys: parseKeys(alert && (alert.text_value ?? alert.display_value)),
      priority: prio ? ((prio.enum_value && prio.enum_value.name) || prio.display_value || '') : '',
    };
  });
}

// A finding turned into a task without AI (fallback, or update of an already-open task).
function taskFromFinding(f, source) {
  return {
    alert_keys: [f.alert_key],
    title: f.title.slice(0, 120),
    country: f.country,
    platform: f.platform,
    type: RULE_TYPE[f.rule] || 'PERFORMANCE',
    priority: f.severity,
    diagnosis: f.summary_line,
    action_steps: f.suggested_steps || [],
    expected_impact: '',
    expected_impact_eur: 0,
    campaign_id: f.campaign_id || '',
    source,
    findings: [f],
  };
}
