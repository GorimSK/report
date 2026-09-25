// Settings injected by build.py (config/settings*.json).
const S = __CONFIG__;
return [{ json: { ...S, today: $today.toISODate(), yesterday: $today.minus({ days: 1 }).toISODate() } }];
