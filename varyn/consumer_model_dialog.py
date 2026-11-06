"""Consumer model selection: choose provider, paste key, browse real models.

Only a user-triggered GET /models is sent when clicking Load models.
The secret lives in RAM for this process, not in environment variables/files.
Each chat request still presents its actual full outgoing text for approval.
"""
from __future__ import annotations

from datetime import date
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from varyn.consumer_model_picker import (
    fetch_models, ListedModel, ModelListError, KEY_PAGES, PRICING_PAGES,
)
from varyn.model_control_center import create_reviewed_offer
from varyn.model_registry import Registry, RegistryRejected

BASE = "#FAFAF7"
INK = "#27333D"
MUTED = "#60717D"
WHITE = "#FFFFFF"
BLUE = "#3E5F71"
LINE = "#DADEDE"


class ModelSelectionDialog(tk.Toplevel):
    def __init__(self, chat):
        super().__init__(chat.winfo_toplevel())
        self.chat = chat
        self.title("VARYN | Choose AI")
        self.geometry("930x685")
        self.minsize(690, 495)
        self.configure(bg=BASE)
        self.transient(chat.winfo_toplevel())
        self._queue = queue.Queue()
        self._poll_id = None
        self._closed = False
        self._request_running = False
        self._models = ()
        self._visible = ()
        self.provider = tk.StringVar(
            master=self, value=chat.mode.get() if chat.mode.get() in
            ("OpenRouter", "DeepSeek") else "OpenRouter",
        )
        self.api_key = tk.StringVar(master=self, value="")
        self.query = tk.StringVar(master=self, value="")
        self.status = tk.StringVar(master=self, value="Select a provider and load its live model catalog.")
        self.reviewed = tk.BooleanVar(master=self, value=False)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()

    def _txt(self, parent, content, *, size=10, muted=False, bold=False):
        return tk.Label(
            parent, text=content, bg=BASE, fg=MUTED if muted else INK,
            anchor="w", justify="left",
            font=("Segoe UI", size, "bold" if bold else "normal"),
        )

    def _btn(self, parent, text, command, *, primary=False):
        return tk.Button(
            parent, text=text, command=command,
            bg=BLUE if primary else WHITE, fg=WHITE if primary else INK,
            activebackground="#526F81" if primary else "#EAF0EE",
            activeforeground=WHITE if primary else INK,
            relief="flat", bd=0, padx=14, pady=9,
            font=("Segoe UI", 10), cursor="hand2",
        )

    def _build(self):
        p = tk.Frame(self, bg=BASE)
        p.pack(fill="both", expand=True, padx=26, pady=(21, 17))
        self._txt(p, "Choose your AI", size=21, bold=True).pack(anchor="w")
        self._txt(
            p, "Use your own API key. Model names and available prices come from the provider.",
            muted=True,
        ).pack(anchor="w", pady=(5, 19))

        upper = tk.Frame(p, bg=BASE)
        upper.pack(fill="x")
        left = tk.Frame(upper, bg=BASE)
        left.pack(side="left", fill="x", expand=True)
        self._txt(left, "Provider", bold=True).pack(anchor="w")
        self.provider_box = ttk.Combobox(
            left, textvariable=self.provider,
            values=("OpenRouter", "DeepSeek"), state="readonly", width=19,
        )
        self.provider_box.pack(fill="x", pady=(6, 0))
        self.provider_box.bind("<<ComboboxSelected>>", self._reset_provider)
        center = tk.Frame(upper, bg=BASE)
        center.pack(side="left", fill="x", expand=True, padx=(14, 0))
        self._txt(center, "API key (not saved to disk)", bold=True).pack(anchor="w")
        self.key_entry = tk.Entry(
            center, textvariable=self.api_key, show="●",
            bg=WHITE, fg=INK, font=("Segoe UI", 11),
            relief="flat", highlightthickness=1, highlightbackground=LINE,
        )
        self.key_entry.pack(fill="x", ipady=7, pady=(6, 0))
        right = tk.Frame(upper, bg=BASE)
        right.pack(side="left", padx=(14, 0))
        self._txt(right, " ", bold=True).pack(anchor="w")
        self.load_button = self._btn(
            right, "Load models", self._load_models, primary=True,
        )
        self.load_button.pack(pady=(3, 0))
        links = tk.Frame(p, bg=BASE)
        links.pack(fill="x", pady=(9, 14))
        self._btn(links, "Get API key", self._open_key_page).pack(side="left")
        self._btn(links, "View provider prices", self._open_price_page).pack(
            side="left", padx=(9, 0),
        )
        self._txt(
            p, "Model list (search by name, company or model ID)", bold=True,
        ).pack(anchor="w")
        search = tk.Entry(
            p, textvariable=self.query, bg=WHITE, fg=INK,
            relief="flat", font=("Segoe UI", 11),
            highlightbackground=LINE, highlightthickness=1,
        )
        search.pack(fill="x", ipady=8, pady=(7, 9))
        self.query.trace_add("write", self._filter_models)
        holder = tk.Frame(p, bg=WHITE)
        holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            holder, columns=("name", "id", "input", "output"),
            show="headings", selectmode="browse",
        )
        for col, heading, width in (
            ("name", "MODEL", 270), ("id", "PROVIDER MODEL ID", 300),
            ("input", "INPUT / 1M", 110), ("output", "OUTPUT / 1M", 110),
        ):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, stretch=col in ("name", "id"),
                             minwidth=55)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(holder, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self._txt(
            p, "Displayed prices are snapshots in USD per 1M tokens, not "
               "guarantees or hard spending limits.", muted=True,
        ).pack(anchor="w", pady=(11, 2))
        self.pricing_note = self._txt(p, "", muted=True)
        self.pricing_note.pack(anchor="w")
        self.review_check = tk.Checkbutton(
            p, variable=self.reviewed,
            text="I reviewed the selected model and current input/output prices.",
            bg=BASE, fg=INK, selectcolor=BASE, activebackground=BASE,
            font=("Segoe UI", 10),
        )
        self.review_check.pack(anchor="w", pady=(10, 4))
        bottom = tk.Frame(p, bg=BASE)
        bottom.pack(fill="x")
        self.status_label = tk.Label(
            bottom, textvariable=self.status, bg=BASE, fg=MUTED,
            font=("Segoe UI", 9), anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.save_button = self._btn(
            bottom, "Use selected model", self._save, primary=True,
        )
        self.save_button.pack(side="right")

    def _open_key_page(self):
        webbrowser.open(KEY_PAGES[self.provider.get().lower()])

    def _open_price_page(self):
        webbrowser.open(PRICING_PAGES[self.provider.get().lower()])

    def _reset_provider(self, _event=None):
        if self._request_running:
            return
        self._models = ()
        self._visible = ()
        self.api_key.set("")
        self.query.set("")
        self.reviewed.set(False)
        self._filter_models()
        self.status.set("Enter your key, then click Load models.")

    def _load_models(self):
        if self._closed or self._request_running:
            return
        provider = self.provider.get().lower()
        credential = self.api_key.get().strip()
        if not 8 <= len(credential) <= 1000:
            self.status.set("Paste your own provider API key first.")
            return
        self._request_running = True
        self.load_button.configure(state="disabled")
        self.provider_box.configure(state="disabled")
        self._models = ()
        self._filter_models()
        self.status.set("Loading the current model list from " + self.provider.get() + "...")
        def work():
            try:
                models = fetch_models(provider, credential)
                self._queue.put(("ok", models))
            except ModelListError:
                self._queue.put(("error", None))
            except Exception:
                self._queue.put(("error", None))
        threading.Thread(target=work, daemon=True).start()
        self._poll_id = self.after(90, self._poll)

    def _poll(self):
        self._poll_id = None
        if self._closed:
            return
        try:
            state, result = self._queue.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(90, self._poll)
            return
        self._request_running = False
        self.load_button.configure(state="normal")
        self.provider_box.configure(state="readonly")
        if state != "ok":
            self.status.set("Could not load models. Check key, credits and network. No chat sent.")
            return
        self._models = result
        self._filter_models()
        self.status.set(str(len(result))+" models received. Choose one and confirm pricing.")

    def _filter_models(self, *_args):
        if not hasattr(self, "tree"):
            return
        q = self.query.get().casefold().strip()
        matches = tuple(m for m in self._models if (
            not q or q in m.label.casefold() or q in m.id.casefold()
        ))
        self._visible = matches[:180]
        for existing in self.tree.get_children():
            self.tree.delete(existing)
        for i, model in enumerate(self._visible):
            self.tree.insert("", "end", iid=str(i), values=(
                model.label, model.id,
                ("$"+model.input_usd_m if model.input_usd_m is not None else "Unknown"),
                ("$"+model.output_usd_m if model.output_usd_m is not None else "Unknown"),
            ))
        self.reviewed.set(False)

    def _selection_changed(self, _event=None):
        ids = self.tree.selection()
        if not ids:
            return
        item = self._visible[int(ids[0])]
        self.pricing_note.configure(text=item.price_source)
        self.reviewed.set(False)

    def _save(self):
        if self._closed or self._request_running:
            return
        choices = self.tree.selection()
        if not choices:
            self.status.set("Select a model from the list.")
            return
        model = self._visible[int(choices[0])]
        if model.input_usd_m is None or model.output_usd_m is None:
            self.status.set("Price missing. Choose a priced model; no guessed $0 rates.")
            return
        if not self.reviewed.get():
            self.status.set("Confirm that you reviewed the provider's actual prices.")
            return
        key = self.api_key.get().strip()
        if not 8 <= len(key) <= 1000:
            self.status.set("Missing API key.")
            return
        try:
            offer = create_reviewed_offer(
                provider=model.provider, model=model.id,
                input_usd=model.input_usd_m,
                output_usd=model.output_usd_m,
                date_text=date.today().isoformat(),
                reviewed=True, fixed=True,
            )
            Registry([offer])
        except (ValueError, RegistryRejected):
            self.status.set("Model metadata invalid or price unsupported.")
            return
        # Commit the credential in process RAM ONLY, no os.environ or disk.
        self.chat._offers[model.provider] = offer
        self.chat._session_keys[model.provider] = key
        self.chat.mode.set("OpenRouter" if model.provider == "openrouter" else "DeepSeek")
        self.chat._model_values()
        self.chat._select_mode()
        # Keep the main composer compact; the full identity is in this dialog.
        short = model.label if len(model.label) <= 24 else model.label[:21] + "…"
        self.chat.active_model_label.configure(text=short)
        self.chat.status.set("Model ready. Approve each online request before sending.")
        self.api_key.set("")
        self._close()

    def _close(self):
        if self._closed:
            return
        self._closed = True
        self.api_key.set("")
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        self.grab_release()
        self.destroy()
