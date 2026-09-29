# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.0,<2", "google-auth>=2.0", "requests"]
# ///
"""Read-only Google Tag Manager MCP server (stdio) over the Tag Manager API v2.

Credentials: service account JSON in GOOGLE_APPLICATION_CREDENTIALS (set by
.claude/gtm-mcp.sh). The service account must be added as a user (Read) in the
GTM account/container, and the Tag Manager API must be enabled in its GCP project.
"""
import json
import os

import google.auth
from google.auth.transport.requests import AuthorizedSession
from mcp.server.fastmcp import FastMCP

API = "https://tagmanager.googleapis.com/tagmanager/v2"
SCOPES = ["https://www.googleapis.com/auth/tagmanager.readonly"]

mcp = FastMCP("gtm")
_session = None


def _get(path, **params):
    global _session
    if _session is None:
        creds, _ = google.auth.default(scopes=SCOPES)
        _session = AuthorizedSession(creds)
    path = path.lstrip("/")
    url = path if path.startswith("http") else f"{API}/{path}"
    items, token = None, None
    while True:
        q = dict(params)
        if token:
            q["pageToken"] = token
        r = _session.get(url, params=q)
        if r.status_code >= 400:
            raise RuntimeError(f"GTM API {r.status_code}: {r.text[:500]}")
        data = r.json()
        token = data.pop("nextPageToken", None)
        if items is None:
            items = data
        else:
            for k, v in data.items():
                if isinstance(v, list):
                    items.setdefault(k, []).extend(v)
        if not token:
            return items


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _brief(entities, *fields):
    return [{f: e.get(f) for f in fields if f in e} for e in entities]


@mcp.tool()
def list_accounts() -> str:
    """List GTM accounts the service account can read."""
    return _dump(_brief(_get("accounts").get("account", []), "path", "accountId", "name"))


@mcp.tool()
def list_containers(account_id: str) -> str:
    """List containers in a GTM account."""
    data = _get(f"accounts/{account_id}/containers")
    return _dump(_brief(data.get("container", []), "path", "containerId", "publicId", "name", "usageContext"))


@mcp.tool()
def find_container(public_id: str) -> str:
    """Find a container by its public ID (e.g. GTM-XXXXXXX) across all readable accounts."""
    for acc in _get("accounts").get("account", []):
        for c in _get(f"{acc['path']}/containers").get("container", []):
            if c.get("publicId", "").upper() == public_id.upper():
                return _dump({"account": acc.get("name"), **c})
    return f"Container {public_id} not found (is the service account added to it?)"


@mcp.tool()
def list_workspaces(container_path: str) -> str:
    """List workspaces of a container. container_path: accounts/{a}/containers/{c}."""
    data = _get(f"{container_path}/workspaces")
    return _dump(_brief(data.get("workspace", []), "path", "workspaceId", "name", "description"))


@mcp.tool()
def workspace_status(workspace_path: str) -> str:
    """Unpublished changes (added/updated/deleted entities) and merge conflicts of a workspace.
    workspace_path: accounts/{a}/containers/{c}/workspaces/{w}."""
    data = _get(f"{workspace_path}/status")
    changes = []
    for ch in data.get("workspaceChange", []):
        kind = next((k for k in ch if k != "changeStatus"), None)
        ent = ch.get(kind, {}) if kind else {}
        changes.append({"status": ch.get("changeStatus"), "type": kind, "name": ent.get("name"), "path": ent.get("path")})
    return _dump({"changes": changes, "mergeConflict": data.get("mergeConflict", [])})


@mcp.tool()
def list_entities(workspace_path: str, entity: str, full: bool = False) -> str:
    """List entities in a workspace. entity: tags | triggers | variables | built_in_variables |
    folders | templates | clients | transformations | zones. full=True returns complete definitions."""
    name = {"built_in_variables": "built_in_variables"}.get(entity, entity)
    data = _get(f"{workspace_path}/{name}")
    key = next((k for k, v in data.items() if isinstance(v, list)), None)
    items = data.get(key, []) if key else []
    if full:
        return _dump(items)
    return _dump(_brief(items, "path", "name", "type", "firingTriggerId", "blockingTriggerId", "parentFolderId"))


@mcp.tool()
def get_entity(path: str) -> str:
    """Get any GTM API resource by path, e.g. accounts/1/containers/2/workspaces/3/tags/4."""
    return _dump(_get(path))


@mcp.tool()
def live_version(container_path: str, full: bool = False) -> str:
    """Currently published container version. full=True returns tags/triggers/variables in full."""
    v = _get(f"{container_path}/versions:live")
    if full:
        return _dump(v)
    return _dump({
        "containerVersionId": v.get("containerVersionId"),
        "name": v.get("name"),
        "description": v.get("description"),
        "fingerprint": v.get("fingerprint"),
        "tags": _brief(v.get("tag", []), "tagId", "name", "type", "firingTriggerId", "blockingTriggerId"),
        "triggers": _brief(v.get("trigger", []), "triggerId", "name", "type"),
        "variables": _brief(v.get("variable", []), "variableId", "name", "type"),
    })


@mcp.tool()
def list_versions(container_path: str) -> str:
    """Container version headers (id, name, deleted, counts)."""
    data = _get(f"{container_path}/version_headers")
    return _dump(data.get("containerVersionHeader", []))


if __name__ == "__main__":
    mcp.run()
