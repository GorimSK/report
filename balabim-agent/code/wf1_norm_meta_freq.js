// Meta insights (ad set, whole 7-day window) -> meta_adset_7d rows.
// Frequency is not additive across days, so it needs its own non-daily request.
const cfg = $('Config').first().json;
const fx = $('FX').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const out = [];

for (const r of unwrap($input.all(), 'data')) {
  const currency = r.account_currency || 'EUR';
  const rate = fxRate(fx, currency, cfg.until);
  out.push({
    json: {
      snapshot_date: cfg.until,
      account_id: normId(r.account_id),
      country: resolveCountry(accountMap, 'META', r.account_id, r.campaign_name),
      campaign_id: String(r.campaign_id),
      campaign_name: r.campaign_name || '',
      adset_id: String(r.adset_id),
      adset_name: r.adset_name || '',
      spend_eur: round(num(r.spend) / rate, 4),
      impressions: Math.round(num(r.impressions)),
      reach: Math.round(num(r.reach)),
      frequency: round(num(r.frequency), 3),
      link_clicks: Math.round(num(r.inline_link_clicks)),
      ingested_at: ingested,
    },
  });
}
return out;
