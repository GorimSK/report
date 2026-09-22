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
})();
