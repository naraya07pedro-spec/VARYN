"""Explicit Google Desktop OAuth 2.0 PKCE connector for three VARYN services.

No Google identity is bundled or borrowed from ChatGPT. Owner supplies a
Desktop OAuth client JSON and approves read-only scopes in system browser.
This deliberately uses loopback 127.0.0.1, one-time state, exact fixed HTTPS
API endpoints, PKCE, no redirect following and bounded responses.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse
import urllib.error
import urllib.request

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = (
    "openid", "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
)
LIST_URLS = {
    "gmail": "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=12&labelIds=INBOX",
    "google_calendar": "https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=20",
    "google_drive": "https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(id%2Cname%2CmimeType%2CwebViewLink)%2CnextPageToken&q=trashed%3Dfalse",
}
CLIENT_ID = re.compile(r"\A[A-Za-z0-9_-]{8,160}\.apps\.googleusercontent\.com\Z")
EMAIL = re.compile(r"\A[^\s@<>]{1,80}@[^\s@<>]{1,100}\Z")


class GoogleConnectError(ValueError):
    pass


@dataclass
class GoogleSession:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: float
    email: str

    def clear(self):
        self.access_token = ""
        self.refresh_token = ""


def read_desktop_client(file_path):
    """User-selected Google OAuth Desktop JSON, never web client/service acct."""
    path = Path(file_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise GoogleConnectError("Choose a Google OAuth Desktop app JSON file")
    try:
        obj = json.loads(path.read_bytes())
        installed = obj["installed"]
        if type(installed) is not dict or not CLIENT_ID.fullmatch(installed["client_id"]):
            raise ValueError()
        if installed.get("auth_uri") not in (None, AUTH_URL,
                "https://accounts.google.com/o/oauth2/auth"):
            raise ValueError()
        if installed.get("token_uri") not in (None, TOKEN_URL):
            raise ValueError()
        secret = installed.get("client_secret", "")
        if type(secret) is not str or len(secret) > 256:
            raise ValueError()
        return {"client_id":installed["client_id"],"client_secret":secret}
    except (ValueError, KeyError, TypeError, UnicodeError, OSError):
        raise GoogleConnectError("Invalid OAuth Desktop client configuration") from None


def _http(url, *, bearer=None, post=None, timeout=15, transport=None):
    """Pinned Google HTTPS endpoints; never include tokens in URL or errors."""
    if not (url in (TOKEN_URL, USER_URL) or url in LIST_URLS.values() or
            (url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/")
             and re.fullmatch(
                r"[a-zA-Z0-9_-]{4,100}",
                url.split("/messages/", 1)[-1].split("?", 1)[0],
             ))):
        raise GoogleConnectError("Unrecognized Google endpoint")
    if transport is not None:
        raw = transport(url, bearer, post)
    else:
        headers={"Accept":"application/json"}
        if bearer is not None:
            headers["Authorization"]="Bearer "+bearer
        if post is not None:
            headers["Content-Type"]="application/x-www-form-urlencoded"
        request=urllib.request.Request(
            url, data=post, headers=headers,
            method="POST" if post is not None else "GET",
        )
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*_args,**_kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                request,timeout=timeout,
            ) as response:
                raw=response.read(131073)
        except (OSError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError):
            raise GoogleConnectError("Google authorization/API request failed") from None
    if type(raw) is not bytes or not 1<=len(raw)<=131072:
        raise GoogleConnectError("Invalid Google response size")
    try:
        obj=json.loads(raw)
    except (ValueError,UnicodeError,RecursionError):
        raise GoogleConnectError("Invalid Google JSON response") from None
    if type(obj) is not dict:
        raise GoogleConnectError("Unexpected Google response")
    return obj


def build_authorization_url(client_id, redirect, *, state, verifier):
    if not CLIENT_ID.fullmatch(client_id) or not redirect.startswith(
        "http://127.0.0.1:"
    ):
        raise GoogleConnectError("Untrusted desktop OAuth redirect")
    if not 40<=len(verifier)<=128 or not 30<=len(state)<=160:
        raise GoogleConnectError("Invalid OAuth challenge")
    challenge=base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest(),
    ).rstrip(b"=").decode("ascii")
    return AUTH_URL+"?"+urlencode({
        "client_id":client_id,"redirect_uri":redirect,
        "response_type":"code","scope":" ".join(SCOPES),
        "access_type":"offline","prompt":"consent",
        "state":state,"code_challenge":challenge,
        "code_challenge_method":"S256",
    })


def _exchange(config, code, redirect, verifier, *, transport=None):
    fields={
        "client_id":config["client_id"],
        "code":code,"redirect_uri":redirect,
        "grant_type":"authorization_code","code_verifier":verifier,
    }
    if config["client_secret"]:
        fields["client_secret"]=config["client_secret"]
    obj=_http(TOKEN_URL,post=urlencode(fields).encode("ascii"),transport=transport)
    token=obj.get("access_token")
    refresh=obj.get("refresh_token","")
    expires=obj.get("expires_in",3600)
    if (type(token) is not str or not 10<=len(token)<=4096 or
            type(refresh) is not str or len(refresh)>4096 or
            type(expires) not in (int,float) or not 60<=expires<=86400):
        raise GoogleConnectError("Invalid Google OAuth token response")
    granted=obj.get("scope")
    if type(granted) is str:
        requested=set(SCOPES)
        if not requested.issubset(set(granted.split())):
            raise GoogleConnectError("Required Google read-only scopes not approved")
    identity=_http(USER_URL,bearer=token,transport=transport)
    email=identity.get("email")
    if type(email) is not str or not EMAIL.fullmatch(email):
        raise GoogleConnectError("Could not verify Google account email")
    return GoogleSession(
        config["client_id"],config["client_secret"],
        token,refresh,time.time()+expires,email,
    )


def authorize_google(config, open_browser, *, timeout=180, transport=None):
    """Browser-owned login; only valid callback state yields authorization code."""
    if type(config) is not dict or not CLIENT_ID.fullmatch(
        config.get("client_id","")
    ) or type(config.get("client_secret")) is not str:
        raise GoogleConnectError("Invalid OAuth client")
    state=secrets.token_urlsafe(32)
    verifier=secrets.token_urlsafe(64)
    event=threading.Event()
    holder={}
    expected_host={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*_args):
            pass  # never log OAuth codes in callback URLs
        def do_GET(self):
            parsed=urlparse(self.path)
            values=parse_qs(parsed.query)
            if (parsed.path!="/oauth2callback" or
                self.headers.get("Host")!=expected_host["host"] or
                values.get("state")!=[state] or
                "error" in values or
                len(values.get("code",[]))!=1 or
                not re.fullmatch(r"[A-Za-z0-9_./-]{8,4096}",values["code"][0])):
                self.send_error(403,"Invalid OAuth callback")
                return
            if event.is_set():
                self.send_error(409,"Already processed")
                return
            holder["code"]=values["code"][0]
            event.set()
            body=b"<html><body>VARYN authorization received. You may close this tab.</body></html>"
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    try:
        server=ThreadingHTTPServer(("127.0.0.1",0),Callback)
    except OSError:
        raise GoogleConnectError("Cannot start local OAuth receiver") from None
    server.daemon_threads=True
    redirect="http://127.0.0.1:"+str(server.server_port)+"/oauth2callback"
    expected_host["host"]="127.0.0.1:"+str(server.server_port)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    try:
        thread.start()
        url=build_authorization_url(config["client_id"],redirect,
                                    state=state,verifier=verifier)
        if open_browser(url) is False:
            raise GoogleConnectError("Could not open default browser")
        if not event.wait(timeout):
            raise GoogleConnectError("Google login was not completed in time")
        return _exchange(config,holder["code"],redirect,verifier,transport=transport)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def refresh_google(session, *, transport=None):
    if type(session) is not GoogleSession or not session.refresh_token:
        raise GoogleConnectError("Google session expired; reconnect")
    if session.expires_at>time.time()+60:
        return session.access_token
    fields={"client_id":session.client_id,"refresh_token":session.refresh_token,
            "grant_type":"refresh_token"}
    if session.client_secret:
        fields["client_secret"]=session.client_secret
    obj=_http(TOKEN_URL,post=urlencode(fields).encode("ascii"),transport=transport)
    token=obj.get("access_token")
    ttl=obj.get("expires_in")
    if type(token) is not str or not 10<=len(token)<=4096 or (
        type(ttl) not in (int,float) or not 60<=ttl<=86400
    ):
        raise GoogleConnectError("Google token refresh failed")
    session.access_token=token
    session.expires_at=time.time()+ttl
    return token


def list_google(service, session, *, transport=None):
    """Owner-click read-only browse. Never sends content to a model."""
    if service not in LIST_URLS:
        raise GoogleConnectError("Unsupported Google service")
    token=refresh_google(session,transport=transport) if (
        session.expires_at<=time.time()+60
    ) else session.access_token
    if not token:
        raise GoogleConnectError("Google connection expired")
    obj=_http(LIST_URLS[service],bearer=token,transport=transport)
    if service=="gmail":
        # Message IDs deliberately do not get used as guessed web URLs.
        messages=obj.get("messages",[])
        if type(messages) is not list:
            raise GoogleConnectError("Invalid Gmail response")
        records=[]
        for item in messages[:8]:
            if type(item) is not dict:
                continue
            ident=item.get("id")
            if type(ident) is not str or not re.fullmatch(
                "[a-zA-Z0-9_-]{4,100}",ident
            ):
                continue
            meta=_http(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                +ident+"?format=metadata&metadataHeaders=Subject&metadataHeaders=From",
                bearer=token,transport=transport,
            )
            headers=meta.get("payload",{}).get("headers",[])
            if type(headers) is not list:
                headers=[]
            fields={
                field.get("name","").casefold():field.get("value","")
                for field in headers[:50] if type(field) is dict
                and type(field.get("name")) is str
                and type(field.get("value")) is str
            }
            subject=" ".join(fields.get("subject","(no subject)").split())[:110]
            sender=" ".join(fields.get("from","").split())[:80]
            records.append((subject+" | "+sender,
                            "https://mail.google.com/mail/u/0/#inbox"))
        return tuple(records)
    entries=obj.get("items" if service=="google_calendar" else "files",[])
    if type(entries) is not list:
        raise GoogleConnectError("Invalid Google resource response")
    result=[]
    for item in entries[:20]:
        if type(item) is not dict:
            continue
        title=item.get("summary" if service=="google_calendar" else "name")
        if type(title) is not str or not 1<=len(title)<=150:
            continue
        if service=="google_calendar":
            link="https://calendar.google.com/calendar/u/0/r"
        else:
            link=item.get("webViewLink")
            if type(link) is not str or not link.startswith(
                ("https://drive.google.com/","https://docs.google.com/")
            ):
                link="https://drive.google.com/drive/u/0/home"
        result.append((title,link))
    return tuple(result)
