// Google Ads searchStream (campaign × day) -> daily_perf rows in EUR.
const fx = $('FX').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const out = [];

for (const r of unwrap($input.all(), 'results')) {
  const date = r.segments.date;
  const currency = r.customer.currencyCode;
  const rate = fxRate(fx, currency, date);
  const m = r.metrics || {};
  const c = r.campaign || {};
  const isShare = (v) => (v === undefined || v === null ? null : num(v));
  out.push({
    json: {
      date,
      platform: 'GOOGLE_ADS',
      account_id: normId(r.customer.id),
      account_name: r.customer.descriptiveName || '',
      country: resolveCountry(accountMap, 'GOOGLE_ADS', r.customer.id, c.name),
      campaign_id: String(c.id),
      campaign_name: c.name || '',
      campaign_type: c.advertisingChannelType || '',
      campaign_status: c.status || '',
      adset_id: null,
      adset_name: null,
      currency,
      fx_rate: rate,
      cost_eur: round(num(m.costMicros) / 1e6 / rate, 4),
      impressions: Math.round(num(m.impressions)),
      clicks: Math.round(num(m.clicks)),
      reach: null,
      conversions: round(num(m.conversions), 4),
      conv_value_eur: round(num(m.conversionsValue) / rate, 4),
      search_is: isShare(m.searchImpressionShare),
      search_lost_is_budget: isShare(m.searchBudgetLostImpressionShare),
      search_lost_is_rank: isShare(m.searchRankLostImpressionShare),
      budget_daily_eur: r.campaignBudget ? round(num(r.campaignBudget.amountMicros) / 1e6 / rate, 2) : null,
      bidding_strategy: c.biddingStrategyType || '',
      primary_status: c.primaryStatus || '',
      primary_status_reasons: (c.primaryStatusReasons || []).join(','),
      ingested_at: ingested,
    },
  });
}
return out;
