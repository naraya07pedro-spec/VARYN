"""VARYN premium dark desktop shell.

Local tasks are unencrypted SQLite. Integration catalog is discovery-only.
The chat retains its original owner authorization and provider boundaries.
"""
import os
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import ttk
from varyn.integration_catalog import load_catalog, CatalogRejected
from varyn.unlimited_task_store import TaskStore, TaskRejected
from varyn.simple_chat import ChatSurface

BG = "#090e19"
SIDE = "#0e1626"
PANEL = "#111b2d"
CARD = "#162339"
TEXT = "#f4f7fc"
MUTED = "#93a5c0"
ACCENT = "#7868fa"
LINE = "#253449"


def owner_task_path():
    root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    folder = root / "VARYN"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "tasks.sqlite3"


def label(parent, text, *, size=11, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop("bg", PANEL), fg=color,
                    font=("Segoe UI", size, "bold" if bold else "normal"),
                    justify="left", anchor="w", **kwargs)


def action(parent, title, callback, *, primary=False, width=None):
    return tk.Button(
        parent, text=title, command=callback,
        bg=ACCENT if primary else CARD, fg="#ffffff" if primary else TEXT,
        activebackground="#9185ff" if primary else "#223552",
        activeforeground="#ffffff", bd=0, relief="flat",
        font=("Segoe UI", 10, "bold"), cursor="hand2",
        padx=16, pady=10, width=width,
        highlightthickness=0,
    )


class OwnerHome(tk.Toplevel):
    def __init__(self, desktop, *, database_path=None):
        super().__init__(desktop)
        self.desktop = desktop
        self.closed = False
        self.tick_id = None
        self.offset = 0
        self.store = None
        self._nav = {}
        self._panels = {}
        self.title("VARYN | Personal AI Workspace")
        self.geometry("1170x760")
        self.minsize(870, 570)
        self.configure(bg=BG)
        # This is the real owner application, not a temporary modal dialog.
        # Windows Toplevel.transient() suppresses its maximize/restore controls.
        self.resizable(True, True)
        try:
            self.store = TaskStore(database_path or owner_task_path())
            self._build()
            self.refresh()
            self.tick_id = self.after(30000, self._tick)
        except BaseException:
            if self.store is not None:
                self.store.close()
            self.destroy()
            raise
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("V.Treeview", background=CARD, foreground=TEXT,
                        fieldbackground=CARD, rowheight=35, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("V.Treeview.Heading", background=SIDE, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("V.Treeview", background=[("selected", "#384679")])
        style.configure("V.Scrollbar", background=SIDE, troughcolor=PANEL)
        style.configure("V.Entry", foreground=TEXT, fieldbackground=CARD,
                        insertcolor=TEXT, bordercolor=LINE, padding=8)
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=SIDE, width=222)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        branding = tk.Frame(sidebar, bg=SIDE)
        branding.pack(fill="x", padx=24, pady=(28, 28))
        tk.Label(branding, text="◆", font=("Segoe UI", 24, "bold"),
                 fg=ACCENT, bg=SIDE).pack(side="left")
        tk.Label(branding, text=" VARYN", font=("Segoe UI", 18, "bold"),
                 fg=TEXT, bg=SIDE).pack(side="left")
        tk.Label(sidebar, text="WORKSPACE", bg=SIDE, fg="#687d9b",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=26, pady=(0, 12))
        for key, title in (
            ("chat", "  ◉   AI Chat"), ("tasks", "  ▤   My Tasks"),
            ("connectors", "  ◈   Connectors & Skills"),
        ):
            btn = tk.Button(
                sidebar, text=title, anchor="w",
                font=("Segoe UI", 11, "bold"), relief="flat", bd=0,
                bg=SIDE, fg=MUTED, activebackground=CARD,
                activeforeground=TEXT, cursor="hand2",
                padx=18, pady=13, command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", padx=12, pady=3)
            self._nav[key] = btn
        tk.Frame(sidebar, bg=SIDE).pack(fill="both", expand=True)
        label(sidebar, "●  LOCAL WORKSPACE", size=9, color="#6ad5a4",
              bg=SIDE).pack(anchor="w", padx=24, pady=(0, 7))
        label(sidebar, "Experimental  •  Alpha build", size=9,
              color=MUTED, bg=SIDE).pack(anchor="w", padx=24, pady=(0, 25))
        right = tk.Frame(shell, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=BG, height=74)
        top.pack(fill="x", padx=30, pady=(14, 0))
        label(top, "Your personal AI, your control", size=12,
              color=MUTED, bg=BG).pack(side="left", pady=13)
        action(top, "Advanced tools", self._advanced).pack(side="right")
        area = tk.Frame(right, bg=BG)
        area.pack(fill="both", expand=True, padx=30, pady=(10, 25))
        for key in ("chat", "tasks", "connectors"):
            panel = tk.Frame(area, bg=PANEL,
                             highlightbackground=LINE, highlightthickness=1)
            self._panels[key] = panel
        self._build_chat(self._panels["chat"])
        self._build_tasks(self._panels["tasks"])
        self._build_connectors(self._panels["connectors"])
        self._show("chat")

    def _show(self, page):
        if self.closed:
            return
        for key, panel in self._panels.items():
            panel.pack_forget()
            self._nav[key].configure(
                bg=ACCENT if key == page else SIDE,
                fg=TEXT if key == page else MUTED,
            )
        self._panels[page].pack(fill="both", expand=True)
        if page == "chat" and hasattr(self, "chat_surface"):
            self.chat_surface.input.focus_set()

    def _build_chat(self, panel):
        self.chat_surface = ChatSurface(panel, self.desktop)
        self.chat_surface.pack(fill="both", expand=True, padx=24, pady=21)

    def _build_tasks(self, panel):
        header = tk.Frame(panel, bg=PANEL)
        header.pack(fill="x", padx=27, pady=(27, 12))
        label(header, "My Tasks", size=22, bold=True).pack(anchor="w")
        label(header, "Your local work queue. No artificial total task count cap.",
              color=MUTED).pack(anchor="w", pady=5)
        form = tk.Frame(panel, bg=PANEL)
        form.pack(fill="x", padx=27, pady=(4, 8))
        self.title_var = tk.StringVar(master=self)
        self.due_var = tk.StringVar(master=self)
        label(form, "TASK", size=9, color=MUTED).grid(row=0, column=0, sticky="w")
        label(form, "DUE DATE (OPTIONAL)", size=9, color=MUTED).grid(
            row=0, column=1, sticky="w", padx=(8, 0))
        tk.Entry(form, textvariable=self.title_var, bg=CARD, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 11),
                 highlightthickness=1, highlightbackground=LINE).grid(
                    row=1, column=0, sticky="ew", ipady=10)
        tk.Entry(form, textvariable=self.due_var, bg=CARD, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
                 highlightthickness=1, highlightbackground=LINE).grid(
                    row=1, column=1, sticky="ew", ipady=11, padx=8)
        action(form, "+ Add task", self.add, primary=True).grid(row=1, column=2)
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=2)
        label(panel, "Example: 2026-11-09T14:30:00+07:00", size=9,
              color=MUTED).pack(anchor="w", padx=27, pady=(0, 12))
        frame = tk.Frame(panel, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=27, pady=(0, 10))
        self.table = ttk.Treeview(frame, columns=("title", "status", "due"),
                                  show="headings", height=9, selectmode="browse",
                                  style="V.Treeview")
        for key, heading, width in (
            ("title", "TASK", 330), ("status", "STATUS", 110),
            ("due", "DUE UTC", 220),
        ):
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, stretch=key=="title")
        self.table.pack(fill="both", expand=True)
        actions = tk.Frame(panel, bg=PANEL)
        actions.pack(fill="x", padx=27, pady=(0, 8))
        for title, state in (("✓ Complete", "completed"),
                             ("Pause", "paused"), ("Cancel", "cancelled")):
            action(actions, title, lambda s=state: self.change(s)).pack(
                side="left", padx=(0, 7))
        action(actions, "Refresh", self.refresh).pack(side="left")
        action(actions, "Next →", lambda: self.page(1)).pack(side="right")
        action(actions, "← Previous", lambda: self.page(-1)).pack(
            side="right", padx=(0, 7))
        self.feedback = tk.StringVar(master=self, value="")
        tk.Label(panel, textvariable=self.feedback, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(
                    fill="x", padx=27, pady=(0, 17))

    def _build_connectors(self, panel):
        label(panel, "Connectors & Skills", size=22, bold=True).pack(
            anchor="w", padx=27, pady=(27, 4))
        label(panel, "Explore future integrations. Nothing is connected to your accounts.",
              color=MUTED).pack(anchor="w", padx=27, pady=(0, 17))
        frame = tk.Frame(panel, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=27)
        tree = ttk.Treeview(frame, columns=("kind", "name", "status"),
                            show="headings", style="V.Treeview")
        for key, heading, width in (
            ("kind", "TYPE", 160), ("name", "APPLICATION / SKILL", 350),
            ("status", "CONNECTION", 160),
        ):
            tree.heading(key, text=heading)
            tree.column(key, width=width, stretch=(key=="name"))
        tree.pack(fill="both", expand=True)
        try:
            entries = load_catalog()
        except (CatalogRejected, OSError):
            entries = ()
            label(panel, "Local catalog unavailable", color=MUTED).pack(anchor="w")
        for i, entry in enumerate(entries):
            tree.insert("", "end", iid="c-"+str(i),
                        values=(entry.kind, entry.name, "NOT CONNECTED"))
        label(panel, "GitHub public metadata is available from Advanced tools. "
              "Private app accounts require separate official login.",
              size=9, color=MUTED).pack(anchor="w", padx=27, pady=15)
        action(panel, "Advanced tools", self._advanced).pack(
            anchor="w", padx=27, pady=(0, 22))

    def _model(self):
        if self.closed or self.desktop._closing: return
        self.desktop._open_model_control_center()
        panel = self.desktop._model_center
        if panel is not None and panel.winfo_exists():
            panel.lift()
            panel.focus_set()

    def _relay(self):
        if self.closed or self.desktop._closing: return
        self.desktop._open_relay_workbench()
        panel = self.desktop._relay_workbench
        if panel is not None and panel.winfo_exists():
            panel.lift()

    def _advanced(self):
        if self.closed or self.desktop._closing: return
        self.desktop.deiconify()
        self.desktop.lift()

    def add(self):
        if self.closed: return
        try:
            self.store.create(self.title_var.get(),
                              due_utc=self.due_var.get().strip() or None)
            self.title_var.set("")
            self.due_var.set("")
            self.offset = 0
            self.refresh()
            self.feedback.set("Task saved locally. No action executed.")
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set("Invalid title or due date. Include a timezone (+07:00).")

    def change(self, state):
        if self.closed: return
        selected = self.table.selection()
        if not selected:
            self.feedback.set("Select a task first.")
            return
        try:
            self.store.transition(selected[0], state)
            self.refresh()
            self.feedback.set("Task marked " + state + ". No external action.")
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set("Cannot change task in its current state.")

    def page(self, delta):
        if self.closed: return
        self.offset = max(0, self.offset + delta*100)
        self.refresh()

    def refresh(self):
        if self.closed: return
        try:
            total = self.store.count()
            if self.offset >= total:
                self.offset = (max(0, total-1)//100)*100
            rows = self.store.list(limit=100, offset=self.offset)
            for iid in self.table.get_children():
                self.table.delete(iid)
            for item in rows:
                self.table.insert("", "end", iid=item["id"], values=(
                    item["title"], item["status"], item["due_utc"] or "Not scheduled"))
            self.feedback.set(
                str(total) + " tasks saved • " + str(len(rows)) +
                " shown • due checked while VARYN runs, never executed.")
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set("Task database unavailable. No task dispatched.")

    def _tick(self):
        self.tick_id = None
        if self.closed or self.desktop._closing: return
        try:
            updated = self.store.mark_due(batch_size=200)
            if updated: self.refresh()
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set("Due refresh failed. No task executed.")
        self.tick_id = self.after(30000, self._tick)

    def close(self):
        if self.closed: return
        self.closed = True
        if self.tick_id is not None:
            try: self.after_cancel(self.tick_id)
            except tk.TclError: pass
            self.tick_id = None
        if hasattr(self, "chat_surface"):
            self.chat_surface.close()
        if self.store is not None:
            self.store.close()
            self.store = None
        self.destroy()
