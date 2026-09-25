// Meta insights (ad set × day) -> daily_perf rows in EUR.
const cfg = $('Config').first().json;
const fx = $('FX').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const types = cfg.meta_purchase_action_types;

// First matching action type wins, so omni_purchase is not double-counted with purchase.
function pick(list) {
  for (const t of types) {
    const hit = (list || []).find((a) => a.action_type === t);
    if (hit) return num(hit.value);
  }
  return 0;
}

const out = [];
for (const r of unwrap($input.all(), 'data')) {
  const date = r.date_start;
  const currency = r.account_currency || (accountMap[`META|${normId(r.account_id)}`] || {}).currency || 'EUR';
  const rate = fxRate(fx, currency, date);
  out.push({
    json: {
      date,
      platform: 'META',
      account_id: normId(r.account_id),
      account_name: r.account_name || '',
      country: resolveCountry(accountMap, 'META', r.account_id, r.campaign_name),
      campaign_id: String(r.campaign_id),
      campaign_name: r.campaign_name || '',
      campaign_type: r.objective || '',
      campaign_status: '',
      adset_id: String(r.adset_id),
      adset_name: r.adset_name || '',
      currency,
      fx_rate: rate,
      cost_eur: round(num(r.spend) / rate, 4),
      impressions: Math.round(num(r.impressions)),
      clicks: Math.round(num(r.inline_link_clicks)),
      reach: Math.round(num(r.reach)),
      conversions: round(pick(r.actions), 4),
      conv_value_eur: round(pick(r.action_values) / rate, 4),
      search_is: null,
      search_lost_is_budget: null,
      search_lost_is_rank: null,
      budget_daily_eur: null,
      bidding_strategy: '',
      primary_status: '',
      primary_status_reasons: '',
      ingested_at: ingested,
    },
  });
}
return out;
