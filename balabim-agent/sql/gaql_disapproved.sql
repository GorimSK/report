SELECT
  customer.id,
  campaign.id,
  campaign.name,
  ad_group.id,
  ad_group.name,
  ad_group_ad.ad.id,
  ad_group_ad.ad.name,
  ad_group_ad.policy_summary.approval_status
FROM ad_group_ad
WHERE ad_group_ad.status = 'ENABLED'
  AND campaign.status = 'ENABLED'
  AND ad_group.status = 'ENABLED'
  AND ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'
