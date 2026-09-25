// Settings injected by build.py (config/settings*.json + GAQL from sql/).
const S = __CONFIG__;

// $today = start of today in the workflow timezone (Europe/Bratislava).
const until = $today.minus({ days: 1 }).toISODate();
const since = $today.minus({ days: S.lookback_days }).toISODate();
const stSince = $today.minus({ days: S.search_terms_lookback_days }).toISODate();
// Pull a few extra days of FX so weekends/holidays resolve to the last ECB fixing.
const fxFrom = $today.minus({ days: Math.max(S.lookback_days, S.search_terms_lookback_days) + 7 }).toISODate();

const fill = (q) => q.replaceAll('{since}', since).replaceAll('{until}', until).replaceAll('{st_since}', stSince);

return [{
  json: {
    ...S,
    since,
    until,
    st_since: stSince,
    fx_from: fxFrom,
    gaql_campaigns: fill(S.gaql.campaigns),
    gaql_search_terms: fill(S.gaql.search_terms),
    gaql_disapproved: fill(S.gaql.disapproved),
    meta_time_range: JSON.stringify({ since, until }),
  },
}];
