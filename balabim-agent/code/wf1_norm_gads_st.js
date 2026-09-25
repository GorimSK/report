// Google Ads search terms (aggregated over the lookback window) -> search_terms rows.
const cfg = $('Config').first().json;
const fx = $('FX').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const out = [];

for (const r of unwrap($input.all(), 'results')) {
  const rate = fxRate(fx, r.customer.currencyCode, cfg.until);
  const m = r.metrics || {};
  out.push({
    json: {
      snapshot_date: cfg.until,
      period_start: cfg.st_since,
      platform: 'GOOGLE_ADS',
      account_id: normId(r.customer.id),
      country: resolveCountry(accountMap, 'GOOGLE_ADS', r.customer.id, r.campaign.name),
      campaign_id: String(r.campaign.id),
      campaign_name: r.campaign.name || '',
      ad_group_id: String(r.adGroup.id),
      ad_group_name: r.adGroup.name || '',
      search_term: r.searchTermView.searchTerm,
      cost_eur: round(num(m.costMicros) / 1e6 / rate, 4),
      clicks: Math.round(num(m.clicks)),
      conversions: round(num(m.conversions), 4),
      conv_value_eur: round(num(m.conversionsValue) / rate, 4),
      ingested_at: ingested,
    },
  });
}
return out;
