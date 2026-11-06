"""VARYN's everyday workspace, optimized for nontechnical desktop users.

English is the default, with Indonesian, Spanish and French available.
The app is a proper resizable/maximizable window, not a transient dialog.
No imaginary connected applications, auto-executed tasks or online AI answers.
"""
from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from tkinter import ttk

from varyn.owner_home import OwnerHome
from varyn.integration_catalog import load_catalog, CatalogRejected
from varyn.unlimited_task_store import TaskRejected
from varyn.consumer_chat import ConsumerChat
from varyn.ui_language import (
    LANGUAGES, LABELS, load_language, save_language, text as tr,
)

BG = "#FAFAF7"
SIDE = "#F0F1ED"
WHITE = "#FFFFFF"
INK = "#25313D"
MUTED = "#6F7880"
ACCENT = "#3E5F71"
LINE = "#E1E5E1"

_STATE_LABELS = {
    "en": ("Pending", "Due", "Paused", "Completed", "Cancelled"),
    "id": ("Menunggu", "Jatuh tempo", "Dijeda", "Selesai", "Dibatalkan"),
    "es": ("Pendiente", "Vencida", "Pausada", "Completada", "Cancelada"),
    "fr": ("En attente", "À faire", "En pause", "Terminée", "Annulée"),
}
_STATES = ("pending", "due", "paused", "completed", "cancelled")
_KIND_LABELS = {
    "en": ("App connection", "Plugin candidate", "Skill candidate"),
    "id": ("Koneksi aplikasi", "Calon plugin", "Calon skill"),
    "es": ("Conexión", "Complemento previsto", "Función prevista"),
    "fr": ("Connexion", "Extension prévue", "Fonction prévue"),
}
_KINDS = ("connector", "plugin_candidate", "skill_candidate")


def _label(parent, value, *, size=11, fg=INK, bold=False, bg=BG):
    return tk.Label(
        parent, text=value, bg=bg, fg=fg, anchor="w", justify="left",
        font=("Segoe UI", size, "bold" if bold else "normal"),
    )


def _button(parent, caption, command, *, primary=False):
    return tk.Button(
        parent, text=caption, command=command, cursor="hand2",
        font=("Segoe UI", 10, "bold" if primary else "normal"),
        bg=ACCENT if primary else WHITE,
        fg=WHITE if primary else INK,
        activebackground="#527D91" if primary else "#EDEFEA",
        activeforeground=WHITE if primary else INK,
        bd=0, relief="flat", padx=15, pady=9,
    )


class ConsumerWorkspace(OwnerHome):
    """Real working owner home that does not require engineering terminology."""

    def __init__(self, desktop, *, database_path=None):
        self.language = load_language()
        self._translated = []
        self._locale_switching = False
        super().__init__(desktop, database_path=database_path)

    def _t(self, key, **data):
        return tr(self.language, key, **data)

    def _caption(self, parent, key, **style):
        widget = _label(parent, self._t(key), **style)
        self._translated.append((widget, key))
        return widget

    def _action(self, parent, key, command, *, primary=False):
        widget = _button(parent, self._t(key), command, primary=primary)
        self._translated.append((widget, key))
        return widget

    def _build(self):
        self.title("VARYN")
        self.geometry("1320x820")
        self.minsize(900, 620)
        self.resizable(True, True)
        self.configure(bg=BG)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "VarynConsumer.Treeview",
            background=WHITE, foreground=INK, fieldbackground=WHITE,
            borderwidth=0, rowheight=39, font=("Segoe UI", 10),
        )
        style.configure(
            "VarynConsumer.Treeview.Heading",
            background=SIDE, foreground=MUTED, borderwidth=0,
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "VarynConsumer.Treeview",
            background=[("selected", "#E4EBEB")],
            foreground=[("selected", INK)],
        )
        style.configure(
            "VarynConsumer.Combo.TCombobox",
            fieldbackground=WHITE, background=WHITE, foreground=INK,
            borderwidth=0, padding=8,
        )
        style.map(
            "VarynConsumer.Combo.TCombobox",
            fieldbackground=[("readonly", WHITE)],
            foreground=[("readonly", INK)],
        )
        self._panels = {}
        self._nav = {}
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=SIDE, width=218)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=SIDE)
        brand.pack(fill="x", padx=24, pady=(34, 34))
        tk.Label(
            brand, text="VARYN", bg=SIDE, fg=INK,
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")
        self.workspace_label = self._caption(
            sidebar, "workspace", size=9, fg=MUTED, bold=True, bg=SIDE,
        )
        self.workspace_label.pack(anchor="w", padx=24, pady=(0, 15))

        for page, key in (
            ("chat", "home"), ("tasks", "tasks"),
            ("connectors", "apps"), ("history", "history"),
        ):
            entry = tk.Button(
                sidebar, text=self._t(key),
                command=lambda p=page: self._show(p),
                bg=SIDE, fg=INK, activebackground="#E0E5E2",
                activeforeground=INK,
                font=("Segoe UI", 11), anchor="w",
                padx=19, pady=13, relief="flat", bd=0,
                cursor="hand2",
            )
            entry.pack(fill="x", padx=10, pady=2)
            self._nav[page] = entry

        tk.Frame(sidebar, bg=SIDE).pack(fill="both", expand=True)
        self.prefs_button = self._action(
            sidebar, "settings", self._settings,
        )
        self.prefs_button.configure(
            bg=SIDE, anchor="w", padx=19,
            activebackground="#E0E5E2",
        )
        self.prefs_button.pack(fill="x", padx=10, pady=(0, 16))
        self.personal_label = self._caption(
            sidebar, "personal", size=10, fg=MUTED, bg=SIDE,
        )
        self.personal_label.pack(anchor="w", padx=29, pady=(0, 30))

        right = tk.Frame(shell, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        header = tk.Frame(right, bg=BG)
        header.pack(fill="x", padx=28, pady=(20, 15))
        self.header_title = _label(
            header, "VARYN", size=12, bold=True,
        )
        self.header_title.pack(side="left")
        self.expand_button = self._action(
            header, "expand", self._toggle_maximize,
        )
        self.expand_button.pack(side="right", padx=(12, 0))
        self.language_var = tk.StringVar(
            master=self, value=LABELS.get(self.language, "English"),
        )
        self.language_selector = ttk.Combobox(
            header, textvariable=self.language_var,
            values=list(LANGUAGES), state="readonly",
            width=19, style="VarynConsumer.Combo.TCombobox",
            font=("Segoe UI", 10),
        )
        self.language_selector.pack(side="right")
        self.language_selector.bind(
            "<<ComboboxSelected>>", self._change_language,
        )

        body = tk.Frame(right, bg=BG)
        body.pack(fill="both", expand=True, padx=19, pady=(0, 13))
        for name in ("chat", "tasks", "connectors", "history"):
            self._panels[name] = tk.Frame(body, bg=BG)
        self._build_chat(self._panels["chat"])
        self._build_tasks(self._panels["tasks"])
        self._build_connectors(self._panels["connectors"])
        self._build_history(self._panels["history"])
        self._show("chat")
        # Normal Windows top-level window with native maximize support;
        # start enlarged without permanently locking the owner at this size.
        if os.name == "nt":
            self.after_idle(self._start_maximized)

    def _start_maximized(self):
        if self.closed:
            return
        try:
            self.state("zoomed")
            self.expand_button.configure(text=self._t("restore"))
        except tk.TclError:
            pass

    def _toggle_maximize(self):
        if self.closed:
            return
        try:
            was_zoomed = self.state() == "zoomed"
            self.state("normal" if was_zoomed else "zoomed")
            self.expand_button.configure(
                text=self._t("expand" if was_zoomed else "restore"),
            )
        except tk.TclError:
            # Native titlebar maximize may still work on non-Windows Tk.
            pass

    def _show(self, page):
        if self.closed or page not in self._panels:
            return
        if page == "history":
            self._refresh_history()
        for key, panel in self._panels.items():
            panel.pack_forget()
            self._nav[key].configure(
                bg="#DEE6E1" if key == page else SIDE,
                fg=INK,
            )
        self._panels[page].pack(fill="both", expand=True)
        if page == "chat":
            self.chat_surface.input.focus_set()

    def _build_chat(self, frame):
        self.chat_surface = ConsumerChat(
            frame, self.desktop, language=self.language,
            on_tasks=lambda: self._show("tasks"),
            on_apps=lambda: self._show("connectors"),
        )
        self.chat_surface.pack(fill="both", expand=True, padx=36, pady=14)

    def _section_header(self, parent, title_key, subtitle_key):
        heading = self._caption(
            parent, title_key, size=24, bold=True,
        )
        heading.pack(anchor="w", padx=24, pady=(27, 8))
        sub = self._caption(
            parent, subtitle_key, size=11, fg=MUTED,
        )
        sub.pack(anchor="w", padx=24, pady=(0, 27))

    def _build_tasks(self, frame):
        self._section_header(frame, "tasks", "tasks_intro")
        form = tk.Frame(frame, bg=BG)
        form.pack(fill="x", padx=24, pady=(0, 11))
        self.title_var = tk.StringVar(master=self)
        self.due_var = tk.StringVar(master=self)
        self._caption(
            form, "task_name", size=10, fg=MUTED,
        ).grid(row=0, column=0, sticky="w")
        self._caption(
            form, "due_date", size=10, fg=MUTED,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))
        for column, variable in (
            (0, self.title_var), (1, self.due_var),
        ):
            tk.Entry(
                form, textvariable=variable, bg=WHITE, fg=INK,
                insertbackground=INK, font=("Segoe UI", 11),
                relief="flat", bd=0,
                highlightthickness=1, highlightbackground=LINE,
            ).grid(
                row=1, column=column, sticky="ew",
                ipady=13, pady=7, padx=(0, 11),
            )
        self._action(
            form, "add", self.add, primary=True,
        ).grid(row=1, column=2)
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=2)
        self._caption(
            frame, "date_example", size=9, fg=MUTED,
        ).pack(anchor="w", padx=24, pady=(0, 21))
        holder = tk.Frame(frame, bg=BG)
        holder.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.table = ttk.Treeview(
            holder, columns=("title", "status", "due"),
            show="headings", selectmode="browse", height=10,
            style="VarynConsumer.Treeview",
        )
        for key, width, col in (
            ("task_col", 360, "title"),
            ("status_col", 160, "status"),
            ("due_col", 230, "due"),
        ):
            self.table.heading(col, text=self._t(key))
            self.table.column(
                col, width=width, stretch=(col=="title"), minwidth=85,
            )
        self.table.pack(fill="both", expand=True)
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill="x", padx=24, pady=(0, 14))
        for label, status in (
            ("complete", "completed"),
            ("pause", "paused"),
            ("cancel", "cancelled"),
        ):
            self._action(
                controls, label, lambda s=status: self.change(s),
            ).pack(side="left", padx=(0, 7))
        self._action(
            controls, "refresh", self.refresh,
        ).pack(side="left")
        self._action(
            controls, "next", lambda: self.page(1),
        ).pack(side="right")
        self._action(
            controls, "previous", lambda: self.page(-1),
        ).pack(side="right", padx=(0, 6))
        self.feedback = tk.StringVar(master=self, value="")
        self.feedback_widget = tk.Label(
            frame, textvariable=self.feedback, bg=BG, fg=MUTED,
            font=("Segoe UI", 10), anchor="w",
        )
        self.feedback_widget.pack(fill="x", padx=24, pady=(0, 20))

    def _build_connectors(self, frame):
        self._section_header(frame, "apps", "apps_intro")
        self._caption(
            frame, "apps_warning", size=10, fg=ACCENT,
        ).pack(anchor="w", padx=24, pady=(0, 16))
        holder = tk.Frame(frame, bg=BG)
        holder.pack(fill="both", expand=True, padx=24)
        self.app_tree = ttk.Treeview(
            holder, columns=("kind", "name", "status"),
            show="headings", style="VarynConsumer.Treeview",
        )
        for key, col, width in (
            ("type_col", "kind", 160),
            ("app_col", "name", 340),
            ("connection_col", "status", 170),
        ):
            self.app_tree.heading(col, text=self._t(key))
            self.app_tree.column(
                col, width=width, minwidth=90, stretch=col=="name",
            )
        self.app_tree.pack(fill="both", expand=True)
        try:
            self._app_entries = load_catalog()
        except (CatalogRejected, OSError):
            self._app_entries = ()
        self._refresh_apps()
        self._caption(
            frame, "apps_footnote", size=10, fg=MUTED,
        ).pack(anchor="w", padx=24, pady=15)
        self._action(
            frame, "advanced", self._advanced,
        ).pack(anchor="w", padx=24, pady=(0, 20))

    def _refresh_apps(self):
        for child in self.app_tree.get_children():
            self.app_tree.delete(child)
        for i, item in enumerate(self._app_entries):
            code = _KINDS.index(item.kind) if item.kind in _KINDS else 0
            self.app_tree.insert(
                "", "end", iid=str(i),
                values=(
                    _KIND_LABELS[self.language][code],
                    item.name, self._t("not_connected"),
                ),
            )

    def _build_history(self, frame):
        self._section_header(frame, "history_title", "history_note")
        self.history_view = tk.Text(
            frame, bg=WHITE, fg=INK, state="disabled",
            font=("Segoe UI", 11), wrap="word",
            relief="flat", padx=19, pady=18,
            highlightthickness=1, highlightbackground=LINE,
        )
        self.history_view.pack(
            fill="both", expand=True, padx=24, pady=(0, 28),
        )

    def _refresh_history(self):
        transcript = self.chat_surface.chat.get("1.0", "end").strip()
        self.history_view.configure(state="normal")
        self.history_view.delete("1.0", "end")
        self.history_view.insert(
            "1.0", transcript or self._t("history_empty"),
        )
        self.history_view.configure(state="disabled")

    def _change_language(self, _event=None):
        choice = self.language_var.get()
        selected = LANGUAGES.get(choice)
        if selected is None or selected == self.language:
            return
        self.language = selected
        try:
            save_language(selected)
        except OSError:
            # The UI still switches even if preferences cannot be written.
            pass
        self._apply_language()

    def _apply_language(self):
        for widget, key in self._translated:
            if widget.winfo_exists():
                widget.configure(text=self._t(key))
        for page, key in (
            ("chat", "home"), ("tasks", "tasks"),
            ("connectors", "apps"), ("history", "history"),
        ):
            self._nav[page].configure(text=self._t(key))
        self.expand_button.configure(
            text=self._t(
                "restore" if self.state() == "zoomed" else "expand",
            ),
        )
        self.chat_surface.set_language(self.language)
        for col, key in (
            ("title", "task_col"), ("status", "status_col"),
            ("due", "due_col"),
        ):
            self.table.heading(col, text=self._t(key))
        for col, key in (
            ("kind", "type_col"), ("name", "app_col"),
            ("status", "connection_col"),
        ):
            self.app_tree.heading(col, text=self._t(key))
        self.refresh()
        self._refresh_apps()
        self._refresh_history()

    def _settings(self):
        if self.closed:
            return
        popup = tk.Toplevel(self)
        popup.title("VARYN | " + self._t("settings"))
        popup.configure(bg=BG)
        popup.geometry("500x360")
        popup.resizable(True, True)
        popup.transient(self)
        frame = tk.Frame(popup, bg=BG)
        frame.pack(fill="both", expand=True, padx=25, pady=24)
        self._caption(
            frame, "settings", size=22, bold=True,
        ).pack(anchor="w")
        self._caption(
            frame, "prefs_intro", size=11, fg=MUTED,
        ).pack(anchor="w", pady=(8, 20))
        self._caption(
            frame, "settings_language", size=10, bold=True,
        ).pack(anchor="w")
        selected = tk.StringVar(
            master=popup, value=LABELS.get(self.language, "English"),
        )
        combo = ttk.Combobox(
            frame, textvariable=selected,
            values=list(LANGUAGES), state="readonly",
            font=("Segoe UI", 11),
        )
        combo.pack(fill="x", pady=(9, 13))
        def select(_event=None):
            self.language_var.set(selected.get())
            self._change_language()
        combo.bind("<<ComboboxSelected>>", select)
        self._caption(
            frame, "prefs_note", size=10, fg=MUTED,
        ).pack(anchor="w", pady=(0, 18))
        def model():
            popup.destroy()
            self._show("chat")
            self.chat_surface.open_settings()
        self._action(
            frame, "settings_ai", model, primary=True,
        ).pack(anchor="w")
        self._action(
            frame, "close", popup.destroy,
        ).pack(anchor="e", pady=(16, 0))

    def add(self):
        if self.closed:
            return
        try:
            self.store.create(
                self.title_var.get(),
                due_utc=self.due_var.get().strip() or None,
            )
            self.title_var.set("")
            self.due_var.set("")
            self.offset = 0
            self.refresh()
            self.feedback.set(self._t("task_saved"))
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set(self._t("task_invalid"))

    def change(self, state):
        if self.closed:
            return
        selected = self.table.selection()
        if not selected:
            self.feedback.set(self._t("task_select"))
            return
        try:
            self.store.transition(selected[0], state)
            self.refresh()
            self.feedback.set(self._t("task_changed"))
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set(self._t("task_change_invalid"))

    def refresh(self):
        if self.closed:
            return
        try:
            total = self.store.count()
            if self.offset >= total:
                self.offset = (max(0, total-1) // 100) * 100
            rows = self.store.list(limit=100, offset=self.offset)
            for item in self.table.get_children():
                self.table.delete(item)
            for row in rows:
                status = row["status"]
                index = _STATES.index(status) if status in _STATES else 0
                self.table.insert(
                    "", "end", iid=row["id"],
                    values=(
                        row["title"],
                        _STATE_LABELS[self.language][index],
                        row["due_utc"] or "—",
                    ),
                )
            self.feedback.set(self._t(
                "task_count", total=total, shown=len(rows),
            ))
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set(self._t("task_db_error"))

    def _tick(self):
        self.tick_id = None
        if self.closed or self.desktop._closing:
            return
        try:
            changed = self.store.mark_due(batch_size=200)
            if changed:
                self.refresh()
        except (TaskRejected, OSError, sqlite3.Error):
            self.feedback.set(self._t("due_error"))
        self.tick_id = self.after(30000, self._tick)
