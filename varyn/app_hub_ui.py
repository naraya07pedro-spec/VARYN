"""Clickable, visual application hub.

Telegram uses the preexisting official Bot API setup.
GitHub/Notion/Netlify/Supabase connect with user-supplied independent tokens
and a single official read-only account probe. Other catalog entries open
an actual documented setup path or disclose that no adapter exists.
"""
from __future__ import annotations

import queue
import sys
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from varyn.integration_catalog import load_catalog, CatalogRejected
from varyn.external_connect_ui import ExternalConnectMixin, EXTERNAL_APPS
from varyn.more_api_connections import (
    APPS as TOKEN_APPS, TOKEN_PAGES, HELP,
    MoreAPIError, probe_more_api, browse_more_api,
)
from varyn.app_api_connections import (
    AppConnectionError, CREDENTIAL_PAGES, guide_for,
    probe_connection, browse_resources,
)

BG = "#FAFAF7"
PAPER = "#FFFFFF"
INK = "#25313D"
SUB = "#67727E"
BLUE = "#3E5F71"
LINE = "#E4E7E4"

LOC = {
    "en": ("Connect", "View setup", "Connected", "Not connected",
           "Available to configure", "Not yet implemented",
           "Browse", "Disconnect", "Search apps", "More services",
           "A connected credential is needed for this action.",
           "This integration is not implemented. No account was accessed.",
           "Official guide", "Request connector"),
    "id": ("Hubungkan", "Panduan", "Terhubung", "Belum terhubung",
           "Bisa diatur", "Belum tersedia",
           "Jelajahi", "Putuskan", "Cari aplikasi", "Aplikasi lainnya",
           "Hubungkan akun terlebih dahulu.",
           "Integrasi ini belum dibuat. Tidak ada akun yang diakses.",
           "Panduan resmi", "Minta konektor"),
    "es": ("Conectar", "Ver guía", "Conectado", "Sin conexión",
           "Se puede configurar", "Todavía no disponible",
           "Explorar", "Desconectar", "Buscar aplicaciones", "Más servicios",
           "Conecta una cuenta primero.",
           "Esta integración no está implementada.",
           "Guía oficial", "Solicitar conector"),
    "fr": ("Connecter", "Voir le guide", "Connecté", "Non connecté",
           "Configuration possible", "Pas encore disponible",
           "Explorer", "Déconnecter", "Chercher des applications", "Autres services",
           "Connectez d'abord votre compte.",
           "Cette intégration n'est pas disponible.",
           "Guide officiel", "Demander le connecteur"),
}

FEATURED = (
    ("github", "GitHub", "#24292F", "GH", "Read account and repositories"),
    ("notion", "Notion", "#202020", "N", "Explore accessible pages"),
    ("netlify", "Netlify", "#007F83", "N", "Browse your sites, read-only"),
    ("supabase", "Supabase", "#3E8E61", "S", "Browse your projects, read-only"),
    ("telegram", "Telegram", "#229ED9", "✈", "Owner-only private bot"),
    ("whatsapp", "WhatsApp", "#25D366", "☎", "Official Meta setup required"),
)
BRAND_COLORS = {
    "github":"#24292F", "notion":"#202020", "telegram":"#229ED9",
    "whatsapp":"#25D366", "gmail":"#EA4335", "google-drive":"#4285F4",
    "google-calendar":"#4285F4", "slack":"#4A154B", "discord":"#5865F2",
    "supabase":"#3ECF8E", "netlify":"#007F83", "google-sheets":"#34A853",
    "google-docs":"#4285F4", "hubspot":"#FF7A59",
    "canva":"#00C4CC", "linkedin":"#0A66C2",
    "linear":"#5E6AD2", "dropbox":"#0061FF",
}


def badge(parent, title, color, symbol=None):
    """Compact stylized brand marks, locally drawn; no remote icon loading."""
    canvas = tk.Canvas(parent, width=43, height=43, highlightthickness=0,
                       bd=0, bg=PAPER)
    canvas.create_oval(3, 3, 40, 40, fill=color, outline="")
    if title.casefold() == "telegram":
        canvas.create_polygon(11, 22, 33, 12, 27, 34, 21, 27,
                              17, 29, 19, 24, fill="white", outline="")
    elif title.casefold() == "whatsapp":
        canvas.create_text(21,21,text="☎",fill="white",
                           font=("Segoe UI Symbol",17,"bold"))
    elif title.casefold() == "github":
        canvas.create_polygon(12,16,14,8,19,13,24,13,30,8,32,16,
                              fill="white",outline="")
        canvas.create_oval(13,15,30,32,fill="white",outline="")
        canvas.create_oval(17,20,19,22,fill=color,outline="")
        canvas.create_oval(25,20,27,22,fill=color,outline="")
    elif title.casefold() == "notion":
        canvas.create_rectangle(12,10,31,33,outline="white",width=2)
        canvas.create_text(21,21,text="N",fill="white",
                           font=("Georgia",16,"bold"))
    elif title.casefold() == "netlify":
        # Locally rendered brand-inspired mark; no remote logo calls.
        canvas.create_polygon(21,7,35,21,21,35,7,21,
                              fill="white",outline="")
        canvas.create_polygon(21,13,29,21,21,29,13,21,
                              fill=color,outline="")
    elif title.casefold() == "supabase":
        canvas.create_polygon(25,7,14,23,22,23,18,36,
                              32,17,23,17,fill="white",outline="")
    else:
        glyph = symbol or "".join(w[0] for w in title.split()[:2]).upper()[:2]
        canvas.create_text(21,21,text=glyph,fill="white",
                           font=("Segoe UI",12,"bold"))
    return canvas


class AppHubMixin(ExternalConnectMixin):
    def _loc(self, index):
        return LOC.get(self.language, LOC["en"])[index]

    def _brand_logo(self, parent, app_id, title, color, symbol=None):
        """Load ORIGINAL locally bundled raster brand artwork, not fake initials.

        Offline PNGs are generated from curated, license-documented SVGs.
        A neutral fallback is used only for services without licensed artwork.
        """
        key = app_id
        if key not in self._brand_images:
            root = Path(getattr(
                sys, "_MEIPASS", Path(__file__).resolve().parent.parent,
            ))
            img_path = root / "assets" / "brand_png" / (app_id + ".png")
            try:
                self._brand_images[key] = (
                    tk.PhotoImage(master=self, file=str(img_path))
                    if img_path.is_file() else None
                )
            except (tk.TclError, OSError):
                self._brand_images[key] = None
        asset = self._brand_images[key]
        if asset is not None:
            return tk.Label(
                parent, image=asset, bg=PAPER,
                borderwidth=0, width=48, height=48,
            )
        # Never pretend initials are an official logo.
        return badge(parent, title, color, symbol)

    def _build_app_hub(self, frame):
        self._app_credentials = {}
        self._brand_images = {}
        self._app_labels = {}
        self._app_buttons = {}
        self._app_status = {}
        self._app_rows = []
        self._app_queue = queue.Queue()
        self._app_poll = None
        self._app_busy = set()
        self._init_external()
        self.app_search = tk.StringVar(master=self)
        canvas = tk.Canvas(frame, bg=BG, borderwidth=0, highlightthickness=0)
        bar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        body = tk.Frame(canvas, bg=BG)
        inner_id = canvas.create_window((0,0),window=body,anchor="nw")
        body.bind("<Configure>", lambda _ev:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda ev:canvas.itemconfigure(inner_id,width=ev.width))
        def scroll(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(-int(event.delta/120), "units")
        canvas.bind("<Enter>",lambda _ev:canvas.bind_all("<MouseWheel>",scroll))
        canvas.bind("<Leave>",lambda _ev:canvas.unbind_all("<MouseWheel>"))

        heading = tk.Frame(body,bg=BG)
        heading.pack(fill="x",padx=25,pady=(13,16))
        tk.Label(heading,text="Apps",bg=BG,fg=INK,
                 font=("Segoe UI",24,"bold")).pack(anchor="w")
        tk.Label(heading,text="Pick an app. Connect supported services with "
                 "your own account, or open the official setup guide.",
                 bg=BG,fg=SUB,font=("Segoe UI",10)).pack(anchor="w",pady=(7,0))
        featured = tk.Frame(body,bg=BG)
        featured.pack(fill="x",padx=24)
        for col in range(2):
            featured.columnconfigure(col,weight=1,uniform="service")
        for i,(service,name,color,mark,note) in enumerate(FEATURED):
            card = tk.Frame(featured,bg=PAPER,highlightbackground=LINE,
                            highlightthickness=1)
            card.grid(row=i//2,column=i%2,sticky="nsew",padx=5,pady=6)
            item = tk.Frame(card,bg=PAPER)
            item.pack(fill="x",padx=15,pady=(15,11))
            self._brand_logo(item,service,name,color,mark).pack(side="left")
            heading_col=tk.Frame(item,bg=PAPER)
            heading_col.pack(side="left",fill="x",expand=True,padx=12)
            tk.Label(heading_col,text=name,bg=PAPER,fg=INK,
                     font=("Segoe UI",12,"bold")).pack(anchor="w")
            tk.Label(heading_col,text=note,bg=PAPER,fg=SUB,
                     font=("Segoe UI",9)).pack(anchor="w",pady=(4,0))
            state = tk.StringVar(master=self,value=self._loc(3))
            self._app_status[service]=state
            tk.Label(card,textvariable=state,bg=PAPER,fg=SUB,
                     font=("Segoe UI",9),anchor="w").pack(fill="x",padx=17)
            controls=tk.Frame(card,bg=PAPER)
            controls.pack(fill="x",padx=13,pady=(8,14))
            title=(self._loc(0) if service!="whatsapp" else self._loc(1))
            action=tk.Button(
                controls,text=title,cursor="hand2",bd=0,relief="flat",
                bg=BLUE,fg="white",padx=15,pady=7,
                font=("Segoe UI",10),
                command=lambda k=service:self._open_app(k),
            )
            action.pack(side="left")
            self._app_buttons[service]=action
            if service in ("github","notion","netlify","supabase"):
                tk.Button(
                    controls,text=self._loc(7),bd=0,relief="flat",
                    bg=PAPER,fg=SUB,cursor="hand2",padx=9,pady=7,
                    font=("Segoe UI",9),
                    command=lambda k=service:self._disconnect_app(k),
                ).pack(side="right")

        # Telegram Bot API fields exist, but are collapsed rather than
        # overwhelming nontechnical users above the app grid.
        self.telegram_section = tk.Frame(body,bg=BG)
        self._build_telegram(self.telegram_section)
        # Do not pack until Connect Telegram is clicked.
        tk.Label(body,text=self._loc(9),bg=BG,fg=INK,
                 font=("Segoe UI",16,"bold")).pack(anchor="w",padx=28,pady=(22,8))
        tk.Entry(body,textvariable=self.app_search,bg=PAPER,fg=INK,
                 font=("Segoe UI",11),relief="flat",bd=0,
                 highlightbackground=LINE,highlightthickness=1).pack(
                    fill="x",ipady=10,padx=28,pady=(0,12))
        self.app_search.trace_add("write",self._filter_app_rows)
        list_area=tk.Frame(body,bg=BG)
        list_area.pack(fill="x",padx=26,pady=(0,20))
        try:
            self._app_entries = load_catalog()
        except (CatalogRejected,OSError):
            self._app_entries=()
        # Real Connect/Browse controls are deliberately shown BEFORE the
        # catalog-only entries, not buried below a wall of guide buttons.
        connected_first = ("gmail","google_calendar","google_drive",
                           "hostinger_mail","slack","linear","hubspot",
                           "dropbox","discord")
        ordered_apps = sorted(
            self._app_entries,
            key=lambda item: (
                connected_first.index(item.id)
                if item.id in connected_first and item.kind=="connector"
                else 100,
                item.name.casefold(),
            ),
        )
        for entry in ordered_apps:
            # Only actual named app candidates belong in the Apps directory;
            # generic plugin/skill workflow labels do not imply an app login.
            if entry.kind != "connector":
                continue
            # Telegram/WhatsApp/GitHub/Notion are represented as first-class
            # featured service cards above, not duplicated in the catalog.
            if entry.id in ("github","notion","netlify","supabase","telegram","whatsapp"):
                continue
            card=tk.Frame(list_area,bg=PAPER,highlightbackground=LINE,
                          highlightthickness=1)
            card.pack(fill="x",pady=3)
            kind_color=BRAND_COLORS.get(entry.id, "#637887")
            self._brand_logo(
                card, entry.id, entry.name, kind_color,
            ).pack(side="left",padx=(13,8),pady=7)
            middle=tk.Frame(card,bg=PAPER)
            middle.pack(side="left",fill="x",expand=True,pady=8)
            tk.Label(middle,text=entry.name,bg=PAPER,fg=INK,
                     font=("Segoe UI",11,"bold")).pack(anchor="w")
            if entry.id in EXTERNAL_APPS or entry.id in TOKEN_APPS:
                message=tk.StringVar(master=self,value="Not connected")
                (self._external_status if entry.id in EXTERNAL_APPS
                 else self._app_status)[entry.id]=message
                tk.Label(middle,textvariable=message,bg=PAPER,fg=SUB,
                         font=("Segoe UI",9)).pack(anchor="w",pady=(3,0))
                action=(lambda k=entry.id:self._open_external(k)) if (
                    entry.id in EXTERNAL_APPS
                ) else (lambda k=entry.id:self._open_app(k))
                caption=self._loc(0)
            else:
                tk.Label(middle,text=self._loc(5),bg=PAPER,fg=SUB,
                         font=("Segoe UI",9)).pack(anchor="w",pady=(3,0))
                action=lambda k=entry.id,n=entry.name:self._explain_app(k,n)
                caption=self._loc(12) if guide_for(entry.id) else self._loc(13)
            if entry.id in EXTERNAL_APPS or entry.id in TOKEN_APPS:
                tk.Button(
                    card,text=self._loc(7),bg=PAPER,fg=SUB,bd=0,
                    relief="flat",padx=9,pady=8,cursor="hand2",
                    command=lambda k=entry.id:(
                        self._disconnect_external(k) if k in EXTERNAL_APPS
                        else self._disconnect_app(k)
                    ),
                ).pack(side="right")
            button=tk.Button(
                card,text=caption,bg=BLUE if entry.id in EXTERNAL_APPS or entry.id in TOKEN_APPS else BG,
                fg="white" if entry.id in EXTERNAL_APPS or entry.id in TOKEN_APPS else BLUE,
                bd=0,relief="flat",padx=14,pady=8,cursor="hand2",
                command=action,
            )
            button.pack(side="right",padx=12)
            if entry.id in EXTERNAL_APPS:
                self._external_buttons[entry.id]=button
            elif entry.id in TOKEN_APPS:
                self._app_buttons[entry.id]=button
            self._app_rows.append((entry,card,button))

        # Legacy compatibility for previous hosted tests; this metadata
        # view is intentionally NOT rendered as the user's main app list.
        self.app_tree=ttk.Treeview(
            body,columns=("kind","name","status"),show="headings",
        )
        for key,title in (("kind","TYPE"),("name","APPLICATION"),("status","STATUS")):
            self.app_tree.heading(key,text=title)
        self._refresh_apps()

    def _filter_app_rows(self,*_):
        q=self.app_search.get().strip().casefold()
        for entry,card,_ in self._app_rows:
            if not q or q in entry.name.casefold() or q in entry.kind.casefold():
                if not card.winfo_manager():
                    card.pack(fill="x",pady=3)
            else:
                card.pack_forget()

    def _open_app(self,service):
        if service=="telegram":
            if self.telegram_section.winfo_manager():
                self.telegram_section.pack_forget()
            else:
                # Place the expanded form between featured cards and list.
                self.telegram_section.pack(
                    fill="x",padx=26,pady=12,
                    after=self.telegram_section.master.winfo_children()[1],
                )
            return
        if service=="whatsapp":
            self._explain_app(service,"WhatsApp")
            return
        if service in self._app_credentials:
            self._browse_app(service)
        else:
            self._connect_app(service)

    def _explain_app(self,service,name):
        """A single click opens real documentation or a feature request.

        Never ask the owner to paste credentials into an unsupported adapter.
        This is setup HELP, not a connection or OAuth claim.
        """
        guide = guide_for(service)
        if guide:
            webbrowser.open(guide)
        else:
            from urllib.parse import quote
            query = quote("Connector request: " + name)
            webbrowser.open(
                "https://github.com/naraya07pedro-spec/VARYN/issues/new?title="
                + query
            )

    def _connect_app(self,service):
        if service not in ("github","notion","netlify","supabase",*TOKEN_APPS) or service in self._app_busy:
            return
        popup=tk.Toplevel(self)
        popup.title("VARYN | Connect "+(
            "Discord Bot" if service=="discord" else service.title()
        ))
        popup.geometry("535x330")
        popup.transient(self)
        popup.configure(bg=BG)
        popup.grab_set()
        tk.Label(popup,text="Connect "+service.title(),bg=BG,fg=INK,
                 font=("Segoe UI",18,"bold")).pack(anchor="w",padx=24,pady=(22,8))
        tk.Label(popup,text=(
                 HELP[service] if service in TOKEN_APPS
                 else "Paste a token issued by this service. "
                 "VARYN only makes read-only account and resource requests. "
                 "Prefer narrowly scoped credentials."
                 )+" Token stays in RAM, never saved. "
                 "Never paste it into ChatGPT or GitHub.",
                 bg=BG,fg=SUB,font=("Segoe UI",10),
                 wraplength=470,justify="left").pack(anchor="w",padx=24)
        token=tk.StringVar(master=popup)
        input_box=tk.Entry(popup,textvariable=token,show="●",bg=PAPER,
                           fg=INK,relief="flat",font=("Segoe UI",11),
                           highlightbackground=LINE,highlightthickness=1)
        input_box.pack(fill="x",padx=24,pady=(15,11),ipady=9)
        status=tk.StringVar(master=popup,value="")
        tk.Label(popup,textvariable=status,bg=BG,fg=SUB,
                 font=("Segoe UI",9)).pack(anchor="w",padx=24)
        actions=tk.Frame(popup,bg=BG)
        actions.pack(fill="x",padx=24,pady=10)
        tk.Button(
            actions,text="Create token",bg=PAPER,fg=INK,bd=0,
            padx=13,pady=8,cursor="hand2",
            command=lambda:webbrowser.open(
                TOKEN_PAGES[service] if service in TOKEN_APPS
                else CREDENTIAL_PAGES[service]
            ),
        ).pack(side="left")
        def begin():
            key=token.get().strip()
            if not 8<=len(key)<=1000:
                status.set("Paste the correct API token first.")
                return
            token.set("")
            action.configure(state="disabled")
            status.set("Checking this token with the official service…")
            self._app_busy.add(service)
            def work():
                try:
                    info=(probe_more_api(service,key) if service in TOKEN_APPS
                          else probe_connection(service,key))
                    self._app_queue.put((service,"ok",key,info))
                except AppConnectionError:
                    self._app_queue.put((service,"error",None,None))
                except Exception:
                    self._app_queue.put((service,"error",None,None))
            threading.Thread(target=work,daemon=True).start()
            self._pump_app_connections()
            popup.destroy()
        action=tk.Button(
            actions,text="Connect",command=begin,bg=BLUE,fg="white",
            padx=18,pady=8,bd=0,cursor="hand2",
        )
        action.pack(side="right")
        input_box.focus_set()

    def _pump_app_connections(self):
        if self.closed:
            return
        while True:
            try:
                service,state,key,info=self._app_queue.get_nowait()
            except queue.Empty:
                break
            self._app_busy.discard(service)
            if state=="ok":
                self._app_credentials[service]=key
                self._app_labels[service]=info["label"]
                self._app_status[service].set(
                    self._loc(2)+": "+info["label"]
                )
                self._app_buttons[service].configure(text=self._loc(6))
            else:
                self._app_status[service].set(
                    "Connection failed. Check token and permissions."
                )
        if self._app_busy:
            self.after(120,self._pump_app_connections)

    def _disconnect_app(self,service):
        self._app_credentials.pop(service,None)
        self._app_labels.pop(service,None)
        if service in self._app_status:
            self._app_status[service].set(self._loc(3))
            self._app_buttons[service].configure(text=self._loc(0))

    def _browse_app(self,service):
        key=self._app_credentials.get(service)
        if not key:
            return
        popup=tk.Toplevel(self)
        popup.title("VARYN | "+service.title()+" resources")
        popup.geometry("675x460")
        popup.transient(self)
        popup.configure(bg=BG)
        tk.Label(popup,text="Accessible "+service.title()+" resources",
                 bg=BG,fg=INK,
                 font=("Segoe UI",17,"bold")).pack(anchor="w",padx=21,pady=18)
        note=tk.StringVar(master=popup,value="Reading your authorized resources…")
        tk.Label(popup,textvariable=note,bg=BG,fg=SUB,
                 font=("Segoe UI",10)).pack(anchor="w",padx=21)
        listing=tk.Listbox(
            popup,bg=PAPER,fg=INK,font=("Segoe UI",11),
            exportselection=False,relief="flat",
        )
        listing.pack(fill="both",expand=True,padx=21,pady=13)
        result=queue.Queue()
        def work():
            try:
                result.put(browse_more_api(service,key) if service in TOKEN_APPS
                           else browse_resources(service,key))
            except (AppConnectionError,MoreAPIError,OSError):
                result.put(None)
            except Exception:
                result.put(None)
        threading.Thread(target=work,daemon=True).start()
        resources=[]
        def poll():
            if not popup.winfo_exists() or self.closed:
                return
            try:
                records=result.get_nowait()
            except queue.Empty:
                popup.after(110,poll)
                return
            if records is None:
                note.set("Could not list resources. Check token permissions.")
                return
            resources.extend(records)
            for name,_ in resources:
                listing.insert("end",name)
            note.set(str(len(resources))+" resources. Double-click to open in browser.")
        def open_selected(_e):
            idx=listing.curselection()
            if idx and idx[0]<len(resources):
                webbrowser.open(resources[idx[0]][1])
        listing.bind("<Double-Button-1>",open_selected)
        popup.after(110,poll)

    def _apply_app_language(self):
        for service,btn in getattr(self,"_app_buttons",{}).items():
            btn.configure(text=(
                self._loc(1) if service=="whatsapp" else
                self._loc(6) if service in self._app_credentials else self._loc(0)
            ))
        for service,var in getattr(self,"_app_status",{}).items():
            if service in self._app_labels:
                var.set(self._loc(2)+": "+self._app_labels[service])
            elif service != "telegram":
                var.set(self._loc(3))
        for entry,_,button in getattr(self,"_app_rows",[]):
            if entry.id in TOKEN_APPS:
                button.configure(text=(
                    self._loc(6) if entry.id in self._app_credentials
                    else self._loc(0)
                ))
            elif entry.id in EXTERNAL_APPS:
                active=("google" in self._external_sessions if
                        entry.id in ("gmail","google_calendar","google_drive")
                        else "hostinger_mail" in self._external_sessions)
                button.configure(text=self._loc(6) if active else self._loc(0))
            else:
                button.configure(text=(
                    self._loc(12) if guide_for(entry.id) else self._loc(13)
                ))

    def close(self):
        self._close_external()
        self._app_credentials.clear()
        self._app_labels.clear()
        super().close()
