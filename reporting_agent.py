"""AI agent pre reporting nad dátami BUX-DATA (Google Sheets).

Agent používa Claude + tool use: model si sám vyberá, ktoré analytické
nástroje zavolá (tržby podľa zdroja, Google Ads kampane, čerpanie rozpočtu,
porovnanie období), a z výsledkov napíše report v slovenčine.

Použitie:
    export ANTHROPIC_API_KEY=...
    python reporting_agent.py report                  # mesačný report -> reports/*.md
    python reporting_agent.py report --period last-week
    python reporting_agent.py chat                    # interaktívne otázky nad dátami
    python reporting_agent.py report --demo           # bez Google Sheets, na vzorových dátach
"""
import argparse
import datetime
import json
import pathlib
import random

import anthropic
import pandas as pd
from anthropic import beta_tool

MODEL = "claude-opus-5"
CREDENTIALS_FILE = "budget-report-keys.json"
SPREADSHEET = "BUX-DATA"
MONTHLY_AD_BUDGET = 3000.0  # rovnaký limit ako v BUX-report.py

SYSTEM_PROMPT = f"""Si dátový analytik pre e-shop BUX. Odpovedáš po slovensky.
Máš k dispozícii nástroje nad dvoma tabuľkami:
- "Report": denné tržby podľa Source/Medium (GA),
- "Google_Ads_Report": denné tržby a náklady podľa Google Ads kampaní.
Mesačný rozpočet na Google Ads je {MONTHLY_AD_BUDGET:.0f} €.

Pravidlá:
- Každé číslo v odpovedi musí pochádzať z výsledku nástroja; nič si nevymýšľaj.
- Ak začínaš a nevieš, aké obdobie dáta pokrývajú, zavolaj najprv get_data_overview.
- Pri reporte porovnaj obdobie s predchádzajúcim rovnako dlhým obdobím.
- Upozorni na anomálie (prudké poklesy/nárasty, kampane s ROAS < 1, prečerpanie rozpočtu).
- Sumy formátuj ako "1 234,56 €", percentá na jedno desatinné miesto.
"""

REPORT_PROMPT = """Priprav manažérsky report za obdobie {start} až {end} v Markdowne:
1. **Zhrnutie** (3-5 odrážok s najdôležitejšími zisteniami)
2. **Tržby podľa zdrojov** (tabuľka + zmena oproti predchádzajúcemu obdobiu)
3. **Google Ads** (kampane: tržby, náklady, ROAS; čerpanie mesačného rozpočtu a projekcia)
4. **Anomálie a riziká**
5. **Odporúčania** (konkrétne kroky na ďalší týždeň)
"""


# ---------------------------------------------------------------------------
# Dáta
# ---------------------------------------------------------------------------

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ("Total Revenue", "Ad Cost"):
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("€", "").str.replace(",", ".").str.strip(),
                errors="coerce",
            ).fillna(0.0)
    return df


def load_sheets() -> dict:
    """Načíta hárky z Google Sheets rovnako ako Streamlit dashboard."""
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    book = gspread.authorize(creds).open(SPREADSHEET)
    frames = {}
    for name in ("Report", "Google_Ads_Report"):
        values = book.worksheet(name).get_all_values()
        frames[name] = _clean(pd.DataFrame(values[1:], columns=values[0]))
    return frames


def load_demo() -> dict:
    """Vzorové dáta s rovnakou štruktúrou, aby sa agent dal vyskúšať bez prístupu k Sheets."""
    rng = random.Random(42)
    days = pd.date_range(end=datetime.date.today(), periods=90, freq="D")
    sources = {"google / cpc": 420, "google / organic": 260, "facebook / cpc": 140, "(direct) / (none)": 90}
    campaigns = {"Search - Brand": (180, 25), "Search - Generic": (160, 55), "PMax - Všetky produkty": (120, 45)}
    report_rows, ads_rows = [], []
    for day in days:
        weekend = 0.75 if day.weekday() >= 5 else 1.0
        for src, base in sources.items():
            report_rows.append([day, src, round(base * weekend * rng.uniform(0.6, 1.4), 2)])
        for camp, (rev, cost) in campaigns.items():
            # "Search - Generic" sa posledné 2 týždne zhoršuje, nech má agent čo nájsť
            decay = 0.45 if camp == "Search - Generic" and day > days[-15] else 1.0
            ads_rows.append([day, camp, round(rev * weekend * decay * rng.uniform(0.6, 1.4), 2),
                             round(cost * rng.uniform(0.8, 1.2), 2)])
    return {
        "Report": pd.DataFrame(report_rows, columns=["Date", "Source/Medium", "Total Revenue"]),
        "Google_Ads_Report": pd.DataFrame(ads_rows, columns=["Date", "Campaign Name", "Total Revenue", "Ad Cost"]),
    }


DATA: dict = {}


def _parse_date(value: str) -> datetime.date:
    return datetime.date.fromisoformat(value)


def _between(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    start, end = _parse_date(start_date), _parse_date(end_date)
    return df[(df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)]


def _ads(start_date: str, end_date: str) -> pd.DataFrame:
    df = _between(DATA["Google_Ads_Report"], start_date, end_date)
    return df[~df["Campaign Name"].str.contains(r"\(not set\)|\(direct\)", na=False)]


def _to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Nástroje pre agenta
# ---------------------------------------------------------------------------

@beta_tool
def get_data_overview() -> str:
    """Vráti rozsah dátumov, zoznam zdrojov (Source/Medium) a kampaní, ktoré sú v dátach dostupné."""
    rep, ads = DATA["Report"], DATA["Google_Ads_Report"]
    return _to_json({
        "today": datetime.date.today().isoformat(),
        "report": {"from": rep["Date"].min().date(), "to": rep["Date"].max().date(),
                   "sources": sorted(rep["Source/Medium"].unique().tolist())},
        "google_ads": {"from": ads["Date"].min().date(), "to": ads["Date"].max().date(),
                       "campaigns": sorted(ads["Campaign Name"].unique().tolist())},
    })


@beta_tool
def revenue_by_source(start_date: str, end_date: str) -> str:
    """Súčet tržieb podľa Source/Medium za obdobie, zoradené zostupne, vrátane podielu na celku.

    Args:
        start_date: Začiatok obdobia vo formáte YYYY-MM-DD (vrátane).
        end_date: Koniec obdobia vo formáte YYYY-MM-DD (vrátane).
    """
    df = _between(DATA["Report"], start_date, end_date)
    total = float(df["Total Revenue"].sum())
    grouped = df.groupby("Source/Medium")["Total Revenue"].sum().sort_values(ascending=False)
    return _to_json({
        "total_revenue": round(total, 2),
        "by_source": [{"source_medium": k, "revenue": round(v, 2),
                       "share_pct": round(100 * v / total, 1) if total else 0.0}
                      for k, v in grouped.items()],
    })


@beta_tool
def daily_revenue(start_date: str, end_date: str, source_medium: str = "") -> str:
    """Denný vývoj tržieb (vhodné na hľadanie trendov a anomálií).

    Args:
        start_date: Začiatok obdobia vo formáte YYYY-MM-DD.
        end_date: Koniec obdobia vo formáte YYYY-MM-DD.
        source_medium: Voliteľný filter na jeden zdroj, napr. "google / cpc". Prázdne = všetky zdroje.
    """
    df = _between(DATA["Report"], start_date, end_date)
    if source_medium:
        df = df[df["Source/Medium"] == source_medium]
    daily = df.groupby(df["Date"].dt.date)["Total Revenue"].sum()
    return _to_json({
        "mean": round(float(daily.mean()), 2) if len(daily) else 0.0,
        "days": [{"date": d, "revenue": round(v, 2)} for d, v in daily.items()],
    })


@beta_tool
def google_ads_campaigns(start_date: str, end_date: str) -> str:
    """Výkon Google Ads kampaní za obdobie: tržby, náklady a ROAS (tržby / náklady).

    Args:
        start_date: Začiatok obdobia vo formáte YYYY-MM-DD.
        end_date: Koniec obdobia vo formáte YYYY-MM-DD.
    """
    df = _ads(start_date, end_date)
    g = df.groupby("Campaign Name").agg(revenue=("Total Revenue", "sum"), cost=("Ad Cost", "sum"))
    g["roas"] = (g["revenue"] / g["cost"]).where(g["cost"] > 0)
    rows = [{"campaign": k, "revenue": round(r.revenue, 2), "cost": round(r.cost, 2),
             "roas": None if pd.isna(r.roas) else round(r.roas, 2)}
            for k, r in g.sort_values("revenue", ascending=False).iterrows()]
    return _to_json({"total_revenue": round(float(g["revenue"].sum()), 2),
                     "total_cost": round(float(g["cost"].sum()), 2), "campaigns": rows})


@beta_tool
def ad_budget_status(month: str) -> str:
    """Čerpanie mesačného rozpočtu Google Ads a lineárna projekcia do konca mesiaca.

    Args:
        month: Mesiac vo formáte YYYY-MM.
    """
    first = _parse_date(f"{month}-01")
    last = (first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    df = _ads(first.isoformat(), last.isoformat())
    spent = float(df["Ad Cost"].sum())
    days_with_data = df["Date"].dt.date.nunique()
    days_in_month = last.day
    projected = spent / days_with_data * days_in_month if days_with_data else 0.0
    return _to_json({
        "month": month, "budget": MONTHLY_AD_BUDGET, "spent": round(spent, 2),
        "spent_pct": round(100 * spent / MONTHLY_AD_BUDGET, 1),
        "days_with_data": days_with_data, "days_in_month": days_in_month,
        "projected_month_spend": round(projected, 2),
        "projected_over_budget": projected > MONTHLY_AD_BUDGET,
    })


@beta_tool
def compare_periods(current_start: str, current_end: str, previous_start: str, previous_end: str) -> str:
    """Porovná dve obdobia: tržby podľa zdrojov a náklady/tržby Google Ads, s percentuálnou zmenou.

    Args:
        current_start: Začiatok aktuálneho obdobia (YYYY-MM-DD).
        current_end: Koniec aktuálneho obdobia (YYYY-MM-DD).
        previous_start: Začiatok porovnávaného obdobia (YYYY-MM-DD).
        previous_end: Koniec porovnávaného obdobia (YYYY-MM-DD).
    """
    def pct(cur, prev):
        return round(100 * (cur - prev) / prev, 1) if prev else None

    cur = _between(DATA["Report"], current_start, current_end).groupby("Source/Medium")["Total Revenue"].sum()
    prev = _between(DATA["Report"], previous_start, previous_end).groupby("Source/Medium")["Total Revenue"].sum()
    sources = sorted(set(cur.index) | set(prev.index))
    cur_ads, prev_ads = _ads(current_start, current_end), _ads(previous_start, previous_end)
    return _to_json({
        "revenue_total": {"current": round(cur.sum(), 2), "previous": round(prev.sum(), 2),
                          "change_pct": pct(cur.sum(), prev.sum())},
        "by_source": [{"source_medium": s, "current": round(cur.get(s, 0.0), 2),
                       "previous": round(prev.get(s, 0.0), 2),
                       "change_pct": pct(cur.get(s, 0.0), prev.get(s, 0.0))} for s in sources],
        "google_ads": {
            "cost": {"current": round(cur_ads["Ad Cost"].sum(), 2), "previous": round(prev_ads["Ad Cost"].sum(), 2),
                     "change_pct": pct(cur_ads["Ad Cost"].sum(), prev_ads["Ad Cost"].sum())},
            "revenue": {"current": round(cur_ads["Total Revenue"].sum(), 2),
                        "previous": round(prev_ads["Total Revenue"].sum(), 2),
                        "change_pct": pct(cur_ads["Total Revenue"].sum(), prev_ads["Total Revenue"].sum())},
        },
    })


TOOLS = [get_data_overview, revenue_by_source, daily_revenue, google_ads_campaigns,
         ad_budget_status, compare_periods]


# ---------------------------------------------------------------------------
# Agentová slučka
# ---------------------------------------------------------------------------

def run_agent(client: anthropic.Anthropic, messages: list) -> str:
    """Spustí agenta nad históriou `messages` (doplní ju o odpovede) a vráti finálny text."""
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=list(messages),
        # pri odmietnutí požiadavky API automaticky skúsi záložný model
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    final = None
    for message in runner:
        final = message
        messages.append({"role": "assistant", "content": message.content})
        for block in message.content:
            if block.type == "tool_use":
                print(f"  → {block.name}({json.dumps(block.input, ensure_ascii=False)})")
        tool_response = runner.generate_tool_call_response()
        if tool_response is not None:
            messages.append(tool_response)

    if final is None:
        return ""
    if final.stop_reason == "refusal":
        return "Model požiadavku odmietol."
    return "".join(b.text for b in final.content if b.type == "text")


def period_bounds(period: str) -> tuple:
    today = datetime.date.today()
    if period == "last-week":
        end = today - datetime.timedelta(days=today.weekday() + 1)  # posledná nedeľa
        return end - datetime.timedelta(days=6), end
    if period == "last-month":
        end = today.replace(day=1) - datetime.timedelta(days=1)
        return end.replace(day=1), end
    return today.replace(day=1), today  # this-month


def cmd_report(client: anthropic.Anthropic, period: str) -> None:
    start, end = period_bounds(period)
    print(f"Generujem report za {start} – {end} ...")
    text = run_agent(client, [{"role": "user", "content": REPORT_PROMPT.format(start=start, end=end)}])
    out = pathlib.Path("reports") / f"report-{start}-{end}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n{text}\n\nUložené do {out}")


def cmd_chat(client: anthropic.Anthropic) -> None:
    print("Pýtaj sa na dáta (napr. 'Ktorá kampaň mala minulý týždeň najhorší ROAS?'). Koniec: prázdny riadok.")
    messages: list = []
    while True:
        question = input("\nTy: ").strip()
        if not question:
            break
        messages.append({"role": "user", "content": question})
        print(f"\nAgent: {run_agent(client, messages)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI reporting agent pre BUX-DATA")
    parser.add_argument("mode", choices=["report", "chat"])
    parser.add_argument("--period", choices=["this-month", "last-month", "last-week"], default="this-month")
    parser.add_argument("--demo", action="store_true", help="použiť vzorové dáta namiesto Google Sheets")
    args = parser.parse_args()

    DATA.update(load_demo() if args.demo else load_sheets())
    client = anthropic.Anthropic()
    if args.mode == "report":
        cmd_report(client, args.period)
    else:
        cmd_chat(client)


if __name__ == "__main__":
    main()
