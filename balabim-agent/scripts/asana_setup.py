#!/usr/bin/env python3
"""Jednorazové nastavenie Asany pre PPC agenta.

Vytvorí (alebo použije existujúci) projekt, sekcie a custom fields a vypíše
JSON blok, ktorý sa vloží do config/settings.json pod kľúč "asana".

Použitie:
    export ASANA_TOKEN=...   # Personal Access Token
    python scripts/asana_setup.py --workspace 1200000000000000 --team 1200000000000001
    python scripts/asana_setup.py --workspace ... --project 1200000000000002   # existujúci projekt

Custom fields vyžadujú platený plán Asany (Starter a vyšší).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://app.asana.com/api/1.0"

ENUMS = {
    "country": ("Krajina", [
        ("SK", "SK", "blue"), ("CZ", "CZ", "blue"), ("HU", "HU", "blue"), ("PL", "PL", "blue"),
        ("RO", "RO", "blue"), ("BG", "BG", "blue"), ("HR", "HR", "blue"), ("SI", "SI", "blue"),
        ("GR", "GR", "blue"), ("ALL", "Všetky", "cool-gray"),
    ]),
    "platform": ("Platforma", [
        ("GOOGLE_ADS", "Google Ads", "yellow"), ("META", "Meta", "indigo"), ("BOTH", "Google + Meta", "purple"),
    ]),
    "type": ("Typ úlohy", [
        ("TRACKING", "Meranie", "red"), ("BUDGET", "Rozpočet", "orange"), ("PERFORMANCE", "Výkon", "yellow-orange"),
        ("WASTE", "Plytvanie", "yellow"), ("SCALE", "Škálovanie", "green"), ("CREATIVE", "Kreatívy", "aqua"),
        ("SEARCH_TERMS", "Search termy", "blue-green"), ("POLICY", "Zamietnutia", "magenta"),
        ("LEARNING", "Learning", "cool-gray"), ("DATA_QUALITY", "Kvalita dát", "cool-gray"),
    ]),
    "priority": ("Priorita", [("P1", "P1", "red"), ("P2", "P2", "orange"), ("P3", "P3", "yellow")]),
}
SECTIONS = ["Nové", "V riešení", "Hotovo"]


def call(method, path, token, data=None, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    body = json.dumps({"data": data}).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Asana {method} {path} zlyhalo ({e.code}): {e.read().decode(errors='replace')}")


def paged(path, token, params):
    params = dict(params, limit=100)
    while True:
        res = call("GET", path, token, params=params)
        yield from res.get("data", [])
        nxt = res.get("next_page")
        if not nxt:
            return
        params["offset"] = nxt["offset"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--team", help="tím pre nový projekt (povinné, ak nie je --project)")
    ap.add_argument("--project", help="GID existujúceho projektu")
    ap.add_argument("--name", default="Balabim – PPC optimalizácia")
    args = ap.parse_args()

    token = os.environ.get("ASANA_TOKEN")
    if not token:
        sys.exit("Nastav premennú prostredia ASANA_TOKEN.")

    if args.project:
        project_gid = args.project
    else:
        if not args.team:
            sys.exit("Pre nový projekt je potrebný --team.")
        project_gid = call("POST", "/projects", token, {
            "workspace": args.workspace, "team": args.team, "name": args.name, "default_view": "board",
        })["data"]["gid"]
        print(f"Vytvorený projekt {project_gid}", file=sys.stderr)

    existing_sections = {s["name"]: s["gid"] for s in paged(f"/projects/{project_gid}/sections", token, {})}
    for name in SECTIONS:
        if name not in existing_sections:
            existing_sections[name] = call("POST", f"/projects/{project_gid}/sections", token, {"name": name})["data"]["gid"]

    ws_fields = {f["name"]: f for f in paged(
        f"/workspaces/{args.workspace}/custom_fields", token,
        {"opt_fields": "name,resource_subtype,enum_options.name,enum_options.gid"})}
    on_project = {s["custom_field"]["gid"] for s in paged(
        f"/projects/{project_gid}/custom_field_settings", token, {"opt_fields": "custom_field.gid"})}

    def ensure(name, spec):
        field = ws_fields.get(name)
        if not field:
            field = call("POST", "/custom_fields", token, {"workspace": args.workspace, "name": name, **spec})["data"]
            print(f"Vytvorené pole {name}", file=sys.stderr)
        if field["gid"] not in on_project:
            call("POST", f"/projects/{project_gid}/addCustomFieldSetting", token,
                 {"custom_field": field["gid"], "is_important": True})
        return field

    fields = {}
    for key, (name, options) in ENUMS.items():
        field = ensure(name, {
            "resource_subtype": "enum",
            "enum_options": [{"name": label, "color": color} for _, label, color in options],
        })
        by_name = {o["name"]: o["gid"] for o in field.get("enum_options", [])}
        missing = [label for _, label, _ in options if label not in by_name]
        for label in missing:
            color = next(c for _, l, c in options if l == label)
            opt = call("POST", f"/custom_fields/{field['gid']}/enum_options", token, {"name": label, "color": color})["data"]
            by_name[label] = opt["gid"]
        fields[key] = {"gid": field["gid"], "options": {code: by_name[label] for code, label, _ in options}}

    fields["alert_id"] = {"gid": ensure("Alert-ID", {"resource_subtype": "text"})["gid"]}
    fields["impact"] = {"gid": ensure("Dopad (€)", {"resource_subtype": "number", "precision": 0})["gid"]}

    print(json.dumps({
        "workspace_gid": args.workspace,
        "project_gid": project_gid,
        "section_new_gid": existing_sections["Nové"],
        "default_assignee_gid": "",
        "due_days": {"P1": 1, "P2": 3, "P3": 7},
        "fields": fields,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
