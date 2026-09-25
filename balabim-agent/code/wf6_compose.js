// Claude commentary (or a fallback note) + KPI table -> Asana project status update.
const cfg = $('Config').first().json;
const b = $('Build Weekly').first().json;
const res = $input.first().json || {};
const ai = res.stop_reason && res.stop_reason !== 'refusal'
  ? (res.content || []).filter((c) => c.type === 'text').map((c) => c.text).join('').trim()
  : '';

const line = (r) => `• ${r.krajina} ${r.platforma}: náklady ${eur(r.naklady_7d)}, ROAS ${fmt(r.roas_7d)} (min. týždeň ${fmt(r.roas_minuly_tyzden)}, cieľ ${fmt(r.ciel_roas)}), MTD ${eur(r.mtd_naklady)}${r.projekcia_vs_rozpocet === null ? '' : ` / projekcia ${pct(r.projekcia_vs_rozpocet)} vs. rozpočet`}`;
const text = [
  ai || '(AI komentár nie je k dispozícii, nižšie sú iba čísla.)',
  '',
  `SPOLU 7 dní: náklady ${eur(b.totals.cost)}, obrat ${eur(b.totals.value)}, ROAS ${fmt(safeDiv(b.totals.value, b.totals.cost))}. Otvorené úlohy agenta: ${b.open_count}.`,
  '',
  'KRAJINY',
  ...b.table.map(line),
  '',
  '🤖 Vygenerované PPC agentom (n8n).',
].join('\n');

return [{
  json: {
    status_body: {
      data: {
        parent: cfg.asana.project_gid,
        status_type: b.status_type,
        title: `Týždenný stav PPC – týždeň do ${cfg.yesterday}`,
        text,
      },
    },
    email_subject: `Balabim PPC – týždenný stav do ${cfg.yesterday}`,
    email_text: text,
  },
}];
