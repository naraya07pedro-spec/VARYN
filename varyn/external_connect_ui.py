"""Owner-controlled Google/Hostinger connection UX for VARYN Apps.

No inherited login or generic "guide" pretending to connect. Real network
operations happen only on user action and in a background thread.
"""
from __future__ import annotations

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

from varyn.google_oauth import (
    GoogleConnectError, read_desktop_client, authorize_google, list_google,
)
from varyn.hostinger_imap import (
    MailConnectError, verify_mailbox, browse_mailbox,
)

GOOGLE_APPS = ("gmail", "google_calendar", "google_drive")
EXTERNAL_APPS = GOOGLE_APPS + ("hostinger_mail",)
BG = "#FAFAF7"
PAPER = "#FFFFFF"
INK = "#25313D"
SUB = "#67727E"
BLUE = "#3E5F71"


class ExternalConnectMixin:
    def _init_external(self):
        self._external_sessions = {}
        self._external_status = {}
        self._external_buttons = {}
        self._external_queue = queue.Queue()
        self._external_busy = set()
        self._external_poll = None

    def _external_label(self, app):
        if app in GOOGLE_APPS:
            sess = self._external_sessions.get("google")
            if sess:
                return "Connected: " + sess.email + " · read-only"
        else:
            account = self._external_sessions.get("hostinger_mail")
            if account:
                return "Connected: " + account[0] + " · IMAP read-only"
        return "Not connected"

    def _external_refresh(self):
        for app, var in self._external_status.items():
            if app in self._external_busy:
                var.set("Waiting for authorization...")
            else:
                var.set(self._external_label(app))
            button = self._external_buttons.get(app)
            if button and button.winfo_exists():
                connected = (
                    "google" in self._external_sessions if app in GOOGLE_APPS
                    else "hostinger_mail" in self._external_sessions
                )
                button.configure(text="Browse" if connected else "Connect")

    def _open_external(self, service):
        if service in self._external_busy or self.closed:
            return
        if service in GOOGLE_APPS:
            if "google" in self._external_sessions:
                self._browse_external(service)
            else:
                self._connect_google(service)
        elif service == "hostinger_mail":
            if "hostinger_mail" in self._external_sessions:
                self._browse_external(service)
            else:
                self._connect_hostinger()

    def _connect_google(self, service):
        popup=tk.Toplevel(self)
        popup.title("VARYN | Connect Google")
        popup.configure(bg=BG)
        popup.geometry("580x355")
        popup.transient(self)
        popup.grab_set()
        tk.Label(
            popup, text="Connect Google apps", bg=BG, fg=INK,
            font=("Segoe UI",18,"bold"),
        ).pack(anchor="w",padx=23,pady=(22,10))
        tk.Label(
            popup, text=(
                "One Google login connects Gmail, Calendar and Drive for "
                "read-only browsing. Google requires a registered Desktop "
                "OAuth client. Select the JSON file downloaded from your "
                "own Google Cloud project. Never send it in chat.\n\n"
                "Enable Gmail, Calendar and Drive APIs in Google Cloud. "
                "In Testing mode, add your Google account as a test user. "
                "Google may require security verification for public access."
            ), bg=BG, fg=SUB, font=("Segoe UI",10),
            wraplength=525,justify="left",
        ).pack(anchor="w",padx=23)
        status=tk.StringVar(master=popup,value="Choose your Desktop OAuth client JSON.")
        tk.Label(popup,textvariable=status,bg=BG,fg=SUB,
                 font=("Segoe UI",10)).pack(anchor="w",padx=23,pady=(16,7))
        area=tk.Frame(popup,bg=BG)
        area.pack(fill="x",padx=23,pady=8)
        tk.Button(
            area,text="Google Cloud setup",bg=PAPER,fg=INK,bd=0,
            padx=12,pady=9,cursor="hand2",
            command=lambda:webbrowser.open(
                "https://console.cloud.google.com/apis/credentials"
            ),
        ).pack(side="left")
        def choose():
            path=filedialog.askopenfilename(
                parent=popup,title="Select Google OAuth Desktop client JSON",
                filetypes=[("Google OAuth Desktop JSON","*.json")],
            )
            if not path:
                return
            try:
                cfg=read_desktop_client(path)
            except (GoogleConnectError,OSError):
                status.set("Choose a valid Google OAuth Desktop JSON.")
                return
            popup.destroy()
            for app in GOOGLE_APPS:
                self._external_busy.add(app)
            self._external_refresh()
            def work():
                try:
                    session=authorize_google(cfg,webbrowser.open)
                    self._external_queue.put(("google",True,session))
                except (GoogleConnectError,OSError,ValueError):
                    self._external_queue.put(("google",False,None))
            threading.Thread(target=work,daemon=True).start()
            self._pump_external()
        tk.Button(
            area,text="Choose JSON and sign in",bg=BLUE,fg="white",bd=0,
            padx=15,pady=9,cursor="hand2",command=choose,
        ).pack(side="right")

    def _connect_hostinger(self):
        popup=tk.Toplevel(self)
        popup.title("VARYN | Hostinger Email")
        popup.configure(bg=BG)
        popup.geometry("510x310")
        popup.transient(self)
        popup.grab_set()
        tk.Label(
            popup,text="Connect Hostinger Email",
            bg=BG,fg=INK,font=("Segoe UI",18,"bold"),
        ).pack(anchor="w",padx=22,pady=(22,8))
        tk.Label(
            popup,text=("Use your existing Hostinger Email mailbox address "
                        "and password. Encrypted IMAP (993), read-only inbox. "
                        "Credentials stay in RAM and are forgotten on exit. "
                        "This is not a Hostinger account SSO connection."),
            bg=BG,fg=SUB,font=("Segoe UI",10),
            wraplength=462,justify="left",
        ).pack(anchor="w",padx=22)
        email=tk.StringVar(master=popup)
        password=tk.StringVar(master=popup)
        tk.Label(popup,text="Email address",bg=BG,fg=INK).pack(
            anchor="w",padx=22,pady=(10,0),
        )
        tk.Entry(popup,textvariable=email,bg=PAPER,fg=INK).pack(
            fill="x",padx=22,ipady=7,
        )
        tk.Label(popup,text="Mailbox password",bg=BG,fg=INK).pack(
            anchor="w",padx=22,pady=(6,0),
        )
        tk.Entry(popup,textvariable=password,show="●",bg=PAPER,fg=INK).pack(
            fill="x",padx=22,ipady=7,
        )
        def begin():
            user=email.get().strip()
            secret=password.get()
            password.set("")
            popup.destroy()
            self._external_busy.add("hostinger_mail")
            self._external_refresh()
            def work():
                try:
                    verify_mailbox(user,secret)
                    self._external_queue.put(
                        ("hostinger_mail",True,(user,secret)),
                    )
                except (MailConnectError,OSError,ValueError):
                    self._external_queue.put(("hostinger_mail",False,None))
            threading.Thread(target=work,daemon=True).start()
            self._pump_external()
        tk.Button(
            popup,text="Connect mailbox",bg=BLUE,fg="white",
            bd=0,padx=17,pady=9,command=begin,
        ).pack(anchor="e",padx=22,pady=12)

    def _pump_external(self):
        if self.closed:
            return
        while True:
            try:
                service,ok,value=self._external_queue.get_nowait()
            except queue.Empty:
                break
            affected=GOOGLE_APPS if service=="google" else ("hostinger_mail",)
            for app in affected:
                self._external_busy.discard(app)
            if ok:
                self._external_sessions[service]=value
                self._external_refresh()
            else:
                for app in affected:
                    var=self._external_status.get(app)
                    if var:
                        var.set(
                            "Connection failed or cancelled. Check access "
                            "and provider permissions."
                        )
                self._external_refresh()
                for app in affected:
                    self._external_status[app].set(
                        "Connection failed. Check credentials or permissions."
                    )
        if self._external_busy:
            self._external_poll=self.after(170,self._pump_external)
        else:
            self._external_poll=None

    def _disconnect_external(self,service):
        key="google" if service in GOOGLE_APPS else service
        if key=="google":
            session=self._external_sessions.pop("google",None)
            if session:
                session.clear()
        else:
            self._external_sessions.pop("hostinger_mail",None)
        self._external_refresh()

    def _browse_external(self,service):
        if service in GOOGLE_APPS:
            sess=self._external_sessions.get("google")
        else:
            sess=self._external_sessions.get("hostinger_mail")
        if not sess:
            return
        popup=tk.Toplevel(self)
        popup.title("VARYN | "+service.replace("_"," ").title())
        popup.geometry("700x480")
        popup.configure(bg=BG)
        popup.transient(self)
        tk.Label(
            popup,text="Read-only browsing",bg=BG,fg=INK,
            font=("Segoe UI",18,"bold"),
        ).pack(anchor="w",padx=22,pady=(20,8))
        status=tk.StringVar(master=popup,value="Loading from official service...")
        tk.Label(popup,textvariable=status,bg=BG,fg=SUB).pack(
            anchor="w",padx=22,
        )
        listing=tk.Listbox(
            popup,bg=PAPER,fg=INK,font=("Segoe UI",11),
            exportselection=False,relief="flat",
        )
        listing.pack(fill="both",expand=True,padx=22,pady=(12,20))
        output=queue.Queue()
        def work():
            try:
                rows=(list_google(service,sess)
                      if service in GOOGLE_APPS else
                      browse_mailbox(sess[0],sess[1]))
                output.put(rows)
            except (GoogleConnectError,MailConnectError,OSError,ValueError):
                output.put(None)
        threading.Thread(target=work,daemon=True).start()
        resources=[]
        def poll():
            if self.closed or not popup.winfo_exists():
                return
            try:
                rows=output.get_nowait()
            except queue.Empty:
                popup.after(140,poll)
                return
            if rows is None:
                status.set("Could not load. Check account permissions and enabled APIs.")
                return
            resources.extend(rows)
            for name,_url in resources:
                listing.insert("end",name)
            status.set(str(len(resources))+
                       " items · double-click to open the official app.")
        def open_item(_event):
            index=listing.curselection()
            if index and index[0]<len(resources):
                url=resources[index[0]][1]
                # URLs are pinned by the connector, not constructed from
                # arbitrary service-provided redirects.
                webbrowser.open(url)
        listing.bind("<Double-Button-1>",open_item)
        popup.after(140,poll)

    def _close_external(self):
        if self._external_poll is not None:
            try:
                self.after_cancel(self._external_poll)
            except tk.TclError:
                pass
            self._external_poll=None
        sess=self._external_sessions.pop("google",None)
        if sess:
            sess.clear()
        self._external_sessions.clear()
