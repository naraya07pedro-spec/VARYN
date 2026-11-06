"""User-initiated authenticated read-only app adapters: 2026-11 alpha.

Slack, Linear, HubSpot, Dropbox, and Discord BOT (not user self-bot).
All endpoints and methods are hardcoded, no redirects, no auto retries, no
provider response content ever forwarded to an LLM. Credentials stay in RAM.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

APPS = ("slack", "linear", "hubspot", "dropbox", "discord")
NAME = {
    "slack":"Slack", "linear":"Linear",
    "hubspot":"HubSpot", "dropbox":"Dropbox", "discord":"Discord Bot",
}
TOKEN_PAGES = {
    "slack":"https://api.slack.com/apps",
    "linear":"https://linear.app/settings/api",
    "hubspot":"https://app.hubspot.com/private-apps/",
    "dropbox":"https://www.dropbox.com/developers/apps",
    "discord":"https://discord.com/developers/applications",
}
HELP = {
    "slack":"Use a workspace OAuth token from an installed Slack app; add channels:read to browse public channels.",
    "linear":"Create a personal API key in Linear Settings > Security & access; restrict access where available.",
    "hubspot":"Use a HubSpot private app token with crm.objects.contacts.read scope to read contacts.",
    "dropbox":"Create a scoped Dropbox app and token with account_info.read and files.metadata.read.",
    "discord":"Discord BOT connection only: paste an official bot token, NEVER a user token or cookie; invite the bot to servers you control.",
}
_URLS = {
    "slack":(
        ("https://slack.com/api/auth.test", "POST", b""),
        ("https://slack.com/api/conversations.list?limit=20&types=public_channel", "GET", None),
    ),
    "linear":(
        ("https://api.linear.app/graphql", "POST", b'{"query":"query { viewer { id name } }"}'),
        ("https://api.linear.app/graphql", "POST", b'{"query":"query { issues(first:20) { nodes { identifier title url } } }"}'),
    ),
    "hubspot":(
        ("https://api.hubapi.com/crm/objects/2026-03/contacts?limit=1&properties=firstname,lastname,email", "GET", None),
        ("https://api.hubapi.com/crm/objects/2026-03/contacts?limit=20&properties=firstname,lastname,email", "GET", None),
    ),
    "dropbox":(
        ("https://api.dropboxapi.com/2/users/get_current_account", "POST", b"null"),
        ("https://api.dropboxapi.com/2/files/list_folder", "POST", b'{"path":"","recursive":false,"limit":20}'),
    ),
    "discord":(
        ("https://discord.com/api/v10/users/@me", "GET", None),
        ("https://discord.com/api/v10/users/@me/guilds", "GET", None),
    ),
}


class MoreAPIError(ValueError):
    pass


def _api(service, credential, *, list_mode=False, transport=None):
    if service not in APPS or type(credential) is not str or not 12 <= len(credential) <= 1024:
        raise MoreAPIError("Missing valid provider-issued credential")
    url, method, body = _URLS[service][1 if list_mode else 0]
    if transport is not None:
        raw = transport(service, list_mode, credential)
    else:
        headers = {"Accept":"application/json", "User-Agent":"VARYN/0.1 (owner local read only)"}
        if service=="discord":
            # Bot token, not a user self-bot token.
            headers["Authorization"]="Bot "+credential
        elif service=="linear":
            headers["Authorization"]=credential
        else:
            headers["Authorization"]="Bearer "+credential
        if body is not None:
            headers["Content-Type"]=(
                "application/x-www-form-urlencoded" if service=="slack"
                else "application/json"
            )
        req=urllib.request.Request(url,data=body,headers=headers,method=method)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                req,timeout=12,
            ) as response:
                raw=response.read(131073)
        except (urllib.error.HTTPError,urllib.error.URLError,OSError,TimeoutError):
            raise MoreAPIError("Provider refused connection or network failed") from None
    if type(raw) is not bytes or not 1 <= len(raw) <= 131072:
        raise MoreAPIError("Invalid provider response length")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeError,RecursionError):
        raise MoreAPIError("Malformed provider response") from None
    if service in ("slack","linear"):
        if type(data) is not dict:
            raise MoreAPIError("Provider returned invalid data")
        if service=="slack" and data.get("ok") is not True:
            raise MoreAPIError("Slack rejected credentials or permissions")
        if service=="linear" and (data.get("errors") or type(data.get("data")) is not dict):
            raise MoreAPIError("Linear rejected credentials or permissions")
    return data


def _title(value, *, fallback="Unnamed"):
    if type(value) is not str:
        return fallback
    cleaned=" ".join(value.split())
    return cleaned[:120] if cleaned else fallback


def _http_link(value, host):
    if type(value) is not str or len(value)>800:
        return None
    parsed=urlsplit(value)
    return value if (
        parsed.scheme=="https" and parsed.hostname==host and
        parsed.username is None and parsed.password is None and
        parsed.port is None
    ) else None


def probe_more_api(service, credential, *, transport=None):
    obj=_api(service,credential,transport=transport)
    if type(obj) is not dict:
        raise MoreAPIError("Unexpected account response")
    if service=="slack":
        if type(obj.get("team_id")) is not str or type(obj.get("user")) is not str:
            raise MoreAPIError("No Slack workspace identity")
        label="Slack: "+_title(obj.get("team"))
    elif service=="linear":
        viewer=obj["data"].get("viewer")
        if type(viewer) is not dict or type(viewer.get("id")) is not str:
            raise MoreAPIError("No Linear user identity")
        label="Linear: "+_title(viewer.get("name"))
    elif service=="hubspot":
        if type(obj.get("results")) is not list:
            raise MoreAPIError("HubSpot contacts scope not verified")
        label="HubSpot contacts API authorized"
    elif service=="dropbox":
        if type(obj.get("account_id")) is not str or type(obj.get("name")) is not dict:
            raise MoreAPIError("No Dropbox account identity")
        label="Dropbox: "+_title(obj["name"].get("display_name"))
    else:
        if obj.get("bot") is not True or type(obj.get("id")) is not str:
            raise MoreAPIError("Discord requires a BOT token; user tokens denied")
        label="Discord bot: "+_title(obj.get("username"))
    return {"app":service,"label":label[:150],"verified_read_only_probe":True}


def browse_more_api(service, credential, *, transport=None):
    obj=_api(service,credential,list_mode=True,transport=transport)
    if service=="slack":
        items=obj.get("channels") if type(obj) is dict else None
    elif service=="linear":
        issues=obj["data"].get("issues")
        items=issues.get("nodes") if type(issues) is dict else None
    elif service=="hubspot":
        items=obj.get("results") if type(obj) is dict else None
    elif service=="dropbox":
        items=obj.get("entries") if type(obj) is dict else None
    else:
        items=obj
    if type(items) is not list:
        raise MoreAPIError("Provider denied access to this resource list")
    result=[]
    for item in items[:20]:
        if type(item) is not dict:
            continue
        if service=="slack":
            name=_title(item.get("name"))
            link="https://app.slack.com/client/"
        elif service=="linear":
            name=_title(item.get("identifier"))+" · "+_title(item.get("title"))
            link=_http_link(item.get("url"),"linear.app") or "https://linear.app/"
        elif service=="hubspot":
            fields=item.get("properties")
            fields=fields if type(fields) is dict else {}
            name=_title(" ".join(str(fields.get(v) or "") for v in ("firstname","lastname")))
            if name=="Unnamed":
                name=_title(fields.get("email"),fallback="Contact")
            link="https://app.hubspot.com/"
        elif service=="dropbox":
            name=_title(item.get("name"))
            link="https://www.dropbox.com/home"
        else:
            guild_id=item.get("id")
            if type(guild_id) is not str or not re.fullmatch(r"[0-9]{10,25}",guild_id):
                continue
            name=_title(item.get("name"))
            link="https://discord.com/channels/"+guild_id
        result.append((name[:150],link))
    return tuple(result)
