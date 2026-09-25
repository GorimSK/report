// Weekly KPI table per country × platform + status type + Claude request body.
const cfg = $('Config').first().json;
const weekly = rows($('BQ Weekly').all());
const mtd = Object.fromEntries(rows($('BQ MTD').all()).map((r) => [`${r.platform}|${r.country}`, r]));
const targets = {};
for (const { json: t } of $('Targets').all()) {
  if (isActive(t.active)) targets[`${String(t.platform).trim().toUpperCase()}|${String(t.country).trim().toUpperCase()}`] = t;
}
const open = openTasks($('Asana Open Tasks').all(), cfg.asana.fields.alert_id.gid, cfg.asana.fields.priority.gid);

let atRisk = 0;
const table = weekly.map((r) => {
  const key = `${r.platform}|${r.country}`;
  const t = targets[key] || {};
  const m = mtd[key] || {};
  const roas = safeDiv(r.value_7d, r.cost_7d), roasP = safeDiv(r.value_p7, r.cost_p7);
  const budget = num(t.monthly_budget_eur);
  const projected = num(m.days_elapsed) ? (num(m.cost_mtd) / num(m.days_elapsed)) * num(m.days_in_month) : null;
  const pacing = budget && projected !== null ? projected / budget - 1 : null;
  const targetRoas = num(t.target_roas);
  if (targetRoas && roas !== null && roas < targetRoas * 0.85) atRisk += 1;
  return {
    krajina: r.country, platforma: PLATFORM_LABEL[r.platform] || r.platform,
    naklady_7d: round(r.cost_7d, 0), obrat_7d: round(r.value_7d, 0), konverzie_7d: round(r.conv_7d, 1),
    roas_7d: roas === null ? null : round(roas), roas_minuly_tyzden: roasP === null ? null : round(roasP),
    ciel_roas: targetRoas || null,
    mtd_naklady: round(m.cost_mtd, 0), mesacny_rozpocet: budget || null, projekcia_vs_rozpocet: pacing === null ? null : round(pacing, 3),
  };
});
const openP1 = open.filter((t) => t.priority === 'P1').length;
const status_type = openP1 ? 'off_track' : atRisk >= 2 ? 'at_risk' : 'on_track';
const totals = table.reduce((a, r) => ({ cost: a.cost + r.naklady_7d, value: a.value + r.obrat_7d }), { cost: 0, value: 0 });

const body = {
  model: cfg.anthropic_model,
  max_tokens: 4000,
  thinking: { type: 'adaptive' },
  output_config: { effort: 'low' },
  fallbacks: 'default',
  system: cfg.weekly_system,
  messages: [{
    role: 'user',
    content: [
      `Týždeň končiaci ${cfg.yesterday}.`,
      '', 'KPI (EUR):', JSON.stringify(table, null, 1),
      '', `Otvorené úlohy agenta (${open.length}):`, open.map((t) => `- [${t.priority || '?'}] ${t.name}`).join('\n') || '(žiadne)',
    ].join('\n'),
  }],
};

return [{ json: { table, status_type, totals, open_count: open.length, body } }];
