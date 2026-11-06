"""Small official read-only connection probes for GitHub, Notion, Netlify and Supabase.

They establish a session-owned API credential ONLY after manual user action;
they do not inherit ChatGPT plugins, scan browsers or run autonomous actions.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

_PINNED = {
    "github": ("https://api.github.com/user", {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }),
    "notion": ("https://api.notion.com/v1/users/me", {
        "Accept": "application/json",
        "Notion-Version": "2025-09-03",
    }),
    "netlify": ("https://api.netlify.com/api/v1/sites?per_page=20", {
        "Accept": "application/json",
        "User-Agent": "VARYN (local owner-approved read-only client)",
    }),
    "supabase": ("https://api.supabase.com/v1/projects", {
        "Accept": "application/json",
    }),
}
CREDENTIAL_PAGES = {
    "github": "https://github.com/settings/personal-access-tokens",
    "notion": "https://www.notion.so/profile/integrations",
    "netlify": "https://app.netlify.com/user/applications#personal-access-tokens",
    "supabase": "https://supabase.com/dashboard/account/tokens",
}
_GUIDES = {
    "gmail": "https://developers.google.com/workspace/gmail/api/auth/about-auth",
    "google_calendar": "https://developers.google.com/workspace/calendar/api/auth",
    "google_drive": "https://developers.google.com/workspace/drive/api/guides/about-auth",
    "linkedin": "https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow",
    "canva": "https://www.canva.dev/docs/connect/",
    "descript": "https://www.descript.com/",
    "hostinger_mail": "https://www.hostinger.com/tutorials/how-to-set-up-hostinger-email",
    "automations": "https://help.openai.com/",
    "plugin_management": "https://help.openai.com/",
    "writing_style": "https://help.openai.com/",
    "google-drive": "https://developers.google.com/workspace/drive/api/guides/about-auth",
    "google-calendar": "https://developers.google.com/workspace/calendar/api/auth",
    "slack": "https://api.slack.com/apps",
    "discord": "https://discord.com/developers/applications",
    "whatsapp": "https://developers.facebook.com/docs/whatsapp/cloud-api/",
    "supabase": CREDENTIAL_PAGES["supabase"],
    "netlify": CREDENTIAL_PAGES["netlify"],
    "telegram": "https://core.telegram.org/bots/tutorial",
    "linear": "https://developers.linear.app/docs/graphql/working-with-the-graphql-api",
    "hubspot": "https://developers.hubspot.com/docs/api/private-apps",
    "dropbox": "https://www.dropbox.com/developers/apps",
    "spotify": "https://developer.spotify.com/dashboard",
    "github": CREDENTIAL_PAGES["github"],
    "notion": CREDENTIAL_PAGES["notion"],
    "netlify": CREDENTIAL_PAGES["netlify"],
}


class AppConnectionError(ValueError):
    pass


def guide_for(app_id):
    if type(app_id) is not str:
        return None
    return _GUIDES.get(app_id)


def probe_connection(app_id, token, *, transport=None):
    """One owner-initiated GET, with no token output and no automatic retry."""
    if app_id not in _PINNED or type(token) is not str or not 8 <= len(token) <= 1000:
        raise AppConnectionError("Unsupported service or missing key")
    endpoint, headers = _PINNED[app_id]
    if transport is not None:
        raw = transport(app_id, token)
    else:
        request = urllib.request.Request(
            endpoint,
            headers={**headers, "Authorization": "Bearer " + token},
            method="GET",
        )
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                request, timeout=12,
            ) as response:
                raw = response.read(65537)
        except (urllib.error.HTTPError, urllib.error.URLError,
                OSError, TimeoutError, ValueError):
            raise AppConnectionError("Authentication or network check failed") from None
    if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
        raise AppConnectionError("Provider returned invalid account information")
    try:
        account = json.loads(raw)
        if app_id in ("netlify", "supabase"):
            if type(account) is not list or len(account) > 10000:
                raise ValueError()
            if any(type(item) is not dict for item in account):
                raise ValueError()
            label = str(len(account)) + (" accessible sites" if app_id == "netlify"
                                         else " accessible projects")
        else:
            if type(account) is not dict:
                raise ValueError()
            if app_id == "github":
                label = account.get("login")
                if type(account.get("id")) is not int:
                    raise ValueError()
            else:
                label = account.get("name") or account.get("id")
                if account.get("object") != "user":
                    raise ValueError()
        if type(label) is not str or not re.fullmatch(r"[\w .@-]{1,80}", label):
            raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        raise AppConnectionError("Provider returned an unexpected account response") from None
    return {"app": app_id, "label": label, "verified_read_only_probe": True}


def browse_resources(app_id, token, *, transport=None):
    """Explicit owner-initiated, read-only listing of up to 20 resources."""
    if app_id not in _PINNED or type(token) is not str or not 8 <= len(token) <= 1000:
        raise AppConnectionError("Account not connected")
    if transport is not None:
        raw = transport(app_id, token)
    else:
        if app_id == "github":
            url = "https://api.github.com/user/repos?per_page=20&sort=updated"
            payload = None
        elif app_id == "notion":
            url = "https://api.notion.com/v1/search"
            payload = b'{"page_size":20}'
        else:
            url = _PINNED[app_id][0]
            payload = None
        headers = {**_PINNED[app_id][1], "Authorization":"Bearer " + token}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, headers=headers,
            method="POST" if payload is not None else "GET", data=payload,
        )
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                request, timeout=12,
            ) as response:
                raw = response.read(131073)
        except (urllib.error.HTTPError, urllib.error.URLError,
                TimeoutError, OSError, ValueError):
            raise AppConnectionError("Could not list authorized resources") from None
    if type(raw) is not bytes or not 1 <= len(raw) <= 131072:
        raise AppConnectionError("Invalid resource listing")
    try:
        data = json.loads(raw)
        if app_id == "notion":
            if type(data) is not dict or type(data.get("results")) is not list:
                raise ValueError()
            entries = data["results"]
        else:
            if type(data) is not list:
                raise ValueError()
            entries = data
        rows = []
        for item in entries[:20]:
            if type(item) is not dict:
                continue
            if app_id == "github":
                name, url = item.get("full_name"), item.get("html_url")
                allowed = ("https://github.com/",)
            elif app_id == "notion":
                name, url = item.get("id"), item.get("url")
                allowed = ("https://www.notion.so/", "https://notion.so/")
            elif app_id == "netlify":
                name, url = item.get("name"), item.get("admin_url")
                allowed = ("https://app.netlify.com/",)
            else:
                # Never build a URL from unvalidated source content.
                ref = item.get("ref")
                name = item.get("name")
                if type(ref) is not str or not re.fullmatch(r"[a-z0-9]{10,32}", ref):
                    continue
                url = "https://supabase.com/dashboard/project/" + ref
                allowed = ("https://supabase.com/dashboard/project/",)
            if type(name) is not str or not 1 <= len(name) <= 150:
                continue
            if type(url) is not str or not url.startswith(allowed):
                continue
            rows.append((name, url))
        return tuple(rows)
    except (ValueError, TypeError, UnicodeError):
        raise AppConnectionError("Invalid resource listing") from None
