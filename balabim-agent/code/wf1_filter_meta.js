return $input.all().filter((i) =>
  String(i.json.platform || '').trim().toUpperCase() === 'META' && isActive(i.json.active) && i.json.account_id);
