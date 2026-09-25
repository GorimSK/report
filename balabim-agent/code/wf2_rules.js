// Deterministic rules over BigQuery aggregates -> findings.
// Each finding has a stable alert_key so WF4 can comment on an open Asana task
// instead of creating a duplicate.
const cfg = $('Config').first().json;
const D = cfg.rule_defaults;

// --- targets sheet: one row per country × platform ---------------------------
const targets = {};
for (const { json: t } of $('Targets').all()) {
  const platform = String(t.platform || '').trim().toUpperCase();
  const country = String(t.country || '').trim().toUpperCase();
  if (!platform || !country || !isActive(t.active)) continue;
  const val = (k) => (t[k] === undefined || t[k] === '' ? D[k] : num(t[k]));
  targets[`${platform}|${country}`] = {
    platform,
    country,
    kpi: String(t.kpi || 'ROAS').trim().toUpperCase(),
    monthly_budget_eur: num(t.monthly_budget_eur),
    target_roas: num(t.target_roas),
    target_cpa_eur: num(t.target_cpa_eur),
    pacing_tolerance: val('pacing_tolerance'),
    kpi_tolerance: val('kpi_tolerance'),
    wow_drop: val('wow_drop'),
    min_spend_7d_eur: val('min_spend_7d_eur'),
    min_spend_campaign_7d_eur: val('min_spend_campaign_7d_eur'),
    max_frequency: val('max_frequency'),
  };
}

const perf = rows($('BQ Perf').all());
const searchTerms = rows($('BQ Search Terms').all());
const issues = rows($('BQ Issues').all());
const metaFreq = rows($('BQ Meta Freq').all());
const runDate = perf.length ? String(perf[0].run_date).slice(0, 10) : $today.minus({ days: 1 }).toISODate();
const month = runDate.slice(0, 7);

const findings = [];
function add(f) {
  findings.push({
    run_date: runDate,
    scope_level: 'country',
    scope_id: 'ALL',
    scope_name: f.country,
    suggested_steps: [],
    ...f,
    alert_key: [f.platform, f.country, f.scope_id || 'ALL', f.rule, f.key_suffix].filter(Boolean).join('|'),
  });
}
const label = (platform, country) => `${country} ${PLATFORM_LABEL[platform] || platform}`;
const kpiText = (t, value, cost, conv) =>
  t.kpi === 'CPA'
    ? `CPA ${fmt(safeDiv(cost, conv))} € (cieľ ${fmt(t.target_cpa_eur)} €)`
    : `ROAS ${fmt(safeDiv(value, cost))} (cieľ ${fmt(t.target_roas)})`;

// Returns a signed miss ratio: > 0 means worse than target by that fraction.
function kpiMiss(t, value, cost, conv) {
  if (t.kpi === 'CPA') {
    if (!t.target_cpa_eur) return null;
    const cpa = safeDiv(cost, conv);
    return cpa === null ? (num(cost) > 0 ? Infinity : null) : cpa / t.target_cpa_eur - 1;
  }
  if (!t.target_roas) return null;
  const roas = safeDiv(value, cost);
  return roas === null ? null : 1 - roas / t.target_roas;
}

// --- country level -----------------------------------------------------------
const countryRows = perf.filter((r) => r.level === 'country');
const seen = new Set(countryRows.map((r) => `${r.platform}|${r.country}`));

for (const [key, t] of Object.entries(targets)) {
  if (t.monthly_budget_eur > 0 && !seen.has(key)) {
    add({
      rule: 'NO_DATA', severity: 'P1', platform: t.platform, country: t.country,
      title: `${label(t.platform, t.country)}: žiadne dáta ani spend za 14 dní`,
      summary_line: `Pre ${label(t.platform, t.country)} nie sú v dátach žiadne náklady, hoci je nastavený rozpočet ${eur(t.monthly_budget_eur)}.`,
      metrics: { monthly_budget_eur: t.monthly_budget_eur },
      suggested_steps: [
        'Skontrolovať, či kampane bežia (stav účtu, platby, zamietnutia).',
        'Overiť mapovanie účtu v záložke "accounts" v Config Sheete.',
        'Skontrolovať poslednú exekúciu WF1 v n8n.',
      ],
    });
  }
}

for (const r of countryRows) {
  const key = `${r.platform}|${r.country}`;
  const t = targets[key];

  if (r.country === 'UNKNOWN') {
    add({
      rule: 'UNMAPPED', severity: 'P3', platform: r.platform, country: 'ALL', key_suffix: 'UNKNOWN',
      title: `${PLATFORM_LABEL[r.platform]}: náklady ${eur(r.cost_7d)} bez priradenej krajiny`,
      summary_line: `Kampane za ${eur(r.cost_7d)} (7 dní) nemajú krajinu v názve ani v mapovaní účtu.`,
      metrics: { cost_7d: round(r.cost_7d) },
      suggested_steps: ['Doplniť kód krajiny do názvov kampaní alebo mapovanie účtu v Config Sheete.'],
    });
    continue;
  }
  if (!t) continue;

  const cost1 = num(r.cost_1d), cost7 = num(r.cost_7d), costP7 = num(r.cost_p7);
  const conv1 = num(r.conv_1d), conv7 = num(r.conv_7d), convP7 = num(r.conv_p7);
  const value7 = num(r.value_7d), valueP7 = num(r.value_p7);
  const convAvg = num(r.conv_avg_b7);

  // 1) Tracking outage: conversions collapse while money is still being spent.
  if (convAvg >= D.outage_min_daily_conv && cost1 > 0 && conv1 <= convAvg * (1 - D.outage_drop)) {
    add({
      rule: 'TRACKING_OUTAGE', severity: 'P1', platform: r.platform, country: r.country,
      title: `${label(r.platform, r.country)}: prepad konverzií včera (${fmt(conv1, 1)} vs. priemer ${fmt(convAvg, 1)}/deň)`,
      summary_line: `Včera ${fmt(conv1, 1)} konverzií pri nákladoch ${eur(cost1)}, 7-dňový priemer ${fmt(convAvg, 1)}/deň.`,
      metrics: { conv_1d: conv1, conv_avg_b7: round(convAvg), cost_1d: round(cost1) },
      suggested_steps: [
        'Overiť meranie: GA4/Google Ads tag, Meta Pixel + CAPI (Events Manager), testovacia objednávka.',
        'Skontrolovať e-shop (checkout, platobná brána, dostupnosť webu) v danej krajine.',
        'Ak ide o výpadok merania, informovať klienta a nemeniť biddingové stratégie, kým sa dáta neopravia.',
      ],
    });
  }

  // 2) Budget pacing (month to date vs. linear plan).
  if (t.monthly_budget_eur > 0 && num(r.days_elapsed) >= D.pacing_min_days) {
    const days = num(r.days_elapsed), dim = num(r.days_in_month);
    const projected = (num(r.cost_mtd) / days) * dim;
    const dev = projected / t.monthly_budget_eur - 1;
    const common = {
      platform: r.platform, country: r.country, key_suffix: month,
      metrics: {
        cost_mtd: round(r.cost_mtd), monthly_budget_eur: t.monthly_budget_eur,
        projected_eur: round(projected), deviation: round(dev, 3), days_elapsed: days, days_in_month: dim,
      },
      summary_line: `MTD ${eur(r.cost_mtd)}, projekcia ${eur(projected)} vs. rozpočet ${eur(t.monthly_budget_eur)} (${pct(dev)}).`,
    };
    if (dev > t.pacing_tolerance) {
      add({
        ...common, rule: 'PACING_OVER', severity: dev > 2 * t.pacing_tolerance ? 'P1' : 'P2',
        title: `${label(r.platform, r.country)}: hrozí prečerpanie rozpočtu o ${pct(dev)}`,
        suggested_steps: [
          `Znížiť denné rozpočty tak, aby zvyšok mesiaca stál max. ${eur(Math.max(0, t.monthly_budget_eur - num(r.cost_mtd)))}.`,
          'Začať kampaňami s najhorším ROAS/CPA; brand a remarketing obmedziť až nakoniec.',
        ],
      });
    } else if (dev < -t.pacing_tolerance) {
      add({
        ...common, rule: 'PACING_UNDER', severity: 'P2',
        title: `${label(r.platform, r.country)}: podčerpanie rozpočtu (${pct(dev)})`,
        suggested_steps: [
          'Identifikovať kampane obmedzené rozpočtom alebo cieľom (tROAS/tCPA príliš prísne).',
          'Presunúť rozpočet do kampaní s ROAS nad cieľom, prípadne uvoľniť cieľ bidding stratégie.',
        ],
      });
    }
  }

  // 3) KPI vs. target (7 days) and 4) week-over-week drop.
  if (cost7 >= t.min_spend_7d_eur) {
    const miss = kpiMiss(t, value7, cost7, conv7);
    const metrics = {
      cost_7d: round(cost7), value_7d: round(value7), conv_7d: round(conv7, 1),
      roas_7d: round(safeDiv(value7, cost7) ?? 0), cpa_7d: round(safeDiv(cost7, conv7) ?? 0),
      roas_p7: round(safeDiv(valueP7, costP7) ?? 0), target_roas: t.target_roas, target_cpa_eur: t.target_cpa_eur,
    };
    if (miss !== null && miss > t.kpi_tolerance) {
      add({
        rule: 'KPI_BELOW_TARGET', severity: 'P2', platform: r.platform, country: r.country, metrics,
        title: `${label(r.platform, r.country)}: ${t.kpi} 7 dní mimo cieľa`,
        summary_line: `${kpiText(t, value7, cost7, conv7)}, náklady ${eur(cost7)}, konverzie ${fmt(conv7, 1)}.`,
        suggested_steps: [
          'Rozpadnúť výkon podľa kampaní a nájsť hlavného vinníka (náklady × KPI).',
          'Skontrolovať zmeny za posledné 2 týždne (bidding, rozpočty, kreatívy, feed, ceny, sklad).',
          'Upraviť ciele bidding stratégie alebo presunúť rozpočet do výkonnejších kampaní.',
        ],
      });
    } else if (costP7 >= t.min_spend_7d_eur && convP7 >= D.wow_min_conv) {
      const roas7 = safeDiv(value7, cost7), roasP7 = safeDiv(valueP7, costP7);
      const cpa7 = safeDiv(cost7, conv7), cpaP7 = safeDiv(costP7, convP7);
      const drop = t.kpi === 'CPA'
        ? (cpa7 === null ? 1 : cpa7 / cpaP7 - 1)
        : (roasP7 ? 1 - roas7 / roasP7 : 0);
      if (drop > t.wow_drop) {
        add({
          rule: 'KPI_WOW_DROP', severity: 'P2', platform: r.platform, country: r.country, metrics,
          title: `${label(r.platform, r.country)}: ${t.kpi} týždeň na týždeň horší o ${pct(drop)}`,
          summary_line: t.kpi === 'CPA'
            ? `CPA ${fmt(cpa7)} € vs. ${fmt(cpaP7)} € minulý týždeň.`
            : `ROAS ${fmt(roas7)} vs. ${fmt(roasP7)} minulý týždeň, náklady ${eur(cost7)} vs. ${eur(costP7)}.`,
          suggested_steps: [
            'Nájsť kampane s najväčším poklesom a skontrolovať nedávne zmeny.',
            'Overiť sezónnosť, akcie konkurencie a dostupnosť produktov.',
          ],
        });
      }
    }
  }
}

// --- campaign level ----------------------------------------------------------
const campaignRows = perf.filter((r) => r.level === 'campaign' && r.country !== 'UNKNOWN');
for (const r of campaignRows) {
  const t = targets[`${r.platform}|${r.country}`];
  if (!t) continue;
  const cost7 = num(r.cost_7d), conv7 = num(r.conv_7d), value7 = num(r.value_7d);
  const scope = { scope_level: 'campaign', scope_id: String(r.scope_id), scope_name: r.scope_name, campaign_id: String(r.scope_id) };
  const metrics = {
    cost_7d: round(cost7), conv_7d: round(conv7, 1), value_7d: round(value7),
    roas_7d: round(safeDiv(value7, cost7) ?? 0), lost_is_budget_7d: round(r.lost_is_budget_7d ?? 0, 3),
  };

  // 5) Spend without conversions.
  const wasteThreshold = Math.max(t.min_spend_campaign_7d_eur, t.kpi === 'CPA' ? 2 * t.target_cpa_eur : 0);
  if (cost7 >= wasteThreshold && conv7 === 0) {
    add({
      ...scope, rule: 'WASTE_NO_CONV', severity: 'P2', platform: r.platform, country: r.country, metrics,
      title: `${label(r.platform, r.country)}: kampaň „${r.scope_name}“ minula ${eur(cost7)} bez konverzie`,
      summary_line: `${eur(cost7)} za 7 dní, 0 konverzií.`,
      suggested_steps: [
        'Skontrolovať cielenie, search termy / umiestnenia a vstupnú stránku.',
        'Zvážiť zníženie rozpočtu alebo pozastavenie do vyriešenia.',
      ],
    });
    continue;
  }

  // 6) Profitable Google campaign limited by budget -> scale opportunity.
  const miss = kpiMiss(t, value7, cost7, conv7);
  if (r.platform === 'GOOGLE_ADS' && num(r.lost_is_budget_7d) >= D.scale_lost_is_budget
      && conv7 >= D.scale_min_conv && miss !== null && miss <= 0) {
    add({
      ...scope, rule: 'SCALE_BUDGET', severity: 'P3', platform: r.platform, country: r.country, metrics,
      title: `${label(r.platform, r.country)}: „${r.scope_name}“ je nad cieľom, ale obmedzená rozpočtom`,
      summary_line: `${kpiText(t, value7, cost7, conv7)}, stratený IS kvôli rozpočtu ${pct(r.lost_is_budget_7d)}.`,
      suggested_steps: [
        'Navýšiť denný rozpočet o 15–20 % (postupne, max. raz za 3–4 dni).',
        'Skontrolovať, či to celkový mesačný rozpočet krajiny dovoľuje.',
      ],
    });
  }

  // 7) Significant campaign-level drop week over week.
  const costP7 = num(r.cost_p7), convP7 = num(r.conv_p7), valueP7 = num(r.value_p7);
  if (cost7 >= 2 * t.min_spend_campaign_7d_eur && convP7 >= D.wow_min_conv && t.kpi !== 'CPA') {
    const roas7 = safeDiv(value7, cost7) ?? 0, roasP7 = safeDiv(valueP7, costP7);
    if (roasP7 && 1 - roas7 / roasP7 > t.wow_drop && miss !== null && miss > 0) {
      add({
        ...scope, rule: 'CAMPAIGN_DROP', severity: 'P3', platform: r.platform, country: r.country, metrics,
        title: `${label(r.platform, r.country)}: pokles ROAS kampane „${r.scope_name}“`,
        summary_line: `ROAS ${fmt(roas7)} vs. ${fmt(roasP7)} minulý týždeň pri nákladoch ${eur(cost7)}.`,
        suggested_steps: ['Skontrolovať zmeny v kampani, feed/ceny a konkurenciu (Auction insights).'],
      });
    }
  }
}

// --- Meta ad sets: creative fatigue ------------------------------------------
const adsetPerf = Object.fromEntries(perf.filter((r) => r.level === 'adset').map((r) => [String(r.scope_id), r]));
for (const a of metaFreq) {
  const t = targets[`META|${a.country}`];
  if (!t || num(a.spend_eur) < t.min_spend_campaign_7d_eur || num(a.frequency) <= t.max_frequency) continue;
  const p = adsetPerf[String(a.adset_id)] || {};
  const ctr7 = safeDiv(p.clicks_7d, p.impr_7d), ctrP7 = safeDiv(p.clicks_p7, p.impr_p7);
  add({
    rule: 'CREATIVE_FATIGUE', severity: 'P3', platform: 'META', country: a.country,
    scope_level: 'adset', scope_id: String(a.adset_id), scope_name: a.adset_name, campaign_id: String(a.campaign_id),
    title: `${label('META', a.country)}: vysoká frekvencia v ad sete „${a.adset_name}“ (${fmt(a.frequency, 1)})`,
    summary_line: `Frekvencia 7 dní ${fmt(a.frequency, 1)}, spend ${eur(a.spend_eur)}, CTR ${pct(ctr7)} vs. ${pct(ctrP7)} minulý týždeň.`,
    metrics: { frequency_7d: round(a.frequency, 2), spend_7d: round(a.spend_eur), ctr_7d: ctr7, ctr_p7: ctrP7 },
    suggested_steps: [
      'Pripraviť a nasadiť 2–3 nové kreatívy (nový hook/formát).',
      'Rozšíriť publikum alebo vylúčiť nedávnych konvertujúcich.',
    ],
  });
}

// --- Google search terms: one finding per country ----------------------------
const stByCountry = {};
for (const s of searchTerms) {
  if (num(s.cost_eur) < D.search_term_min_cost_eur || s.country === 'UNKNOWN') continue;
  (stByCountry[s.country] ||= []).push(s);
}
for (const [country, list] of Object.entries(stByCountry)) {
  if (!targets[`GOOGLE_ADS|${country}`]) continue;
  const total = list.reduce((a, s) => a + num(s.cost_eur), 0);
  const top = list.slice(0, 25);
  add({
    rule: 'SEARCH_TERMS', severity: 'P3', platform: 'GOOGLE_ADS', country, key_suffix: runDate.slice(0, 7),
    title: `${label('GOOGLE_ADS', country)}: search termy bez konverzie (${list.length}, spolu ${eur(total)})`,
    summary_line: `Top: ${top.slice(0, 5).map((s) => `„${s.search_term}“ ${eur(s.cost_eur)}`).join(', ')}.`,
    metrics: {
      total_cost_eur: round(total), count: list.length,
      terms: top.map((s) => ({ term: s.search_term, cost: round(s.cost_eur), clicks: num(s.clicks), campaign: s.campaign_name })),
    },
    suggested_steps: [
      'Prejsť zoznam a irelevantné výrazy pridať ako negatívne KW (zdieľaný zoznam pre krajinu).',
      'Relevantné výrazy s kliknutiami zvážiť ako samostatné KW s vlastnou reklamou.',
    ],
  });
}

// --- disapproved ads / learning limited: one finding per country × platform × issue
const issueGroups = {};
for (const i of issues) {
  const kind = i.issue === 'LEARNING_LIMITED' ? 'LEARNING_LIMITED' : 'POLICY';
  (issueGroups[`${i.platform}|${i.country}|${kind}`] ||= []).push(i);
}
for (const [key, list] of Object.entries(issueGroups)) {
  const [platform, country, kind] = key.split('|');
  const names = list.slice(0, 15).map((i) => `${i.entity_name} (${i.campaign_name})`);
  if (kind === 'POLICY') {
    add({
      rule: 'POLICY', severity: 'P2', platform, country,
      title: `${label(platform, country)}: zamietnuté alebo problémové reklamy (${list.length})`,
      summary_line: `Napr.: ${names.slice(0, 3).join('; ')}.`,
      metrics: { count: list.length, entities: names, details: list.slice(0, 15).map((i) => i.detail).filter(Boolean) },
      suggested_steps: [
        'Skontrolovať dôvod zamietnutia v rozhraní platformy.',
        'Upraviť reklamu/kreatívu alebo podať odvolanie; nahradiť ju funkčnou verziou.',
      ],
    });
  } else {
    add({
      rule: 'LEARNING_LIMITED', severity: 'P3', platform, country,
      title: `${label(platform, country)}: ad sety v stave Learning limited (${list.length})`,
      summary_line: `Napr.: ${names.slice(0, 3).join('; ')}.`,
      metrics: { count: list.length, entities: names },
      suggested_steps: [
        'Zlúčiť malé ad sety alebo rozšíriť publikum, aby dosiahli ~50 optimalizačných udalostí týždenne.',
        'Zvážiť optimalizáciu na udalosť vyššie vo funneli (napr. AddToCart), ak je nákupov málo.',
      ],
    });
  }
}

findings.sort((a, b) => PRIORITY_ORDER[a.severity] - PRIORITY_ORDER[b.severity]);
return findings.map((f) => ({ json: f }));
