"""Načítanie dát z Google Sheets cez service account.

Credentials sa nikdy nečítajú z repa. Poradie:
1. GOOGLE_SERVICE_ACCOUNT_JSON – celý JSON kľúča v premennej prostredia (CI / GitHub Actions secret)
2. GOOGLE_APPLICATION_CREDENTIALS – cesta k JSON súboru mimo repa
"""
import json
import os

import gspread
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_client() -> gspread.Client:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return gspread.service_account_from_dict(json.loads(raw), scopes=SCOPES)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path:
        return gspread.service_account(filename=path, scopes=SCOPES)
    raise RuntimeError(
        "Chýbajú Google credentials: nastav GOOGLE_SERVICE_ACCOUNT_JSON "
        "alebo GOOGLE_APPLICATION_CREDENTIALS."
    )


def open_spreadsheet(client: gspread.Client, spreadsheet: str) -> gspread.Spreadsheet:
    """`spreadsheet` môže byť názov, key alebo celá URL."""
    if spreadsheet.startswith("https://"):
        return client.open_by_url(spreadsheet)
    try:
        return client.open(spreadsheet)
    except gspread.SpreadsheetNotFound:
        return client.open_by_key(spreadsheet)


def read_tab(sheet: gspread.Spreadsheet, tab: str) -> pd.DataFrame:
    """Vráti záložku ako DataFrame so stringovými hodnotami (parsovanie rieši normalize)."""
    values = sheet.worksheet(tab).get_all_values()
    if not values:
        return pd.DataFrame()
    header, *rows = values
    return pd.DataFrame(rows, columns=header)


def append_report(sheet: gspread.Spreadsheet, tab: str, period: str, text: str) -> None:
    """Pridá vygenerovaný report ako nový riadok (created_at | period | report)."""
    try:
        ws = sheet.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(tab, rows=100, cols=3)
        ws.append_row(["created_at", "period", "report"])
    ws.append_row([pd.Timestamp.now().isoformat(timespec="seconds"), period, text])
