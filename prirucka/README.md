# Marketingová príručka pre začiatočníkov

Statická stránka (HTML + CSS + JS, bez buildu) — doplnkový materiál ku školeniam na ITLearning.

**Živá verzia:** https://prirucka-marketing.vercel.app

(Staršie verzie: marketing-prirucka.vercel.app, marketing-prirucka-sk.vercel.app)

## Obsah stránky

1. **Reklamná aukcia** — Ad Rank, prahy, výpočet reálnej ceny za klik, Auction Insights, paralela na Mete
2. **Skóre kvality** — tri zložky, čo robiť pri každej diagnóze, mýty
3. **Funnel a typy kampaní** — TOFU / MOFU / BOFU / retencia, kam patrí ktorý typ kampane, KPI a podiely rozpočtu
4. **Pravidlá pre konverzie** — 12 pravidiel merania + päťminútová diagnostika
5. **Pravidlá pre landing page** — 12 pravidiel
6. **Checklist pred spustením** — interaktívny, stav sa ukladá v prehliadači (localStorage)
7. **Kalkulačka** — break-even CPC, CPA a ROAS
8. **Ďalší level** — teaser na pripravované školenia (AI, skripty, n8n) + dva flow diagramy
9. **QR kód na zdieľanie** — inline SVG (vygenerované cez segno), mieri na adresu vyššie
8. **Slovníček pojmov** a **kontakt**

## Lokálny náhľad

```bash
cd prirucka
python3 -m http.server 8000   # http://localhost:8000
```

## Nasadenie na Vercel

Aktuálna živá verzia (projekt `prirucka-marketing`) bola nahraná priamo cez Vercel API,
teda **nie je prepojená s týmto repozitárom** — zmeny v gite sa samy nenasadia.
Použitý prístupový token navyše vie iba zakladať nové projekty, nie nasadzovať do
existujúcich, takže každé ďalšie nasadenie touto cestou znamená novú adresu.

Ak chceš automatické nasadenie pri každom pushi, pripoj vo Verceli GitHub účet
(Settings → Login Connections) a naimportuj repozitár `GorimSK/report`.
Voči živej verzii sú v týchto súboroch navyše len komentáre v zdrojovom kóde
a dlhší `meta description`; obsah stránky je rovnaký.

Projekt je statický, žiadny build. V nastaveniach Vercel projektu:

- **Root Directory:** `prirucka`
- **Framework Preset:** Other
- **Build Command:** prázdne
- **Output Directory:** prázdne (`.`)

Každý push do produkčnej vetvy nasadí produkciu, push do inej vetvy vytvorí preview deployment.

## QR kód

QR v sekcii kontaktu je natvrdo vygenerovaný pre adresu `https://prirucka-marketing.vercel.app`.
**Keď sa zmení adresa stránky, treba ho vygenerovať znova:**

```bash
pip install segno
python3 -c "import segno,io; b=io.BytesIO(); segno.make('https://NOVA-ADRESA', error='m').save(b, kind='svg', xmldecl=False, svgns=True, border=3, dark='#14161f', light='#ffffff', omitsize=True); print(b.getvalue().decode())"
```

Výstup nahraď v `index.html` v bloku `.share-qr` (a uprav aj text odkazu pod ním).

## Úpravy obsahu

Celý text je priamo v `index.html` — sekcie sú oddelené HTML komentármi (`<!-- ================= FUNNEL ================= -->`).
Kontaktné údaje sú v sekcii `#kontakt` a v pätičke.
