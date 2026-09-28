"""Reporting agent: načíta dáta z Google Sheets, spočíta KPI a Claude napíše komentár.

Príklady:
    python agent.py --period last_7_days
    python agent.py --period last_month --write-sheet
    python agent.py --csv tests/fixtures/unified.csv --period mtd --as-of 2026-09-20 --dry-run
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import anthropic
import pandas as pd
from anthropic import beta_tool

from reporting import metrics
from reporting.normalize import build_unified, normalize_source

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """Si senior performance marketing analytik. Píšeš reporty pre klienta v slovenčine.

Máš nástroje, ktoré vracajú presné čísla z Google Ads, Meta Ads a ďalších zdrojov (jednotná schéma:
spend, impressions, clicks, conversions, revenue; odvodené CTR, CPC, CVR, CPA, ROAS). Všetky čísla
v reporte musia pochádzať z nástrojov – nič si nevymýšľaj. Keď dáta chýbajú, povedz to.

Postup: zisti súhrn za obdobie, porovnaj s predchádzajúcim obdobím podľa zdroja aj kampaní,
skontroluj čerpanie rozpočtu a anomálie (aspoň spend, conversions, roas).

Formát výstupu (Markdown):
## Zhrnutie – 3 až 5 viet, najdôležitejšie čísla a zmena voči minulému obdobiu
## Kanály – tabuľka: zdroj | spend | revenue | ROAS | CPA | zmena ROAS %
## Čo sa zmenilo a prečo – konkrétne kampane, ktoré zmenu spôsobili
## Rozpočet – čerpanie a projekcia na koniec mesiaca
## Upozornenia – anomálie (ak žiadne, napíš to)
## Odporúčania – presne 3 konkrétne kroky s očakávaným dopadom
"""


def resolve_period(period: str, as_of: dt.date) -> tuple[dt.date, dt.date]:
    if period == "yesterday":
        return as_of, as_of
    if period == "last_7_days":
        return as_of - dt.timedelta(days=6), as_of
    if period == "last_30_days":
        return as_of - dt.timedelta(days=29), as_of
    if period == "last_week":  # posledný celý týždeň pondelok–nedeľa
        end = as_of - dt.timedelta(days=as_of.weekday() + 1) if as_of.weekday() != 6 else as_of
        return end - dt.timedelta(days=6), end
    if period == "mtd":
        return as_of.replace(day=1), as_of
    if period == "last_month":
        end = as_of.replace(day=1) - dt.timedelta(days=1)
        return end.replace(day=1), end
    raise ValueError(f"Neznáme obdobie: {period}")


def load_data(config: dict, csv_path: str | None) -> pd.DataFrame:
    if csv_path:
        df = pd.read_csv(csv_path, parse_dates=["date"])
        return build_unified([df])

    from reporting.sheets import get_client, open_spreadsheet, read_tab

    sheet = open_spreadsheet(get_client(), config["spreadsheet"])
    frames = []
    for src in config["sources"]:
        raw = read_tab(sheet, src["tab"])
        frames.append(normalize_source(raw, src["name"], src["columns"]))
    return build_unified(frames)


def make_tools(df: pd.DataFrame, budgets: dict, as_of: dt.date):
    def _parse(date: str) -> dt.date:
        return dt.date.fromisoformat(date)

    def _json(obj) -> str:
        return json.dumps(obj, ensure_ascii=False, default=str)

    @beta_tool
    def list_sources() -> str:
        """Zoznam zdrojov a kampaní v dátach s rozsahom dátumov. Zavolaj ako prvé."""
        return _json({
            "date_range": [df["date"].min().date().isoformat(), df["date"].max().date().isoformat()] if len(df) else None,
            "sources": sorted(df["source"].unique().tolist()),
            "campaigns_per_source": {s: sorted(g["campaign"].unique().tolist()) for s, g in df.groupby("source")},
        })

    @beta_tool
    def get_kpis(start_date: str, end_date: str, group_by: str = "") -> str:
        """Súčty a pomerové KPI (CTR, CPC, CVR, CPA, ROAS) za obdobie.

        Args:
            start_date: Začiatok obdobia vo formáte YYYY-MM-DD (vrátane).
            end_date: Koniec obdobia vo formáte YYYY-MM-DD (vrátane).
            group_by: Prázdne pre celkový súčet, alebo 'source' či 'campaign'.
        """
        return _json(metrics.summarize(df, _parse(start_date), _parse(end_date), group_by or None))

    @beta_tool
    def compare_periods(start_date: str, end_date: str, group_by: str = "source") -> str:
        """Porovná obdobie s rovnako dlhým predchádzajúcim obdobím, vráti hodnoty a zmenu v %.

        Args:
            start_date: Začiatok aktuálneho obdobia YYYY-MM-DD.
            end_date: Koniec aktuálneho obdobia YYYY-MM-DD.
            group_by: 'source', 'campaign' alebo prázdne pre celok.
        """
        return _json(metrics.compare_periods(df, _parse(start_date), _parse(end_date), group_by or None))

    @beta_tool
    def detect_anomalies(metric: str, date: str = "") -> str:
        """Nájde dni, keď sa metrika per zdroj výrazne odchýlila (|z| >= 2) od predošlých 14 dní.

        Args:
            metric: spend, impressions, clicks, conversions, revenue, ctr, cpc, cvr, cpa alebo roas.
            date: Deň na kontrolu YYYY-MM-DD; prázdne = posledný deň reportu.
        """
        return _json(metrics.detect_anomalies(df, metric, _parse(date) if date else as_of))

    @beta_tool
    def budget_pacing() -> str:
        """Čerpanie mesačného rozpočtu per zdroj k poslednému dňu reportu a projekcia na koniec mesiaca."""
        return _json(metrics.budget_pacing(df, budgets, as_of))

    return [list_sources, get_kpis, compare_periods, detect_anomalies, budget_pacing]


def run_agent(tools, start: dt.date, end: dt.date, currency: str) -> str:
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        tools=tools,
        messages=[{
            "role": "user",
            "content": f"Priprav report za obdobie {start.isoformat()} až {end.isoformat()}. Mena: {currency}.",
        }],
    )
    final = None
    for message in runner:
        final = message
    if final is None:
        raise RuntimeError("Agent nevrátil žiadnu odpoveď.")
    if final.stop_reason == "refusal":
        raise RuntimeError(f"Model odmietol požiadavku: {final.stop_details}")
    return "\n".join(b.text for b in final.content if b.type == "text").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--period", default="last_7_days",
                        choices=["yesterday", "last_7_days", "last_30_days", "last_week", "mtd", "last_month"])
    parser.add_argument("--as-of", help="Posledný deň s dátami YYYY-MM-DD (default: včera)")
    parser.add_argument("--csv", help="Namiesto Google Sheets načítaj jednotné dáta z CSV")
    parser.add_argument("--out", help="Ulož report do súboru (Markdown)")
    parser.add_argument("--write-sheet", action="store_true", help="Zapíš report do záložky report_tab")
    parser.add_argument("--dry-run", action="store_true", help="Bez volania Claude – vypíš len výstupy nástrojov")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today() - dt.timedelta(days=1)
    start, end = resolve_period(args.period, as_of)

    df = load_data(config, args.csv)
    if df.empty:
        print("Žiadne dáta – skontroluj config a záložky v Sheete.", file=sys.stderr)
        return 1

    tools = make_tools(df, config.get("monthly_budget", {}), end)

    if args.dry_run:
        for tool, kwargs in [
            (tools[0], {}),
            (tools[1], {"start_date": start.isoformat(), "end_date": end.isoformat(), "group_by": "source"}),
            (tools[2], {"start_date": start.isoformat(), "end_date": end.isoformat(), "group_by": "source"}),
            (tools[3], {"metric": "spend"}),
            (tools[4], {}),
        ]:
            print(f"### {tool.name}\n{tool.call(kwargs)}\n")
        return 0

    report = run_agent(tools, start, end, config.get("currency", "EUR"))
    print(report)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
    if args.write_sheet:
        from reporting.sheets import append_report, get_client, open_spreadsheet

        sheet = open_spreadsheet(get_client(), config["spreadsheet"])
        append_report(sheet, config.get("report_tab", "AI_Report"), f"{start} – {end}", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
