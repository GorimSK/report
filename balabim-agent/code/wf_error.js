// Error Trigger payload -> alert e-mail.
const e = $input.first().json;
const wf = (e.workflow && e.workflow.name) || 'neznámy workflow';
const ex = e.execution || {};
const err = ex.error || {};
return [{
  json: {
    subject: `❌ n8n Balabim agent: chyba vo „${wf}“`,
    text: [
      `Workflow: ${wf}`,
      `Node: ${ex.lastNodeExecuted || '?'}`,
      `Chyba: ${err.message || JSON.stringify(err).slice(0, 500)}`,
      ex.url ? `Exekúcia: ${ex.url}` : '',
      '',
      'Časté príčiny: expirovaný token (Meta System User, Google OAuth), zmena verzie API, limit API, chýbajúci kurz meny.',
    ].filter((l) => l !== undefined).join('\n'),
  },
}];
