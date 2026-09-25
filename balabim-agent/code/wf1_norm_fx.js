// Frankfurter time series -> fx_rates rows (audit trail of rates used for conversion).
const fx = $('FX').first().json;
const ingested = new Date().toISOString();
const out = [];
for (const [date, rates] of Object.entries(fx.rates || {})) {
  for (const [currency, rate] of Object.entries(rates)) {
    out.push({ json: { date, currency, rate_per_eur: rate, ingested_at: ingested } });
  }
}
return out;
