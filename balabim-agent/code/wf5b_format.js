// Before/after comparison per completed task -> verdict + Asana comment text.
const out = [];
for (const r of rows($input.all())) {
  const cb = num(r.cost_before), ca = num(r.cost_after);
  const vb = num(r.value_before), va = num(r.value_after);
  const nb = num(r.conv_before), na = num(r.conv_after);
  const roasB = safeDiv(vb, cb), roasA = safeDiv(va, ca);
  const change = (a, b) => (b ? (a / b - 1) : null);

  let verdict = 'NEUTRAL';
  if (cb === 0 && ca === 0) verdict = 'NO_DATA';
  else if (r.type === 'WASTE') verdict = ca <= cb * 0.8 && na >= nb ? 'IMPROVED' : (ca > cb * 1.1 && na <= nb ? 'WORSE' : 'NEUTRAL');
  else if (r.type === 'SCALE') verdict = va >= vb * 1.1 && (roasA ?? 0) >= (roasB ?? 0) * 0.9 ? 'IMPROVED' : (va < vb ? 'WORSE' : 'NEUTRAL');
  else if (roasB !== null && roasA !== null) verdict = roasA >= roasB * 1.05 ? 'IMPROVED' : (roasA <= roasB * 0.95 ? 'WORSE' : 'NEUTRAL');

  const icon = { IMPROVED: '✅', NEUTRAL: '➖', WORSE: '⚠️', NO_DATA: '❔' }[verdict];
  const scope = [r.country, PLATFORM_LABEL[r.platform] || r.platform, r.campaign_id ? `kampaň ${r.campaign_id}` : 'celý trh'].join(' / ');
  const text = [
    `${icon} Vyhodnotenie ${r.eval_day} dní po dokončení (${String(r.done_date).slice(0, 10)}) – ${scope}`,
    '',
    `Náklady: ${eur(cb)} → ${eur(ca)} (${pct(change(ca, cb))})`,
    `Obrat z konverzií: ${eur(vb)} → ${eur(va)} (${pct(change(va, vb))})`,
    `Konverzie: ${fmt(nb, 1)} → ${fmt(na, 1)}`,
    `ROAS: ${fmt(roasB)} → ${fmt(roasA)}`,
    '',
    'Pozn.: porovnanie ' + r.eval_day + ' dní pred a po, bez očistenia o sezónnosť. Ide o signál, nie dôkaz príčiny.',
  ].join('\n');

  out.push({ json: { ...r, verdict, comment_text: text } });
}
return out;
