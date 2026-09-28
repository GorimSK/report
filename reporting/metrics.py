"""KPI výpočty nad jednotnou schémou (viď normalize.UNIFIED_COLUMNS)."""
import calendar
import datetime as dt

import pandas as pd

from reporting.normalize import NUMERIC_COLUMNS


def _div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def add_ratios(row: dict) -> dict:
    row["ctr"] = _div(row["clicks"], row["impressions"])
    row["cpc"] = _div(row["spend"], row["clicks"])
    row["cvr"] = _div(row["conversions"], row["clicks"])
    row["cpa"] = _div(row["spend"], row["conversions"])
    row["roas"] = _div(row["revenue"], row["spend"])
    return row


def filter_period(df: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    dates = df["date"].dt.date
    return df[(dates >= start) & (dates <= end)]


def summarize(df: pd.DataFrame, start: dt.date, end: dt.date, group_by: str | None = None) -> list[dict]:
    """Súčty + CTR/CPC/CVR/CPA/ROAS za obdobie, voliteľne podľa 'source' alebo 'campaign'."""
    period = filter_period(df, start, end)
    if group_by:
        grouped = period.groupby(group_by)[NUMERIC_COLUMNS].sum().reset_index()
        rows = grouped.to_dict("records")
    else:
        rows = [{"group": "total", **period[NUMERIC_COLUMNS].sum().to_dict()}]
    return [add_ratios({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}) for r in rows]


def previous_period(start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    """Rovnako dlhé obdobie tesne pred [start, end]."""
    length = (end - start).days + 1
    prev_end = start - dt.timedelta(days=1)
    return prev_end - dt.timedelta(days=length - 1), prev_end


def compare_periods(df: pd.DataFrame, start: dt.date, end: dt.date, group_by: str | None = None) -> dict:
    prev_start, prev_end = previous_period(start, end)
    key = group_by or "group"
    current = {r[key]: r for r in summarize(df, start, end, group_by)}
    previous = {r[key]: r for r in summarize(df, prev_start, prev_end, group_by)}

    rows = []
    for name in sorted(set(current) | set(previous)):
        cur, prev = current.get(name, {}), previous.get(name, {})
        row = {key: name}
        for metric in NUMERIC_COLUMNS + ["ctr", "cpc", "cvr", "cpa", "roas"]:
            c, p = cur.get(metric), prev.get(metric)
            row[metric] = c
            row[f"{metric}_prev"] = p
            row[f"{metric}_change_pct"] = round((c - p) / p * 100, 1) if c is not None and p else None
        rows.append(row)
    return {
        "current_period": [start.isoformat(), end.isoformat()],
        "previous_period": [prev_start.isoformat(), prev_end.isoformat()],
        "rows": rows,
    }


def detect_anomalies(df: pd.DataFrame, metric: str, as_of: dt.date, lookback: int = 14, z: float = 2.0) -> list[dict]:
    """Porovná deň `as_of` s priemerom a smerodajnou odchýlkou predchádzajúcich `lookback` dní per zdroj."""
    anomalies = []
    for source, group in df.groupby("source"):
        daily = group.groupby(group["date"].dt.date)[NUMERIC_COLUMNS].sum()
        daily = daily.reindex(pd.date_range(as_of - dt.timedelta(days=lookback), as_of).date, fill_value=0.0)
        if metric in ("ctr", "cpc", "cvr", "cpa", "roas"):
            series = pd.Series({d: add_ratios(dict(r)).get(metric) for d, r in daily.iterrows()}, dtype=float)
        else:
            series = daily[metric].astype(float)
        history, today = series.iloc[:-1].dropna(), series.iloc[-1]
        if len(history) < 7 or pd.isna(today):
            continue
        mean, std = history.mean(), history.std()
        if not std:
            continue
        score = (today - mean) / std
        if abs(score) >= z:
            anomalies.append({
                "source": source, "metric": metric, "date": as_of.isoformat(),
                "value": round(float(today), 2), "baseline_mean": round(float(mean), 2),
                "z_score": round(float(score), 2), "direction": "up" if score > 0 else "down",
            })
    return anomalies


def budget_pacing(df: pd.DataFrame, budgets: dict, as_of: dt.date) -> list[dict]:
    """Čerpanie mesačného rozpočtu k dňu `as_of` a lineárna projekcia na koniec mesiaca."""
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    month_df = filter_period(df, as_of.replace(day=1), as_of)
    spend_by_source = month_df.groupby("source")["spend"].sum().to_dict()

    rows = []
    for source, budget in budgets.items():
        spent = float(spend_by_source.get(source, 0.0))
        projected = spent / as_of.day * days_in_month
        rows.append({
            "source": source,
            "monthly_budget": budget,
            "spent_mtd": round(spent, 2),
            "spent_pct": _div(spent, budget),
            "expected_pct": round(as_of.day / days_in_month, 4),
            "projected_month_end": round(projected, 2),
            "projected_vs_budget_pct": _div(projected, budget),
        })
    return rows
