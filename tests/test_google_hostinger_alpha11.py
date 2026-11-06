"""Network-free verification of actual Google/Hostinger connector protocols."""
from datetime import time as _time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
import json
import urllib.request
import unittest

from varyn.google_oauth import (
    GoogleConnectError, GoogleSession, read_desktop_client,
    build_authorization_url, authorize_google, list_google, refresh_google,
    AUTH_URL, TOKEN_URL, USER_URL, LIST_URLS,
)
from varyn.hostinger_imap import verify_mailbox, browse_mailbox, MailConnectError


CLIENT="123456789012-testabc.apps.googleusercontent.com"


class GoogleOAuthTests(unittest.TestCase):
    def test_desktop_client_only_and_no_secret_logging(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"client.json"
            payload={"installed":{"client_id":CLIENT,"client_secret":"sample",
                                  "auth_uri":AUTH_URL,"token_uri":TOKEN_URL}}
            path.write_text(json.dumps(payload),"utf-8")
            self.assertEqual(read_desktop_client(path)["client_id"],CLIENT)
            path.write_text(json.dumps({"web":payload["installed"]}),"utf-8")
            with self.assertRaises(GoogleConnectError):
                read_desktop_client(path)

    def test_pkce_state_scopes_and_single_browser_callback(self):
        url=build_authorization_url(
            CLIENT,"http://127.0.0.1:45678/oauth2callback",
            state="s"*40,verifier="v"*64,
        )
        query=parse_qs(urlsplit(url).query)
        self.assertEqual(query["code_challenge_method"],["S256"])
        self.assertIn("gmail.readonly",query["scope"][0])
        self.assertIn("drive.metadata.readonly",query["scope"][0])
        self.assertIn("calendar.calendarlist.readonly",query["scope"][0])
        captures=[]
        def transport(url,bearer,post):
            captures.append((url,bearer,post))
            if url==TOKEN_URL:
                return json.dumps({
                    "access_token":"access-token-123456",
                    "refresh_token":"refresh-token-123456",
                    "expires_in":3600,
                }).encode()
            self.assertEqual(url,USER_URL)
            self.assertEqual(bearer,"access-token-123456")
            return b'{"email":"owner@example.com"}'
        def browser(url):
            q=parse_qs(urlsplit(url).query)
            callback=q["redirect_uri"][0]+"?state="+q["state"][0]+(
                "&code=4/0A-test-code-12345678"
            )
            with urllib.request.urlopen(callback,timeout=3) as res:
                self.assertEqual(res.status,200)
            return True
        sess=authorize_google(
            {"client_id":CLIENT,"client_secret":"synthetic"},
            browser,timeout=3,transport=transport,
        )
        self.assertEqual(sess.email,"owner@example.com")
        self.assertEqual(len(captures),2)
        self.assertIn(b"code_verifier=",captures[0][2])

    def test_google_readonly_browse_formats_no_provider_reply_injection(self):
        session=GoogleSession(CLIENT,"","access-token-12345",
                              "refresh-token-123",99999999999,"owner@example.com")
        def api(url,bearer,post):
            self.assertEqual(bearer,session.access_token)
            if url==LIST_URLS["gmail"]:
                return b'{"messages":[{"id":"abcd12345"}]}'
            if "format=metadata" in url:
                return json.dumps({"payload":{"headers":[
                    {"name":"Subject","value":"Example Subject"},
                    {"name":"From","value":"Sender <mail@example.com>"},
                ]}}).encode()
            if url==LIST_URLS["google_calendar"]:
                return b'{"items":[{"summary":"Personal Calendar","id":"cal1"}]}'
            if url==LIST_URLS["google_drive"]:
                return json.dumps({"files":[
                    {"name":"Report","webViewLink":"https://docs.google.com/document/d/1"},
                    {"name":"Malicious","webViewLink":"https://evil.invalid/bad"},
                ]}).encode()
            raise AssertionError("Unexpected provider endpoint "+url)
        self.assertEqual(
            list_google("gmail",session,transport=api)[0][0].split("|")[0].strip(),
            "Example Subject",
        )
        self.assertEqual(
            list_google("google_calendar",session,transport=api)[0][0],
            "Personal Calendar",
        )
        rows=list_google("google_drive",session,transport=api)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1][1],"https://drive.google.com/drive/u/0/home")
        with self.assertRaises(GoogleConnectError):
            list_google("unsupported",session,transport=api)


class FakeIMAP:
    def __init__(self):
        self.readonly=[]
        self.fetch_calls=[]
        self.logged_out=False
    def login(self,email,password):
        return ("OK",[b"Logged in"])
    def select(self,mailbox,readonly=False):
        self.readonly.append(readonly)
        return ("OK",[b"4"])
    def uid(self,command,*arguments):
        if command=="search":
            return ("OK",[b"1 2 3"])
        if command=="fetch":
            self.fetch_calls.append((arguments,command))
            return ("OK",[(b"1",b"Subject: Testing Subject\r\nFrom: Person <p@example.com>\r\n\r\n")])
        raise AssertionError(command)
    def logout(self):
        self.logged_out=True


class HostingerTests(unittest.TestCase):
    def test_real_protocol_requires_tls_client_and_readonly_peek(self):
        created=[]
        def factory():
            conn=FakeIMAP()
            created.append(conn)
            return conn
        p=verify_mailbox("owner@example.com","sample-password",factory=factory)
        self.assertTrue(p["verified_read_only_probe"])
        rows=browse_mailbox("owner@example.com","sample-password",factory=factory)
        self.assertTrue(all(c.readonly==[True] for c in created))
        self.assertTrue(all(c.logged_out for c in created))
        self.assertEqual(len(rows),3)
        self.assertIn("Testing Subject",rows[0][0])
        self.assertEqual(rows[0][1],"https://mail.hostinger.com/")
        for conn in created:
            for args,_ in conn.fetch_calls:
                self.assertIn(b"BODY.PEEK",args[-1])

    def test_invalid_mailbox_rejected_before_contacting_provider(self):
        with self.assertRaises(MailConnectError):
            verify_mailbox("bad", "sample-password",
                           factory=lambda: (_ for _ in ()).throw(AssertionError()))


if __name__=="__main__":
    unittest.main()
