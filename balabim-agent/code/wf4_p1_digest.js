// One e-mail per run with all P1 items (new or still open) + AI problems, if any.
const items = $input.all().map((i) => i.json);
const p1 = items.filter((i) => i.priority === 'P1');
const aiProblem = items.map((i) => i.ai_problem).find(Boolean);
if (!p1.length && !aiProblem) return [];

const lines = p1.map((i) => `• [${i.country} ${PLATFORM_LABEL[i.platform] || i.platform}] ${i.title}${i.action === 'comment' ? ' (už otvorený task)' : ''}`);
if (aiProblem) lines.push('', `⚠️ AI analýza zlyhala, úlohy boli vytvorené zo šablón: ${aiProblem}`);
return [{
  json: {
    subject: `🚨 Balabim PPC: ${p1.length}× P1 – ${$today.toISODate()}`,
    text: ['Agent našiel kritické problémy, ktoré treba riešiť dnes:', '', ...lines, '', 'Detaily sú v Asane v projekte PPC optimalizácia.'].join('\n'),
  },
}];
