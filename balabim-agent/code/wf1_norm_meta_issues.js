// Meta ad sets (learning status) and ads (disapproved / with issues) -> entity_issues rows.
// Both HTTP nodes feed this node; ads carry adset_id, ad sets do not.
const cfg = $('Config').first().json;
const accountMap = buildAccountMap($('Accounts').all());
const ingested = new Date().toISOString();
const out = [];

for (const r of unwrap($input.all(), 'data')) {
  const campaignName = (r.campaign && r.campaign.name) || '';
  const base = {
    snapshot_date: cfg.until,
    platform: 'META',
    account_id: normId(r.account_id),
    country: resolveCountry(accountMap, 'META', r.account_id, campaignName),
    entity_id: String(r.id),
    entity_name: r.name || '',
    campaign_id: String(r.campaign_id || (r.campaign && r.campaign.id) || ''),
    campaign_name: campaignName,
    ingested_at: ingested,
  };
  if ('adset_id' in r) {
    const detail = (r.issues_info || []).map((i) => i.error_summary || i.error_message).filter(Boolean).join(' | ');
    out.push({ json: { ...base, entity_level: 'AD', issue: r.effective_status, detail } });
  } else if (r.learning_stage_info && r.learning_stage_info.status === 'FAIL') {
    out.push({ json: { ...base, entity_level: 'ADSET', issue: 'LEARNING_LIMITED', detail: 'Learning limited' } });
  }
}
return out;
