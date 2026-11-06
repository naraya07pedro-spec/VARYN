"""Official Hostinger Email IMAP over validated TLS, owner-initiated only.

Only Hostinger Email accounts using imap.hostinger.com:993. Credential exists
in VARYN RAM for session, not in files, environment, GitHub or AI requests.
All browse operations use EXAMINE/readonly and BODY.PEEK headers; no send.
"""
from __future__ import annotations

from email import policy
from email.parser import BytesParser
import imaplib
import re
import ssl

from varyn.google_oauth import GoogleConnectError as MailConnectError

HOST = "imap.hostinger.com"
PORT = 993
EMAIL_RE = re.compile(r"\A[^\s@<>]{1,80}@[^\s@<>]{1,100}\Z")


def _open(email, password, *, factory=None):
    if (type(email) is not str or not EMAIL_RE.fullmatch(email) or
            type(password) is not str or not 8 <= len(password) <= 512):
        raise MailConnectError("Invalid mailbox credentials")
    try:
        if factory:
            conn=factory()
        else:
            conn=imaplib.IMAP4_SSL(
                HOST,PORT,ssl_context=ssl.create_default_context(),timeout=12,
            )
        status,_=conn.login(email,password)
        if status!="OK":
            raise MailConnectError("Mailbox login failed")
        return conn
    except (imaplib.IMAP4.error,imaplib.IMAP4.abort,
            OSError,TimeoutError,ssl.SSLError,ValueError):
        raise MailConnectError("Hostinger IMAP authentication failed") from None


def _close(conn):
    try:
        conn.logout()
    except (OSError,imaplib.IMAP4.error,imaplib.IMAP4.abort):
        pass


def verify_mailbox(email,password,*,factory=None):
    conn=_open(email,password,factory=factory)
    try:
        status,_=conn.select("INBOX",readonly=True)
        if status!="OK":
            raise MailConnectError("Mailbox is inaccessible")
        return {"app":"hostinger_mail","label":email,
                "verified_read_only_probe":True}
    except (imaplib.IMAP4.error,OSError,ValueError):
        raise MailConnectError("Could not inspect inbox") from None
    finally:
        _close(conn)


def browse_mailbox(email,password,*,factory=None):
    conn=_open(email,password,factory=factory)
    try:
        status,_=conn.select("INBOX",readonly=True)
        if status!="OK":
            raise MailConnectError("Mailbox is inaccessible")
        status,data=conn.uid("search",None,"ALL")
        if status!="OK" or not data or not isinstance(data[0],bytes):
            raise MailConnectError("Cannot list mailbox")
        uids=data[0].split()[-12:]
        result=[]
        for uid in reversed(uids):
            if not re.fullmatch(rb"[0-9]{1,20}",uid):
                continue
            status,parts=conn.uid(
                "fetch",uid,b"(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])",
            )
            if status!="OK" or type(parts) is not list:
                continue
            raw=next((t[1] for t in parts
                      if type(t) is tuple and type(t[1]) is bytes),b"")
            if not raw or len(raw)>8192:
                continue
            obj=BytesParser(policy=policy.default).parsebytes(raw,headersonly=True)
            subject=" ".join(str(obj.get("Subject","(no subject)")).split())[:130]
            sender=" ".join(str(obj.get("From","")).split())[:85]
            result.append((subject+"  |  "+sender,
                           "https://mail.hostinger.com/"))
        return tuple(result)
    except (imaplib.IMAP4.error,imaplib.IMAP4.abort,
            OSError,TimeoutError,ValueError):
        raise MailConnectError("Could not browse Hostinger inbox") from None
    finally:
        _close(conn)
