# Marketingová príručka pre začiatočníkov

Statická stránka (HTML + CSS + JS, bez buildu) — doplnkový materiál ku školeniam na ITLearning.

## Obsah stránky

1. **Reklamná aukcia** — Ad Rank, prahy, výpočet reálnej ceny za klik, Auction Insights, paralela na Mete
2. **Skóre kvality** — tri zložky, čo robiť pri každej diagnóze, mýty
3. **Funnel a typy kampaní** — TOFU / MOFU / BOFU / retencia, kam patrí ktorý typ kampane, KPI a podiely rozpočtu
4. **Pravidlá pre konverzie** — 12 pravidiel merania + päťminútová diagnostika
5. **Pravidlá pre landing page** — 12 pravidiel
6. **Checklist pred spustením** — interaktívny, stav sa ukladá v prehliadači (localStorage)
7. **Kalkulačka** — break-even CPC, CPA a ROAS
8. **Slovníček pojmov** a **kontakt**

## Lokálny náhľad

```bash
cd prirucka
python3 -m http.server 8000   # http://localhost:8000
```

## Nasadenie na Vercel

Projekt je statický, žiadny build. V nastaveniach Vercel projektu:

- **Root Directory:** `prirucka`
- **Framework Preset:** Other
- **Build Command:** prázdne
- **Output Directory:** prázdne (`.`)

Každý push do produkčnej vetvy nasadí produkciu, push do inej vetvy vytvorí preview deployment.

## Úpravy obsahu

Celý text je priamo v `index.html` — sekcie sú oddelené HTML komentármi (`<!-- ================= FUNNEL ================= -->`).
Kontaktné údaje sú v sekcii `#kontakt` a v pätičke.
