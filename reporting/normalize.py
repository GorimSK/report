"""Prevod rôznych exportov (Google Ads, Meta, ...) do jednej schémy.

Jednotná schéma:
    date | source | campaign | spend | impressions | clicks | conversions | revenue
"""
import re

import pandas as pd

UNIFIED_COLUMNS = ["date", "source", "campaign", "spend", "impressions", "clicks", "conversions", "revenue"]
NUMERIC_COLUMNS = ["spend", "impressions", "clicks", "conversions", "revenue"]

_NON_NUMERIC = re.compile(r"[^\d,.\-]")


def parse_number(value) -> float:
    """Parsuje čísla v tvare '€ 1 234,56', '1,234.56', '12%', '' → float (prázdne = 0)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if pd.isna(value) else float(value)
    text = _NON_NUMERIC.sub("", str(value))
    if text in ("", "-", ".", ","):
        return 0.0
    if "," in text and "." in text:
        # Oddeľovač desatinných miest je ten, ktorý je posledný
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # Jedna čiarka = desatinná (SK formát), viac čiarok = tisícky
        text = text.replace(",", ".") if text.count(",") == 1 else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_source(raw: pd.DataFrame, source: str, columns: dict) -> pd.DataFrame:
    """Premapuje stĺpce jedného zdroja podľa configu. Chýbajúce metriky = 0."""
    if raw.empty:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    if columns.get("date") not in raw.columns:
        raise ValueError(f"Zdroj '{source}': v záložke chýba dátumový stĺpec '{columns.get('date')}'")

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw[columns["date"]], errors="coerce").dt.normalize()
    out["source"] = source
    campaign_col = columns.get("campaign")
    out["campaign"] = raw[campaign_col].astype(str) if campaign_col in raw.columns else "(all)"
    for metric in NUMERIC_COLUMNS:
        col = columns.get(metric)
        out[metric] = raw[col].map(parse_number) if col in raw.columns else 0.0

    return out.dropna(subset=["date"]).reset_index(drop=True)


def build_unified(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)
    return pd.concat(frames, ignore_index=True)[UNIFIED_COLUMNS].sort_values("date").reset_index(drop=True)
