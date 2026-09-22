(function () {
  'use strict';

  /* ---------- Mobilné menu ---------- */
  var toggle = document.querySelector('.menu-toggle');
  var mobilenav = document.getElementById('mobilenav');
  if (toggle && mobilenav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      mobilenav.hidden = open;
    });
    mobilenav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        toggle.setAttribute('aria-expanded', 'false');
        mobilenav.hidden = true;
      }
    });
  }

  /* ---------- Ukazovateľ prečítaného ---------- */
  var bar = document.querySelector('.progress-bar');
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  var sections = tocLinks
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  function onScroll() {
    if (bar) {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    }
    var current = null;
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].getBoundingClientRect().top <= 140) current = sections[i];
    }
    tocLinks.forEach(function (a) {
      a.classList.toggle('active', !!current && a.getAttribute('href') === '#' + current.id);
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- Checklist s uložením v prehliadači ---------- */
  var KEY = 'mp-checklist-v1';
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.check input[data-ck]'));
  var progress = document.getElementById('checkProgress');
  var reset = document.getElementById('resetCheck');

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || '{}') || {};
    } catch (e) {
      return {};
    }
  }
  function saveState(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* súkromné okno */ }
  }
  function renderProgress() {
    if (!progress) return;
    var done = boxes.filter(function (b) { return b.checked; }).length;
    progress.textContent = 'Hotovo ' + done + ' z ' + boxes.length;
  }
  if (boxes.length) {
    var state = loadState();
    boxes.forEach(function (b) {
      if (state[b.dataset.ck]) b.checked = true;
      b.addEventListener('change', function () {
        var s = loadState();
        if (b.checked) { s[b.dataset.ck] = 1; } else { delete s[b.dataset.ck]; }
        saveState(s);
        renderProgress();
      });
    });
    renderProgress();
    if (reset) {
      reset.addEventListener('click', function () {
        boxes.forEach(function (b) { b.checked = false; });
        saveState({});
        renderProgress();
      });
    }
  }

  /* ---------- Kalkulačka ---------- */
  var fields = ['aov', 'margin', 'cr', 'cpc'].map(function (id) { return document.getElementById(id); });
  var out = {
    profit: document.getElementById('rProfit'),
    cpa: document.getElementById('rCpa'),
    cpc: document.getElementById('rCpc'),
    roas: document.getElementById('rRoas'),
    realCpa: document.getElementById('rRealCpa'),
    realRoas: document.getElementById('rRealRoas'),
    margin: document.getElementById('rMargin'),
    verdict: document.getElementById('verdict')
  };

  function eur(n) {
    return n.toLocaleString('sk-SK', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  }

  function calc() {
    if (fields.some(function (f) { return !f; })) return;
    var aov = parseFloat(fields[0].value) || 0;
    var margin = (parseFloat(fields[1].value) || 0) / 100;
    var cr = (parseFloat(fields[2].value) || 0) / 100;
    var cpc = parseFloat(fields[3].value) || 0;

    var profit = aov * margin;           // hrubý zisk z objednávky
    var beCpa = profit;                  // break-even cena za konverziu
    var beCpc = beCpa * cr;              // break-even cena za klik
    var beRoas = margin > 0 ? 1 / margin : 0;
    var realCpa = cr > 0 ? cpc / cr : 0;
    var realRoas = realCpa > 0 ? aov / realCpa : 0;
    var perOrder = profit - realCpa;

    out.profit.textContent = eur(profit);
    out.cpa.textContent = eur(beCpa);
    out.cpc.textContent = eur(beCpc);
    out.roas.textContent = beRoas ? Math.round(beRoas * 100) + ' %' : '—';
    out.realCpa.textContent = cr > 0 ? eur(realCpa) : '—';
    out.realRoas.textContent = realRoas ? Math.round(realRoas * 100) + ' %' : '—';
    out.margin.textContent = (perOrder >= 0 ? '+' : '') + eur(perOrder);
    out.margin.style.color = perOrder >= 0 ? 'var(--accent-2)' : 'var(--bad)';

    if (!aov || !cr || !margin) {
      out.verdict.textContent = 'Doplň všetky štyri hodnoty.';
      out.verdict.className = 'calc-verdict';
      return;
    }
    if (perOrder >= 0) {
      out.verdict.textContent = 'Pri týchto číslach si v pluse. Priestor máš ešte do CPC ' + eur(beCpc) + '.';
      out.verdict.className = 'calc-verdict good';
    } else {
      out.verdict.textContent = 'Pri týchto číslach si v strate. Buď zníž CPC pod ' + eur(beCpc) +
        ', alebo zdvihni konverzný pomer aspoň na ' + (beCpa > 0 ? (cpc / beCpa * 100).toFixed(2) : '—') + ' %.';
      out.verdict.className = 'calc-verdict bad';
    }
  }

  fields.forEach(function (f) { if (f) f.addEventListener('input', calc); });
  calc();
  /* ---------- Simulátor aukcie ---------- */
  var simBody = document.getElementById('simBody');
  var simVerdict = document.getElementById('simVerdict');
  var simThreshold = document.getElementById('simThreshold');
  var simNames = [
    { name: 'Ty', acc: 'teba' },
    { name: 'Konkurent B', acc: 'konkurenta B' },
    { name: 'Konkurent C', acc: 'konkurenta C' }
  ];
  var simDefaults = [{ bid: '1.00', q: '10' }, { bid: '2.00', q: '4' }, { bid: '1.50', q: '3' }];

  function simEl(cls, i) {
    return document.querySelector('.' + cls + '[data-i="' + i + '"]');
  }
  function num(n) {
    return n.toLocaleString('sk-SK', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function simRender() {
    if (!simBody) return;
    var threshold = parseFloat(simThreshold.value) || 0;

    var all = simNames.map(function (who, i) {
      var bidEl = simEl('sim-bid', i);
      var qEl = simEl('sim-q', i);
      var q = qEl ? parseInt(qEl.value, 10) || 1 : 1;
      var bid = bidEl ? parseFloat(bidEl.value) || 0 : 0;
      var valEl = simEl('sim-q-val', i);
      if (valEl) valEl.textContent = q;
      return { name: who.name, acc: who.acc, you: i === 0, bid: bid, q: q, rank: bid * q };
    });

    var shown = all.filter(function (a) { return a.bid > 0 && a.rank >= threshold; })
      .sort(function (x, y) { return y.rank - x.rank; });
    var out = all.filter(function (a) { return shown.indexOf(a) === -1; });

    shown.forEach(function (a, i) {
      var below = shown[i + 1];
      a.pos = i + 1;
      a.cpc = Math.min(a.bid, (below ? below.rank : threshold) / a.q + 0.01);
    });

    var rows = shown.map(function (a) {
      return '<tr' + (a.you ? ' class="row-you"' : '') + '>' +
        '<td><strong>' + a.pos + '.</strong></td>' +
        '<td>' + a.name + '</td>' +
        '<td>' + eur(a.bid) + '</td>' +
        '<td>' + a.q + '</td>' +
        '<td>' + num(a.rank) + '</td>' +
        '<td><strong>' + eur(a.cpc) + '</strong></td></tr>';
    }).concat(out.map(function (a) {
      return '<tr class="row-out' + (a.you ? ' row-you' : '') + '">' +
        '<td>—</td><td>' + a.name + '</td><td>' + eur(a.bid) + '</td><td>' + a.q + '</td>' +
        '<td>' + num(a.rank) + '</td><td>nezobrazí sa</td></tr>';
    }));
    simBody.innerHTML = rows.join('');

    var you = all[0];
    var msg;
    if (shown.indexOf(you) === -1) {
      msg = 'Nezobrazuješ sa vôbec — tvoj Ad Rank ' + num(you.rank) + ' nedosiahol prah ' + num(threshold) + '.';
    } else if (you.pos === 1) {
      var second = shown[1];
      var minBid = (second ? second.rank : threshold) / you.q + 0.01;
      msg = 'Si na 1. pozícii a platíš ' + eur(you.cpc) + '. Tvoja ponuka je len strop — prvé miesto by si udržal aj s ponukou ' + eur(minBid) + '.';
    } else {
      var above = shown[you.pos - 2];
      var bidNeeded = above.rank / you.q + 0.01;
      var qNeeded = Math.ceil((above.rank + 0.01) / you.bid);
      msg = 'Si na ' + you.pos + '. pozícii a platíš ' + eur(you.cpc) + '. Predbehnúť ' + above.acc +
        ' znamená zdvihnúť ponuku na ' + eur(bidNeeded) +
        (qNeeded <= 10
          ? ' — alebo ponuku nechať a zlepšiť kvalitu na ' + qNeeded + '. To je lacnejšia cesta.'
          : ' — samotná kvalita už nestačí, jej maximum je 10.');
    }
    simVerdict.textContent = msg;
  }

  if (simBody) {
    Array.prototype.slice.call(document.querySelectorAll('.sim-bid, .sim-q')).forEach(function (el) {
      el.addEventListener('input', simRender);
    });
    simThreshold.addEventListener('input', simRender);
    var simReset = document.getElementById('simReset');
    if (simReset) {
      simReset.addEventListener('click', function () {
        simDefaults.forEach(function (d, i) {
          var bidEl = simEl('sim-bid', i);
          var qEl = simEl('sim-q', i);
          if (bidEl) bidEl.value = d.bid;
          if (qEl) qEl.value = d.q;
        });
        simThreshold.value = '2';
        simRender();
      });
    }
    simRender();
  }
})();
