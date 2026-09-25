#!/usr/bin/env python3
"""Build importable n8n workflow JSON files for the Balabim PPC agent.

Code nodes, SQL and prompts live in code/, sql/ and prompts/; this script inlines
them into n8n workflow exports and fills in values from a settings file.

    python build.py                                         # example settings -> n8n/ (committed)
    python build.py --settings config/settings.json --out dist   # real settings -> dist/ (git-ignored)
"""
import argparse
import copy
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = (ROOT / "code" / "_lib.js").read_text()
NS = uuid.UUID("6f1f7a52-6d0c-4b8e-9a53-1f0b5b0a1a11")

ASANA_API = "https://app.asana.com/api/1.0"
ASANA_TASK_FIELDS = ",".join([
    "name", "permalink_url", "custom_fields.gid", "custom_fields.text_value",
    "custom_fields.display_value", "custom_fields.enum_value.name",
])

CRED = {
    "gads": {"googleAdsOAuth2Api": {"id": "REPLACE_ME", "name": "Google Ads OAuth (MCC)"}},
    "meta": {"httpQueryAuth": {"id": "REPLACE_ME", "name": "Meta System User token"}},
    "google": {"googleApi": {"id": "REPLACE_ME", "name": "Google Service Account (BigQuery + Sheets)"}},
    "asana": {"asanaApi": {"id": "REPLACE_ME", "name": "Asana"}},
    "anthropic": {"httpHeaderAuth": {"id": "REPLACE_ME", "name": "Anthropic API key"}},
    "smtp": {"smtp": {"id": "REPLACE_ME", "name": "SMTP"}},
}


def read(rel):
    return (ROOT / rel).read_text()


class Workflow:
    def __init__(self, name, settings, error_workflow=True):
        self.name = name
        self.s = settings
        self.nodes = []
        self.connections = {}
        self.error_workflow = error_workflow

    # --- generic -------------------------------------------------------------
    def add(self, name, type_, version, params, pos, creds=None, **extra):
        node = {
            "parameters": params,
            "id": str(uuid.uuid5(NS, f"{self.name}/{name}")),
            "name": name,
            "type": type_,
            "typeVersion": version,
            "position": [pos[0] * 280, pos[1] * 200],
        }
        if creds:
            node["credentials"] = copy.deepcopy(CRED[creds])
        node.update(extra)
        self.nodes.append(node)
        return name

    def connect(self, src, dst, output=0):
        outs = self.connections.setdefault(src, {"main": []})["main"]
        while len(outs) <= output:
            outs.append([])
        outs[output].append({"node": dst, "type": "main", "index": 0})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.connect(a, b)

    def to_json(self):
        settings = {"executionOrder": "v1", "timezone": self.s["timezone"], "saveManualExecutions": True}
        if self.error_workflow and self.s["workflow_ids"]["error"] != "REPLACE_AFTER_IMPORT":
            settings["errorWorkflow"] = self.s["workflow_ids"]["error"]
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.connections,
            "settings": settings,
            "pinData": {},
            "meta": {"templateCredsSetupCompleted": False},
        }

    # --- node helpers --------------------------------------------------------
    def code(self, name, file, pos, config=None, **extra):
        body = read(f"code/{file}")
        if "__CONFIG__" in body:
            body = body.replace("__CONFIG__", json.dumps(config, ensure_ascii=False, indent=2))
        return self.add(name, "n8n-nodes-base.code", 2, {"jsCode": f"{LIB}\n// ---- {file} ----\n{body}"}, pos, **extra)

    def schedule(self, name, cron, pos):
        return self.add(name, "n8n-nodes-base.scheduleTrigger", 1.2,
                        {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}, pos)

    def sub_trigger(self, name, pos):
        return self.add(name, "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, pos)

    def run_workflow(self, name, workflow_id, pos):
        return self.add(name, "n8n-nodes-base.executeWorkflow", 1.2, {
            "workflowId": {"__rl": True, "value": workflow_id, "mode": "id"},
            "mode": "once",
            "options": {"waitForSubWorkflow": True},
        }, pos)

    def http(self, name, method, url, pos, auth, query=None, headers=None, body=None,
             pagination=None, timeout=60000, **extra):
        p = {"method": method, "url": url}
        if auth in ("gads", "asana"):
            p["authentication"] = "predefinedCredentialType"
            p["nodeCredentialType"] = next(iter(CRED[auth]))
        elif auth in ("meta", "anthropic"):
            p["authentication"] = "genericCredentialType"
            p["genericAuthType"] = next(iter(CRED[auth]))
        if query:
            p["sendQuery"] = True
            p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query.items()]}
        if headers:
            p["sendHeaders"] = True
            p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers.items()]}
        if body:
            p["sendBody"] = True
            p["specifyBody"] = "json"
            p["jsonBody"] = body
        options = {"timeout": timeout}
        if pagination:
            options["pagination"] = {"pagination": pagination}
        p["options"] = options
        extra.setdefault("retryOnFail", True)
        extra.setdefault("maxTries", 3)
        extra.setdefault("waitBetweenTries", 5000)
        return self.add(name, "n8n-nodes-base.httpRequest", 4.2, p, pos, creds=auth if auth else None, **extra)

    def bq_query(self, name, sql_file, pos, **extra):
        sql = read(f"sql/{sql_file}").replace("__DS__", f"{self.s['gcp_project']}.{self.s['bq_dataset']}")
        extra.setdefault("executeOnce", True)
        extra.setdefault("alwaysOutputData", True)
        return self.add(name, "n8n-nodes-base.googleBigQuery", 2.1, {
            "authentication": "serviceAccount",
            "operation": "executeQuery",
            "projectId": {"__rl": True, "value": self.s["gcp_project"], "mode": "id"},
            "sqlQuery": sql,
            "options": {"location": self.s["bq_location"]},
        }, pos, creds="google", **extra)

    def bq_insert(self, name, table, pos):
        return self.add(name, "n8n-nodes-base.googleBigQuery", 2.1, {
            "authentication": "serviceAccount",
            "operation": "insert",
            "projectId": {"__rl": True, "value": self.s["gcp_project"], "mode": "id"},
            "datasetId": {"__rl": True, "value": self.s["bq_dataset"], "mode": "id"},
            "tableId": {"__rl": True, "value": table, "mode": "id"},
            "dataMode": "autoMap",
            "options": {},
        }, pos, creds="google")

    def sheet(self, name, tab, pos, **extra):
        extra.setdefault("executeOnce", True)
        extra.setdefault("alwaysOutputData", True)
        return self.add(name, "n8n-nodes-base.googleSheets", 4.5, {
            "authentication": "serviceAccount",
            "operation": "read",
            "documentId": {"__rl": True, "value": self.s["config_sheet_id"], "mode": "id"},
            "sheetName": {"__rl": True, "value": tab, "mode": "name"},
            "options": {},
        }, pos, creds="google", **extra)

    def if_node(self, name, left, op, pos, right=None):
        operator = {"type": op[0], "operation": op[1]}
        if right is None:
            operator["singleValue"] = True
        return self.add(name, "n8n-nodes-base.if", 2, {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{
                    "id": str(uuid.uuid5(NS, f"{self.name}/{name}/cond")),
                    "leftValue": left,
                    "rightValue": right if right is not None else "",
                    "operator": operator,
                }],
                "combinator": "and",
            },
            "options": {},
        }, pos)

    def email(self, name, subject, text, pos, **extra):
        return self.add(name, "n8n-nodes-base.emailSend", 2.1, {
            "fromEmail": self.s["alert_email_from"],
            "toEmail": self.s["alert_email_to"],
            "subject": subject,
            "emailFormat": "text",
            "text": text,
            "options": {},
        }, pos, creds="smtp", **extra)

    def asana_open_tasks(self, name, pos):
        return self.http(
            name, "GET", f"={ASANA_API}/projects/{{{{ $('Config').first().json.asana.project_gid }}}}/tasks", pos, "asana",
            query={"completed_since": "now", "limit": "100", "opt_fields": ASANA_TASK_FIELDS},
            pagination={
                "paginationMode": "updateAParameterInEachRequest",
                "parameters": {"parameters": [
                    {"type": "qs", "name": "offset", "value": "={{ $response.body.next_page.offset }}"},
                ]},
                "paginationCompleteWhen": "other",
                "completeExpression": "={{ !$response.body.next_page }}",
                "limitPagesFetched": True,
                "maxRequests": 20,
            },
            executeOnce=True, alwaysOutputData=True,
        )

    def claude(self, name, pos):
        return self.http(
            name, "POST", "https://api.anthropic.com/v1/messages", pos, "anthropic",
            headers={
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "server-side-fallback-2026-07-01",
                "content-type": "application/json",
            },
            body="={{ JSON.stringify($json.body) }}",
            timeout=600000, maxTries=2, onError="continueRegularOutput",
        )


def public_settings(s, *drop):
    out = {k: v for k, v in s.items() if not k.startswith("_") and k not in drop}
    if "asana" in out:
        out["asana"] = {k: v for k, v in out["asana"].items() if not k.startswith("_")}
    return out


# --------------------------------------------------------------------------- WF1
def wf1(s):
    w = Workflow("Balabim PPC – WF1 Denný zber dát", s)
    cfg = public_settings(s)
    cfg["gaql"] = {
        "campaigns": read("sql/gaql_campaigns.sql"),
        "search_terms": read("sql/gaql_search_terms.sql"),
        "disapproved": read("sql/gaql_disapproved.sql"),
    }
    C = "$('Config').first().json"
    gads_url = (f"=https://googleads.googleapis.com/{{{{ {C}.gads_api_version }}}}/customers/"
                "{{ String($json.account_id).replace(/-/g, '') }}/googleAds:searchStream")
    gads_headers = {
        "developer-token": f"={{{{ {C}.gads_developer_token }}}}",
        "login-customer-id": f"={{{{ String({C}.gads_login_customer_id).replace(/-/g, '') }}}}",
    }
    meta_base = f"=https://graph.facebook.com/{{{{ {C}.meta_api_version }}}}/act_{{{{ String($json.account_id).replace(/^act_/, '') }}}}"
    meta_pages = {
        "paginationMode": "responseContainsNextURL",
        "nextURL": "={{ $response.body.paging.next }}",
        "paginationCompleteWhen": "other",
        "completeExpression": "={{ !$response.body.paging || !$response.body.paging.next }}",
        "limitPagesFetched": True,
        "maxRequests": 50,
    }

    w.schedule("Každý deň 06:00", "0 6 * * *", (0, 1))
    w.code("Config", "wf1_config.js", (1, 1), config=cfg)
    w.http("FX", "GET", f"=https://api.frankfurter.dev/v1/{{{{ $json.fx_from }}}}..{{{{ $json.until }}}}", (2, 1), None,
           query={"base": "EUR", "symbols": "CZK,HUF,PLN,RON"})
    w.sheet("Accounts", "accounts", (3, 1), alwaysOutputData=False)
    w.chain("Každý deň 06:00", "Config", "FX", "Accounts")

    w.code("Normalize FX", "wf1_norm_fx.js", (3, -1))
    w.bq_insert("BQ fx_rates", "fx_rates", (4, -1))
    w.chain("FX", "Normalize FX", "BQ fx_rates")

    # Google Ads
    w.code("Google Accounts", "wf1_filter_google.js", (4, 1))
    w.connect("Accounts", "Google Accounts")
    for row, (req, q, norm, table) in enumerate([
        ("GAds Campaigns", "gaql_campaigns", ("Normalize GAds Perf", "wf1_norm_gads_perf.js"), "daily_perf"),
        ("GAds Search Terms", "gaql_search_terms", ("Normalize GAds Search Terms", "wf1_norm_gads_st.js"), "search_terms"),
        ("GAds Disapproved Ads", "gaql_disapproved", ("Normalize GAds Issues", "wf1_norm_gads_issues.js"), "entity_issues"),
    ]):
        y = row
        w.http(req, "POST", gads_url, (5, y), "gads", headers=gads_headers,
               body=f"={{{{ JSON.stringify({{ query: {C}.{q} }}) }}}}", timeout=120000)
        w.code(norm[0], norm[1], (6, y))
        w.bq_insert(f"BQ {table} (Google)", table, (7, y))
        w.chain("Google Accounts", req, norm[0], f"BQ {table} (Google)")

    # Meta
    w.code("Meta Accounts", "wf1_filter_meta.js", (4, 4))
    w.connect("Accounts", "Meta Accounts")
    insight_fields = ("account_id,account_name,account_currency,campaign_id,campaign_name,adset_id,adset_name,"
                      "objective,spend,impressions,reach,inline_link_clicks,actions,action_values")
    w.http("Meta Insights Daily", "GET", f"{meta_base}/insights", (5, 3), "meta", query={
        "level": "adset", "time_increment": "1", "time_range": f"={{{{ {C}.meta_time_range }}}}",
        "fields": insight_fields, "limit": "500",
    }, pagination=meta_pages, timeout=120000)
    w.code("Normalize Meta Perf", "wf1_norm_meta_perf.js", (6, 3))
    w.bq_insert("BQ daily_perf (Meta)", "daily_perf", (7, 3))
    w.chain("Meta Accounts", "Meta Insights Daily", "Normalize Meta Perf", "BQ daily_perf (Meta)")

    w.http("Meta Insights 7d", "GET", f"{meta_base}/insights", (5, 4), "meta", query={
        "level": "adset", "time_range": f"={{{{ {C}.meta_time_range }}}}",
        "fields": "account_id,account_currency,campaign_id,campaign_name,adset_id,adset_name,spend,impressions,reach,frequency,inline_link_clicks",
        "limit": "500",
    }, pagination=meta_pages, timeout=120000)
    w.code("Normalize Meta Frequency", "wf1_norm_meta_freq.js", (6, 4))
    w.bq_insert("BQ meta_adset_7d", "meta_adset_7d", (7, 4))
    w.chain("Meta Accounts", "Meta Insights 7d", "Normalize Meta Frequency", "BQ meta_adset_7d")

    w.http("Meta Ad Sets", "GET", f"{meta_base}/adsets", (5, 5), "meta", query={
        "fields": "id,name,account_id,campaign_id,campaign{name},effective_status,learning_stage_info",
        "effective_status": '["ACTIVE"]', "limit": "500",
    }, pagination=meta_pages)
    w.http("Meta Ads With Issues", "GET", f"{meta_base}/ads", (5, 6), "meta", query={
        "fields": "id,name,account_id,adset_id,campaign_id,campaign{name},effective_status,issues_info",
        "effective_status": '["DISAPPROVED","WITH_ISSUES"]', "limit": "500",
    }, pagination=meta_pages)
    w.code("Normalize Meta Issues", "wf1_norm_meta_issues.js", (6, 5))
    w.bq_insert("BQ entity_issues (Meta)", "entity_issues", (7, 5))
    w.chain("Meta Accounts", "Meta Ad Sets", "Normalize Meta Issues", "BQ entity_issues (Meta)")
    w.chain("Meta Accounts", "Meta Ads With Issues", "Normalize Meta Issues")
    return w


# --------------------------------------------------------------------------- WF2
def wf2(s):
    w = Workflow("Balabim PPC – WF2 Pravidlá a detekcia", s)
    w.schedule("Každý deň 07:00", "0 7 * * *", (0, 0))
    w.code("Config", "config_basic.js", (1, 0), config=public_settings(s, "gads_developer_token"))
    w.sheet("Targets", "targets", (2, 0))
    w.bq_query("BQ Perf", "q_rules_perf.sql", (3, 0))
    w.bq_query("BQ Search Terms", "q_rules_search_terms.sql", (4, 0))
    w.bq_query("BQ Issues", "q_rules_issues.sql", (5, 0))
    w.bq_query("BQ Meta Freq", "q_rules_meta_freq.sql", (6, 0))
    w.code("Rules", "wf2_rules.js", (7, 0))
    w.code("Findings to BQ", "wf2_findings_to_bq.js", (8, -1))
    w.bq_insert("BQ findings", "findings", (9, -1))
    w.run_workflow("AI analytik (WF3)", s["workflow_ids"]["wf3_analyst"], (8, 1))
    w.chain("Každý deň 07:00", "Config", "Targets", "BQ Perf", "BQ Search Terms", "BQ Issues", "BQ Meta Freq", "Rules")
    w.chain("Rules", "Findings to BQ", "BQ findings")
    w.connect("Rules", "AI analytik (WF3)")
    return w


# --------------------------------------------------------------------------- WF3
def wf3(s):
    w = Workflow("Balabim PPC – WF3 AI analytik", s)
    cfg = public_settings(s, "gads_developer_token")
    cfg["analyst_system"] = read("prompts/analyst_system.md")
    cfg["analyst_schema"] = json.loads(read("prompts/analyst_output_schema.json"))
    w.sub_trigger("Findings In", (0, 0))
    w.code("Config", "config_basic.js", (1, 0), config=cfg)
    w.asana_open_tasks("Asana Open Tasks", (2, 0))
    w.bq_query("BQ Outcomes", "q_recent_outcomes.sql", (3, 0))
    w.code("Build Request", "wf3_build_request.js", (4, 0))
    w.if_node("Has New Findings?", "={{ $json.has_new }}", ("boolean", "true"), (5, 0))
    w.claude("Claude", (6, -1))
    w.code("Parse Tasks", "wf3_parse.js", (7, 0))
    w.run_workflow("Asana (WF4)", s["workflow_ids"]["wf4_asana"], (8, 0))
    w.chain("Findings In", "Config", "Asana Open Tasks", "BQ Outcomes", "Build Request", "Has New Findings?")
    w.connect("Has New Findings?", "Claude", 0)
    w.connect("Has New Findings?", "Parse Tasks", 1)
    w.chain("Claude", "Parse Tasks", "Asana (WF4)")
    return w


# --------------------------------------------------------------------------- WF4
def wf4(s):
    w = Workflow("Balabim PPC – WF4 Asana úlohy", s)
    w.sub_trigger("Tasks In", (0, 0))
    w.code("Config", "config_basic.js", (1, 0), config=public_settings(s, "gads_developer_token"))
    w.sheet("Targets", "targets", (2, 0))
    w.asana_open_tasks("Asana Open Tasks", (3, 0))
    w.code("Plan Actions", "wf4_plan.js", (4, 0))
    w.if_node("Is New Task?", "={{ $json.action }}", ("string", "equals"), (5, 0), right="create")
    w.http("Create Asana Task", "POST", f"{ASANA_API}/tasks", (6, -1), "asana",
           body="={{ JSON.stringify($json.asana_body) }}")
    w.code("Log Created Tasks", "wf4_log_tasks.js", (7, -1))
    w.bq_insert("BQ agent_tasks", "agent_tasks", (8, -1))
    w.http("Add Comment", "POST", f"={ASANA_API}/tasks/{{{{ $json.task_gid }}}}/stories", (6, 1), "asana",
           body="={{ JSON.stringify($json.asana_body) }}", onError="continueRegularOutput")
    w.code("P1 Digest", "wf4_p1_digest.js", (5, 2))
    w.email("Send P1 Alert", "={{ $json.subject }}", "={{ $json.text }}", (6, 2))
    w.chain("Tasks In", "Config", "Targets", "Asana Open Tasks", "Plan Actions", "Is New Task?")
    w.connect("Is New Task?", "Create Asana Task", 0)
    w.connect("Is New Task?", "Add Comment", 1)
    w.chain("Create Asana Task", "Log Created Tasks", "BQ agent_tasks")
    w.chain("Plan Actions", "P1 Digest", "Send P1 Alert")
    return w


# --------------------------------------------------------------------------- WF5
def wf5(s):
    w = Workflow("Balabim PPC – WF5 Spätná väzba (Asana webhook)", s)
    w.add("Asana Trigger", "n8n-nodes-base.asanaTrigger", 1, {
        "authentication": "accessToken",
        "resource": s["asana"]["project_gid"],
        "workspace": s["asana"]["workspace_gid"],
    }, (0, 0), creds="asana", webhookId=str(uuid.uuid5(NS, "wf5-asana-webhook")))
    w.code("Completed Events", "wf5_filter_events.js", (1, 0))
    w.http("Get Task", "GET", f"={ASANA_API}/tasks/{{{{ $json.task_gid }}}}", (2, 0), "asana",
           query={"opt_fields": "name,completed,completed_at,completed_by.name"})
    w.code("To actions_log", "wf5_to_actions_log.js", (3, 0))
    w.bq_insert("BQ actions_log", "actions_log", (4, 0))
    w.chain("Asana Trigger", "Completed Events", "Get Task", "To actions_log", "BQ actions_log")
    return w


def wf5b(s):
    w = Workflow("Balabim PPC – WF5b Vyhodnotenie dopadu", s)
    w.schedule("Každý deň 07:30", "30 7 * * *", (0, 0))
    w.code("Config", "config_basic.js", (1, 0), config=public_settings(s, "gads_developer_token"))
    w.bq_query("BQ Impact", "q_impact_eval.sql", (2, 0), alwaysOutputData=False)
    w.code("Format Outcome", "wf5b_format.js", (3, 0))
    w.http("Comment Outcome", "POST", f"={ASANA_API}/tasks/{{{{ $json.task_gid }}}}/stories", (4, 0), "asana",
           body="={{ JSON.stringify({ data: { text: $json.comment_text } }) }}", onError="continueRegularOutput")
    w.code("To Outcomes", "wf5b_to_outcomes.js", (5, 0))
    w.bq_insert("BQ action_outcomes", "action_outcomes", (6, 0))
    w.chain("Každý deň 07:30", "Config", "BQ Impact", "Format Outcome", "Comment Outcome", "To Outcomes", "BQ action_outcomes")
    return w


# --------------------------------------------------------------------------- WF6
def wf6(s):
    w = Workflow("Balabim PPC – WF6 Týždenný report", s)
    cfg = public_settings(s, "gads_developer_token")
    cfg["weekly_system"] = read("prompts/weekly_system.md")
    w.schedule("Pondelok 08:00", "0 8 * * 1", (0, 0))
    w.code("Config", "config_basic.js", (1, 0), config=cfg)
    w.bq_query("BQ Weekly", "q_weekly.sql", (2, 0))
    w.bq_query("BQ MTD", "q_weekly_mtd.sql", (3, 0))
    w.sheet("Targets", "targets", (4, 0))
    w.asana_open_tasks("Asana Open Tasks", (5, 0))
    w.code("Build Weekly", "wf6_build.js", (6, 0))
    w.claude("Claude", (7, 0))
    w.code("Compose Status", "wf6_compose.js", (8, 0))
    w.http("Post Status Update", "POST", f"{ASANA_API}/status_updates", (9, 0), "asana",
           body="={{ JSON.stringify($json.status_body) }}")
    w.email("Email Weekly", "={{ $('Compose Status').first().json.email_subject }}",
            "={{ $('Compose Status').first().json.email_text }}", (10, 0), disabled=True)
    w.chain("Pondelok 08:00", "Config", "BQ Weekly", "BQ MTD", "Targets", "Asana Open Tasks",
            "Build Weekly", "Claude", "Compose Status", "Post Status Update", "Email Weekly")
    return w


# --------------------------------------------------------------------------- errors
def wf_error(s):
    w = Workflow("Balabim PPC – Error handler", s, error_workflow=False)
    w.add("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, (0, 0))
    w.code("Format Error", "wf_error.js", (1, 0))
    w.email("Send Error Alert", "={{ $json.subject }}", "={{ $json.text }}", (2, 0))
    w.chain("Error Trigger", "Format Error", "Send Error Alert")
    return w


WORKFLOWS = {
    "WF1_ingest.json": wf1,
    "WF2_rules.json": wf2,
    "WF3_ai_analyst.json": wf3,
    "WF4_asana.json": wf4,
    "WF5_feedback_webhook.json": wf5,
    "WF5b_impact_eval.json": wf5b,
    "WF6_weekly_report.json": wf6,
    "WF_error.json": wf_error,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--settings", default=str(ROOT / "config" / "settings.example.json"))
    ap.add_argument("--out", default=str(ROOT / "n8n"))
    args = ap.parse_args()

    settings = json.loads(Path(args.settings).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for filename, factory in WORKFLOWS.items():
        wf = factory(settings).to_json()
        (out / filename).write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n")
        print(f"{out / filename}  ({len(wf['nodes'])} nodov)")

    schema = read("sql/schema.sql").replace("__DS__", f"{settings['gcp_project']}.{settings['bq_dataset']}")
    (out / "schema.sql").write_text(schema)
    print(f"{out / 'schema.sql'}")


if __name__ == "__main__":
    main()
