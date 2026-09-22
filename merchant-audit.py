#!/usr/bin/env python3
"""
Balabim — audit Merchant Center uctov cez Merchant API.

Vypise vsetky MC (pod)ucty, ktore vidi dany service account: ID, nazov,
domenu, stav overenia domeny a otvorene account issues. Domenu potom sparuje
s trhom podla tabulky pristupov a porovna zistenie s tym, co je zapisane
v Asane.

Pouziva Merchant API (merchantapi.googleapis.com), nie legacy Content API
for Shopping — ten sa doziva.

Pouzitie:
    python3 merchant-audit.py --key sa-key.json
    python3 merchant-audit.py --key sa-key.json --advanced-account 123456789
    python3 merchant-audit.py --key sa-key.json --csv out.csv --json out.json

Bez --advanced-account vypise vsetky ucty, ku ktorym ma service account
pristup. S nim vylistuje poducty daneho advanced (multi-client) uctu.

Kluc sa NEUKLADA do repa — cesta sa zadava parametrom --key alebo cez
GOOGLE_APPLICATION_CREDENTIALS.

Pozn.: cesty su pisane proti v1beta. Ak Google medzitym presunul resource
na stabilnu verziu, spusti s --api-version v1.
"""

import argparse
import csv
import json
import os
import sys

import google.auth
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

BASE = "https://merchantapi.googleapis.com"
SCOPE = "https://www.googleapis.com/auth/content"

# Tabulka pristupov (stav k 17.9.2026) + ID z auditov v Asane z 13.9.2026.
# mc_claimed = Merchant Center ID, ktore sa v Asane uvadza pre dany trh.
# ga4 = GA4 property z matice z 1.9.2026 — pri HR a BG sedi s mc_claimed,
# co je podozrive a prave to ideme overit.
MARKETS = {
    "balabim.sk":          {"market": "SK", "ads": "409-714-8334",  "merchant_expected": "ANO", "ga4": "322870326", "mc_claimed": "137426137"},
    "balabim.cz":          {"market": "CZ", "ads": "949-557-5099",  "merchant_expected": "ANO", "ga4": "312939510", "mc_claimed": None},
    "eredetiajandekok.hu": {"market": "HU", "ads": "796-769-0023",  "merchant_expected": "NIE", "ga4": "296576906", "mc_claimed": None},
    "balabim.ro":          {"market": "RO", "ads": "935-423-4466",  "merchant_expected": "NIE - treba vytvorit novy", "ga4": "322849461", "mc_claimed": None},
    "balabim.bg":          {"market": "BG", "ads": "939-573-0588",  "merchant_expected": "NIE", "ga4": "343783421", "mc_claimed": "343783421"},
    "balabim.si":          {"market": "SI", "ads": "566-293-9274",  "merchant_expected": "NIE", "ga4": "309425018", "mc_claimed": "284143602"},
    "balabim.hr":          {"market": "HR", "ads": "446-898-0090",  "merchant_expected": "NIE", "ga4": "254625984", "mc_claimed": "254625984"},
    "balabim.pl":          {"market": "PL", "ads": "AW-794644383",  "merchant_expected": "NIE", "ga4": "G-2ZN97JCD0E", "mc_claimed": None},
    "balabim.gr":          {"market": "GR", "ads": "AW-11187542719", "merchant_expected": "ANO", "ga4": "377455815", "mc_claimed": None},
    "balabim.de":          {"market": "DE", "ads": "NIE - zruseny", "merchant_expected": "NIE", "ga4": "349960635", "mc_claimed": None},
    "balabim.com":         {"market": "COM", "ads": "NIE - zruseny", "merchant_expected": "NIE", "ga4": None, "mc_claimed": None},
}


def build_session(key_path):
    if key_path:
        creds = service_account.Credentials.from_service_account_file(key_path, scopes=[SCOPE])
    else:
        creds, _ = google.auth.default(scopes=[SCOPE])
    return AuthorizedSession(creds)


def get(session, path, params=None):
    """GET na Merchant API. Vracia (data, chyba)."""
    resp = session.get(f"{BASE}{path}", params=params or {})
    if resp.status_code != 200:
        detail = resp.text.strip().replace("\n", " ")[:200]
        return None, f"HTTP {resp.status_code}: {detail}"
    return resp.json(), None


def paged(session, path, key, params=None):
    """Prejde vsetky stranky a vrati zoznam poloziek pod `key`."""
    items, token, params = [], None, dict(params or {})
    while True:
        if token:
            params["pageToken"] = token
        data, err = get(session, path, params)
        if err:
            return items, err
        items.extend(data.get(key, []))
        token = data.get("nextPageToken")
        if not token:
            return items, None


def domain_of(uri):
    if not uri:
        return None
    d = uri.split("//")[-1].split("/")[0].lower()
    return d[4:] if d.startswith("www.") else d


def collect(session, ver, advanced):
    if advanced:
        path = f"/accounts/{ver}/accounts/{advanced}:listSubaccounts"
    else:
        path = f"/accounts/{ver}/accounts"
    accounts, err = paged(session, path, "accounts")
    if err:
        print(f"CHYBA pri nacitani uctov: {err}", file=sys.stderr)
        if not accounts:
            sys.exit(1)

    rows = []
    for acc in accounts:
        name = acc.get("name", "")
        acc_id = name.split("/")[-1]

        homepage, hp_err = get(session, f"/accounts/{ver}/{name}/homepage")
        uri = homepage.get("uri") if homepage else None
        claimed = homepage.get("claimed") if homepage else None

        issues, iss_err = paged(session, f"/accounts/{ver}/{name}/issues", "accountIssues")
        if iss_err:
            issue_summary = "n/a"
        elif not issues:
            issue_summary = "ziadne"
        else:
            issue_summary = "; ".join(
                f"{i.get('severity', '?')}: {i.get('title', '?')}" for i in issues[:3]
            )
            if len(issues) > 3:
                issue_summary += f" (+{len(issues) - 3})"

        dom = domain_of(uri)
        m = MARKETS.get(dom, {})
        rows.append({
            "mc_id": acc_id,
            "nazov": acc.get("accountName", ""),
            "domena": dom or (uri or "-"),
            "domena_overena": {True: "ANO", False: "NIE"}.get(claimed, "n/a"),
            "trh": m.get("market", "?"),
            "merchant_v_tabulke": m.get("merchant_expected", "-"),
            "mc_id_v_asane": m.get("mc_claimed") or "-",
            "test_ucet": "ANO" if acc.get("testAccount") else "NIE",
            "issues": issue_summary,
            "homepage_chyba": hp_err or "",
        })
    return rows


def print_table(rows):
    cols = ["mc_id", "nazov", "domena", "domena_overena", "trh", "merchant_v_tabulke", "mc_id_v_asane", "issues"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols} if rows else {}
    print()
    print("  ".join(c.upper().ljust(widths[c]) for c in cols))
    print("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


def crosscheck(rows):
    found_ids = {r["mc_id"] for r in rows}
    found_markets = {r["trh"] for r in rows if r["trh"] != "?"}

    print("\n=== KONTROLA PROTI ASANE ===\n")

    for dom, m in MARKETS.items():
        claimed = m.get("mc_claimed")
        if not claimed:
            continue
        if claimed in found_ids:
            print(f"[OK]    {m['market']}: MC {claimed} existuje a vidime ho.")
        else:
            note = ""
            if claimed == m.get("ga4"):
                note = f"  <-- POZOR: rovnake cislo je v matici z 1.9. uvedene ako GA4 property {m['ga4']}"
            print(f"[SPORNE] {m['market']}: MC {claimed} z Asany sme nenasli.{note}")

    print()
    for dom, m in MARKETS.items():
        if m["market"] in found_markets:
            continue
        if m["merchant_expected"].startswith("ANO"):
            print(f"[ROZPOR] {m['market']} ({dom}): v tabulke MERCHANT=ANO, ale ucet sme nenasli.")
        else:
            print(f"[SEDI]   {m['market']} ({dom}): MERCHANT={m['merchant_expected']} — ucet nevidime, tabulka sedi.")

    unknown = [r for r in rows if r["trh"] == "?"]
    if unknown:
        print("\nUcty, ktore sa nepodarilo priradit k trhu (skontroluj domenu rucne):")
        for r in unknown:
            print(f"  - {r['mc_id']}  {r['nazov']}  {r['domena']}")


def main():
    p = argparse.ArgumentParser(description="Audit Merchant Center uctov cez Merchant API.")
    p.add_argument("--key", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
                   help="cesta k JSON klucu service accountu")
    p.add_argument("--advanced-account", help="ID advanced (multi-client) MC uctu; bez neho sa vypisu vsetky dostupne ucty")
    p.add_argument("--api-version", default="v1beta", help="verzia Merchant API (default v1beta)")
    p.add_argument("--csv", help="zapisat vystup do CSV")
    p.add_argument("--json", dest="json_out", help="zapisat vystup do JSON")
    args = p.parse_args()

    session = build_session(args.key)
    rows = collect(session, args.api_version, args.advanced_account)

    if not rows:
        print("Ziadne ucty. Overit, ci je service account pridany v Merchant Center "
              "(Settings -> Access and services) na advanced ucte.")
        return

    rows.sort(key=lambda r: (r["trh"] == "?", r["trh"]))
    print_table(rows)
    crosscheck(rows)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nCSV: {args.csv}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"JSON: {args.json_out}")


if __name__ == "__main__":
    main()
