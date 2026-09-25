return $input.all().filter((i) =>
  String(i.json.platform || '').trim().toUpperCase() === 'GOOGLE_ADS' && isActive(i.json.active) && i.json.account_id);
