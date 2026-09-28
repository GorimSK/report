import datetime as dt

import pandas as pd
import pytest

from agent import resolve_period
from reporting import metrics
from reporting.normalize import build_unified, normalize_source, parse_number


def make_df(rows):
    df = pd.DataFrame(rows, columns=["date", "source", "campaign", "spend", "impressions", "clicks", "conversions", "revenue"])
    df["date"] = pd.to_datetime(df["date"])
    return build_unified([df])


@pytest.mark.parametrize("raw, expected", [
    ("€ 1 234,56", 1234.56),
    ("1,234.56", 1234.56),
    ("1.234,56 €", 1234.56),
    ("12,5", 12.5),
    ("1,234,567", 1234567.0),
    ("", 0.0),
    ("-", 0.0),
    (None, 0.0),
    (42, 42.0),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_normalize_source_maps_columns_and_fills_missing():
    raw = pd.DataFrame({"Day": ["2026-09-01", "2026-09-02", "bad"], "Cost": ["€ 10,50", "20", "5"], "Campaign": ["A", "B", "C"]})
    out = normalize_source(raw, "google_ads", {"date": "Day", "spend": "Cost", "campaign": "Campaign", "revenue": "Missing"})
    assert list(out["spend"]) == [10.5, 20.0]  # riadok s neplatným dátumom vypadne
    assert (out["revenue"] == 0).all()
    assert set(out["source"]) == {"google_ads"}


def test_normalize_source_requires_date_column():
    with pytest.raises(ValueError):
        normalize_source(pd.DataFrame({"x": [1]}), "meta", {"date": "Date"})


def test_summarize_ratios_and_zero_division():
    df = make_df([
        ("2026-09-01", "google_ads", "A", 100, 1000, 50, 5, 400),
        ("2026-09-01", "meta", "B", 50, 0, 0, 0, 0),
    ])
    by_source = {r["source"]: r for r in metrics.summarize(df, dt.date(2026, 9, 1), dt.date(2026, 9, 1), "source")}
    g = by_source["google_ads"]
    assert g["ctr"] == 0.05 and g["cpc"] == 2.0 and g["cpa"] == 20.0 and g["roas"] == 4.0
    m = by_source["meta"]
    assert m["ctr"] is None and m["cpa"] is None and m["roas"] == 0.0


def test_compare_periods_uses_equal_previous_window():
    df = make_df([
        ("2026-09-01", "google_ads", "A", 100, 0, 0, 0, 200),
        ("2026-09-02", "google_ads", "A", 100, 0, 0, 0, 200),
        ("2026-09-03", "google_ads", "A", 150, 0, 0, 0, 600),
        ("2026-09-04", "google_ads", "A", 150, 0, 0, 0, 600),
    ])
    result = metrics.compare_periods(df, dt.date(2026, 9, 3), dt.date(2026, 9, 4), "source")
    assert result["previous_period"] == ["2026-09-01", "2026-09-02"]
    row = result["rows"][0]
    assert row["spend"] == 300 and row["spend_prev"] == 200 and row["spend_change_pct"] == 50.0
    assert row["roas_change_pct"] == 100.0


def test_detect_anomalies_flags_spike():
    rows = [(f"2026-09-{d:02d}", "meta", "A", 100 + (d % 3), 0, 0, 0, 0) for d in range(1, 15)]
    rows.append(("2026-09-15", "meta", "A", 400, 0, 0, 0, 0))
    found = metrics.detect_anomalies(make_df(rows), "spend", dt.date(2026, 9, 15))
    assert len(found) == 1 and found[0]["direction"] == "up"
    assert metrics.detect_anomalies(make_df(rows), "spend", dt.date(2026, 9, 14)) == []


def test_budget_pacing_projects_month_end():
    rows = [(f"2026-09-{d:02d}", "google_ads", "A", 100, 0, 0, 0, 0) for d in range(1, 11)]
    rows.append(("2026-08-31", "google_ads", "A", 999, 0, 0, 0, 0))  # iný mesiac sa nepočíta
    pacing = metrics.budget_pacing(make_df(rows), {"google_ads": 3000, "meta": 1000}, dt.date(2026, 9, 10))
    g = next(p for p in pacing if p["source"] == "google_ads")
    assert g["spent_mtd"] == 1000 and g["projected_month_end"] == 3000
    assert next(p for p in pacing if p["source"] == "meta")["spent_mtd"] == 0


@pytest.mark.parametrize("period, as_of, expected", [
    ("last_7_days", "2026-09-20", ("2026-09-14", "2026-09-20")),
    ("mtd", "2026-12-15", ("2026-12-01", "2026-12-15")),
    ("last_month", "2026-01-10", ("2025-12-01", "2025-12-31")),
    ("last_week", "2026-09-23", ("2026-09-14", "2026-09-20")),  # streda → predošlý Po–Ne
    ("last_week", "2026-09-20", ("2026-09-14", "2026-09-20")),  # nedeľa → aktuálny týždeň
])
def test_resolve_period(period, as_of, expected):
    start, end = resolve_period(period, dt.date.fromisoformat(as_of))
    assert (start.isoformat(), end.isoformat()) == expected
