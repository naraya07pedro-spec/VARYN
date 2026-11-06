"""Reference-aligned, premium VARYN desktop shell.

The chosen UI is a calm personal workspace, not a developer console.
Model approvals and local task behavior remain the existing implementations.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from varyn.owner_home import OwnerHome
from varyn.integration_catalog import load_catalog, CatalogRejected
from varyn.premium_chat import PremiumChatSurface


SIDE = "#101528"
BASE = "#171c34"
CARD = "#252a46"
FG = "#fbf9ff"
MUTED = "#b6b9cd"
PURPLE = "#7860c9"
LINE = "#3b3b58"


def write(parent, text, *, size=11, color=FG, bold=False, bg=BASE):
    return tk.Label(
        parent, text=text, fg=color, bg=bg,
        anchor="w", justify="left",
        font=("Segoe UI", size, "bold" if bold else "normal"),
    )


def button(parent, text, command, *, accent=False):
    return tk.Button(
        parent, text=text, command=command, cursor="hand2",
        bg=PURPLE if accent else CARD, fg=FG,
        activebackground="#9281d7" if accent else "#343856",
        activeforeground=FG,
        relief="flat", bd=0, padx=15, pady=9,
        font=("Segoe UI", 10, "bold" if accent else "normal"),
    )


class PremiumOwnerHome(OwnerHome):
    """Familiar consumer navigation with actual working task and chat controls."""

    def _build(self):
        self.title("VARYN | Personal Workspace")
        self.geometry("1120x735")
        self.minsize(865, 575)
        self.configure(bg=BASE)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Premium.Treeview", background=CARD, foreground=FG,
            fieldbackground=CARD, rowheight=36, borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Premium.Treeview.Heading", background=SIDE, foreground=MUTED,
            font=("Segoe UI", 9, "bold"), borderwidth=0,
        )
        style.map("Premium.Treeview", background=[("selected", "#494677")])
        self._panels = {}
        self._nav = {}
        shell = tk.Frame(self, bg=BASE)
        shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(shell, bg=SIDE, width=233)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        branding = tk.Frame(self.sidebar, bg=SIDE)
        branding.pack(fill="x", padx=24, pady=(29, 34))
        write(branding, "✦", size=22, color="#aa7cff",
              bold=True, bg=SIDE).pack(side="left")
        write(branding, "  VARYN", size=17, bold=True,
              bg=SIDE).pack(side="left")

        for key, icon, title in (
            ("chat", "▢", "Chat"),
            ("tasks", "☑", "Tugas"),
            ("connectors", "▦", "Aplikasi"),
            ("history", "◷", "Riwayat"),
        ):
            control = tk.Button(
                self.sidebar, text="  "+icon+"     "+title,
                command=lambda k=key: self._show(k),
                bg=SIDE, fg=MUTED, activebackground="#292845",
                activeforeground=FG, relief="flat", bd=0,
                font=("Segoe UI", 11), anchor="w", padx=16,
                pady=13, cursor="hand2",
            )
            control.pack(fill="x", padx=12, pady=3)
            self._nav[key] = control

        tk.Frame(self.sidebar, bg=SIDE).pack(fill="both", expand=True)
        settings = tk.Button(
            self.sidebar, text="  ⚙     Pengaturan",
            command=self._settings,
            bg=SIDE, fg=MUTED, activebackground="#292845",
            activeforeground=FG, relief="flat", bd=0,
            font=("Segoe UI", 11), anchor="w", padx=16,
            pady=13, cursor="hand2",
        )
        settings.pack(fill="x", padx=12, pady=(0, 26))
        profile = tk.Frame(self.sidebar, bg=SIDE)
        profile.pack(fill="x", padx=20, pady=(0, 30))
        avatar = tk.Canvas(profile, width=38, height=38,
                           bg=SIDE, highlightthickness=0)
        avatar.pack(side="left")
        avatar.create_oval(2, 2, 36, 36, fill="#866be3", outline="")
        avatar.create_text(19, 19, text="E", fill="white",
                           font=("Segoe UI", 13, "bold"))
        identity = tk.Frame(profile, bg=SIDE)
        identity.pack(side="left", padx=9)
        write(identity, "Evan", size=10, bold=True, bg=SIDE).pack(anchor="w")
        write(identity, "Personal", size=9, color=MUTED, bg=SIDE).pack(anchor="w")

        area = tk.Frame(shell, bg=BASE)
        area.pack(side="left", fill="both", expand=True)
        holder = tk.Frame(area, bg=BASE)
        holder.pack(fill="both", expand=True, padx=16, pady=(16, 18))
        for key in ("chat", "tasks", "connectors", "history"):
            self._panels[key] = tk.Frame(holder, bg=BASE)
        self._build_chat(self._panels["chat"])
        self._build_tasks(self._panels["tasks"])
        self._build_connectors(self._panels["connectors"])
        self._build_history(self._panels["history"])
        self._show("chat")

    def _show(self, page):
        if self.closed:
            return
        if page == "history":
            self._refresh_history()
        for key, frame in self._panels.items():
            frame.pack_forget()
            self._nav[key].configure(
                bg="#292542" if key == page else SIDE,
                fg=FG if key == page else MUTED,
            )
        self._panels[page].pack(fill="both", expand=True)
        if page == "chat" and hasattr(self, "chat_surface"):
            self.chat_surface.input.focus_set()

    def _build_chat(self, panel):
        self.chat_surface = PremiumChatSurface(
            panel, self.desktop,
            on_tasks=lambda: self._show("tasks"),
            on_apps=lambda: self._show("connectors"),
        )
        self.chat_surface.pack(fill="both", expand=True)

    def _build_tasks(self, panel):
        write(panel, "Tugas", size=24, bold=True).pack(
            anchor="w", padx=20, pady=(24, 4))
        write(panel, "Atur pekerjaanmu dengan lebih tenang.",
              size=11, color=MUTED).pack(anchor="w", padx=20, pady=(0, 22))
        form = tk.Frame(panel, bg=BASE)
        form.pack(fill="x", padx=20, pady=(0, 10))
        self.title_var = tk.StringVar(master=self)
        self.due_var = tk.StringVar(master=self)
        write(form, "Nama tugas", size=10).grid(row=0, column=0, sticky="w")
        write(form, "Tanggal (opsional)", size=10).grid(
            row=0, column=1, sticky="w", padx=8)
        for col, var in ((0, self.title_var), (1, self.due_var)):
            entry = tk.Entry(
                form, textvariable=var, bg=CARD, fg=FG,
                insertbackground=FG, font=("Segoe UI", 11),
                relief="flat", bd=0,
                highlightbackground=LINE, highlightthickness=1,
            )
            entry.grid(row=1, column=col, sticky="ew",
                       padx=(0, 8), ipady=12, pady=8)
        button(form, "+ Tambah", self.add, accent=True).grid(row=1, column=2)
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=2)
        write(
            panel, "Contoh tanggal: 2026-11-09T14:30:00+07:00",
            size=9, color=MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 17))

        table_holder = tk.Frame(panel, bg=BASE)
        table_holder.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        self.table = ttk.Treeview(
            table_holder, columns=("title", "status", "due"),
            show="headings", selectmode="browse", height=9,
            style="Premium.Treeview",
        )
        for key, heading, width in (
            ("title", "TUGAS", 350),
            ("status", "STATUS", 110),
            ("due", "JATUH TEMPO (UTC)", 190),
        ):
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, stretch=key == "title")
        self.table.pack(fill="both", expand=True)
        commands = tk.Frame(panel, bg=BASE)
        commands.pack(fill="x", padx=20, pady=(0, 12))
        for title, state in (
            ("Selesai", "completed"),
            ("Jeda", "paused"),
            ("Batalkan", "cancelled"),
        ):
            button(commands, title, lambda s=state: self.change(s)).pack(
                side="left", padx=(0, 7))
        button(commands, "Segarkan", self.refresh).pack(side="left")
        button(commands, "Berikutnya", lambda: self.page(1)).pack(side="right")
        button(commands, "Sebelumnya", lambda: self.page(-1)).pack(
            side="right", padx=(0, 7))
        self.feedback = tk.StringVar(master=self, value="")
        tk.Label(
            panel, textvariable=self.feedback, bg=BASE, fg=MUTED,
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 16))

    def _build_connectors(self, panel):
        write(panel, "Aplikasi", size=24, bold=True).pack(
            anchor="w", padx=20, pady=(24, 6))
        write(
            panel, "Lihat layanan yang mungkin dapat dihubungkan.",
            color=MUTED, size=11,
        ).pack(anchor="w", padx=20)
        write(
            panel, "Belum terhubung. Setiap akun memerlukan izin tersendiri.",
            color="#c8b9ea", size=10,
        ).pack(anchor="w", padx=20, pady=(8, 18))
        frame = tk.Frame(panel, bg=BASE)
        frame.pack(fill="both", expand=True, padx=20)
        listing = ttk.Treeview(
            frame, columns=("kind", "name", "status"),
            show="headings", style="Premium.Treeview",
        )
        for key, heading, width in (
            ("kind", "JENIS", 160),
            ("name", "APLIKASI / KEMAMPUAN", 330),
            ("status", "STATUS", 170),
        ):
            listing.heading(key, text=heading)
            listing.column(key, width=width, stretch=key=="name")
        listing.pack(fill="both", expand=True)
        try:
            entries = load_catalog()
        except (CatalogRejected, OSError):
            entries = ()
        for index, item in enumerate(entries):
            listing.insert(
                "", "end", iid="i-"+str(index),
                values=(item.kind, item.name, "Belum terhubung"),
            )
        write(
            panel, "Daftar ini belum bisa mengakses akun pribadi atau menjalankan tugas.",
            color=MUTED, size=9,
        ).pack(anchor="w", padx=20, pady=15)
        button(panel, "Lihat alat lanjutan", self._advanced).pack(
            anchor="w", padx=20, pady=(0, 22))

    def _build_history(self, panel):
        write(panel, "Riwayat sesi ini", size=24, bold=True).pack(
            anchor="w", padx=20, pady=(24, 5))
        write(
            panel, "Percakapan saat aplikasi terbuka. "
                   "Belum tersimpan permanen.",
            color=MUTED, size=11,
        ).pack(anchor="w", padx=20, pady=(0, 16))
        self.history_view = tk.Text(
            panel, bg=CARD, fg=FG, wrap="word",
            font=("Segoe UI", 11), state="disabled",
            relief="flat", padx=18, pady=18,
        )
        self.history_view.pack(fill="both", expand=True, padx=20, pady=(0, 24))

    def _refresh_history(self):
        if not hasattr(self, "history_view"):
            return
        source = self.chat_surface.chat.get("1.0", "end").strip()
        self.history_view.configure(state="normal")
        self.history_view.delete("1.0", "end")
        self.history_view.insert(
            "1.0", source or "Belum ada percakapan pada sesi ini.",
        )
        self.history_view.configure(state="disabled")

    def _settings(self):
        if self.closed:
            return
        popup = tk.Toplevel(self)
        popup.title("VARYN | Pengaturan")
        popup.configure(bg=BASE)
        popup.geometry("440x250")
        popup.transient(self)
        write(popup, "Pengaturan", size=20, bold=True).pack(
            anchor="w", padx=23, pady=(22, 7))
        write(
            popup, "Pilih layanan AI di Chat sebelum mengatur model.",
            size=10, color=MUTED,
        ).pack(anchor="w", padx=23, pady=(0, 20))
        def ai_config():
            popup.destroy()
            self._show("chat")
            self.chat_surface.open_settings()
        button(popup, "Pengaturan AI", ai_config, accent=True).pack(
            anchor="w", padx=23, pady=(0, 10))
        button(popup, "Alat lanjutan", lambda: (
            popup.destroy(), self._advanced(),
        )).pack(anchor="w", padx=23)
