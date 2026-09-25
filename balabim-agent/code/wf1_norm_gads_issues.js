// Google Ads disapproved (enabled) ads -> entity_issues rows.
const cfg = $('Config').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const out = [];

for (const r of unwrap($input.all(), 'results')) {
  const ad = (r.adGroupAd && r.adGroupAd.ad) || {};
  out.push({
    json: {
      snapshot_date: cfg.until,
      platform: 'GOOGLE_ADS',
      account_id: normId(r.customer.id),
      country: resolveCountry(accountMap, 'GOOGLE_ADS', r.customer.id, r.campaign.name),
      entity_level: 'AD',
      entity_id: String(ad.id),
      entity_name: ad.name || `Reklama ${ad.id} (${r.adGroup.name})`,
      campaign_id: String(r.campaign.id),
      campaign_name: r.campaign.name || '',
      issue: 'DISAPPROVED',
      detail: `Ad group: ${r.adGroup.name}`,
      ingested_at: ingested,
    },
  });
}
return out;
