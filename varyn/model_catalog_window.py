"""17S-43: separate owner-consented model ID catalogue window.

READ-ONLY GET /models; it does not prove the API key can run inference.
Never assumes listed models are free, supported for a user's account or
have fixed upstream identities. Never stores or shows OS API key values.
"""
from datetime import date
import hashlib
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk

from varyn.gateway_chat import KEY_ENVS
from varyn.model_discovery import (
    PINNED_MODEL_URLS, DiscoveryRejected, discover_once, safe_model_id,
)


class ModelCatalogWindow(tk.Toplevel):
    def __init__(self, center, *, transport=None):
        super().__init__(center)
        self._center = center
        self._owner = center._owner
        self._transport = transport
        self._closed = False
        self._running = False
        self._attempted = False
        self._poll_id = None
        self._results = queue.Queue()
        self._ids = ()
        self._listed_provider = None
        self.title("VARYN 17S-43 | Official API model ID discovery")
        self.geometry("640x490")
        self.minsize(460, 360)
        self.transient(center)
        initial = center.provider.get()
        if initial == "fake":
            initial = "openrouter"
        self.provider = tk.StringVar(master=self, value=initial)
        self.allow_network = tk.BooleanVar(master=self, value=False)
        self.authorize_upstream = tk.BooleanVar(master=self, value=False)
        self.status = tk.StringVar(
            master=self,
            value="NO NETWORK. This queries model IDs, NOT pricing or account eligibility.",
        )
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._dismiss)

    def _build(self):
        shell = ttk.Frame(self, padding=12)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Official provider GET /models, opt-in once per window").pack(anchor="w")
        ttk.Label(
            shell, wraplength=600,
            text="A model ID appearing here does NOT verify it is free, available to "
                 "your account, billable at any particular rate, or the actual "
                 "upstream model. A listing alone does NOT validate API credentials. "
                 "No prompt/chat or memory is sent; API key comes from Windows environment.",
        ).pack(anchor="w", pady=6)
        row = ttk.Frame(shell)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Provider").pack(side="left")
        ttk.Combobox(
            row, textvariable=self.provider,
            values=("openrouter", "deepseek", "9router"),
            state="readonly", width=17,
        ).pack(side="left", padx=9)
        ttk.Label(shell, text="Only fixed, pre-audited endpoints are supported.").pack(anchor="w")
        ttk.Checkbutton(
            shell, text="Allow ONE read-only model-list request (OFF by default)",
            variable=self.allow_network,
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            shell, text="9Router: I authorize this local gateway's upstream account use",
            variable=self.authorize_upstream,
        ).pack(anchor="w", pady=4)
        self.discover_button = ttk.Button(
            shell, text="Review exact GET /models & request ONCE",
            command=self._request_models,
        )
        self.discover_button.pack(anchor="w", pady=6)
        ttk.Label(shell, textvariable=self.status, wraplength=600).pack(
            anchor="w", pady=5,
        )
        ttk.Label(
            shell, text="Sanitized provider-CLAIMED model IDs (maximum 60 shown):",
        ).pack(anchor="w")
        self.models = tk.Listbox(shell, height=9, selectmode="browse")
        self.models.pack(fill="both", expand=True, pady=3)
        row = ttk.Frame(shell)
        row.pack(fill="x", pady=6)
        ttk.Button(
            row, text="Use selected ID (pricing MUST be reviewed separately)",
            command=self._use_selected,
        ).pack(side="left")
        ttk.Button(row, text="Close & discard IDs", command=self._dismiss).pack(
            side="right",
        )

    def _ready(self):
        return (
            not self._closed and not self._owner._closing and
            not self._owner._busy and not self._center._closed and
            not self._center._running
        )

    def _request_models(self):
        if not self._ready() or self._running or self._attempted:
            return
        provider = self.provider.get()
        if provider not in PINNED_MODEL_URLS:
            self.status.set("BLOCKED: invalid provider")
            return
        if not self._owner._universal_model_live_capability:
            self.status.set("BLOCKED: desktop gateway does not permit live network")
            return
        if not self.allow_network.get():
            self.status.set("BLOCKED: explicit read-only network permission required")
            return
        upstream = self.authorize_upstream.get()
        if provider == "9router" and not upstream:
            self.status.set("BLOCKED: 9Router upstream-use consent required")
            return
        key_name = KEY_ENVS[provider]
        # Only look at whether the key exists, never copy/log its content.
        if not os.environ.get(key_name, "").strip():
            self.status.set("BLOCKED: OS environment variable " + key_name + " missing")
            return
        snapshot = (provider, self.allow_network.get(), upstream)
        packet = json.dumps({
            "format": "varyn.owner_model_listing_review.v1",
            "method": "GET", "url": PINNED_MODEL_URLS[provider],
            "selected_provider": provider, "key_environment_variable": key_name,
            "key_value_included": False, "chat_prompt_included": False,
            "pricing_proved": False, "account_inference_rights_verified": False,
            "native_consumer_memory_sync": False,
            "one_request_only": True,
        }, sort_keys=True, indent=2)
        digest = hashlib.sha256(packet.encode("utf-8")).hexdigest()
        accepted = self._owner._review_scrollable_manual_text(
            title="VARYN | exact model-catalog GET review",
            heading="ONE GET /models attempt; NOT an inference or consumer sync",
            digest=digest, content=packet,
            warning="This network query may contact a remote provider. "
                    "No pricing or account access is guaranteed. 9Router "
                    "may use upstream subscriptions; only owner-authorized access.",
            approve_label="Approve ONE model listing request",
        )
        if not accepted or not self._ready():
            self.status.set("Denied or closed; no GET sent")
            return
        if snapshot != (self.provider.get(), self.allow_network.get(),
                        self.authorize_upstream.get()):
            self.status.set("BLOCKED: model listing changed after owner review")
            return
        # Fresh approval applies to this one GET only, not a later inference.
        self.allow_network.set(False)
        self.authorize_upstream.set(False)
        self._attempted = True
        self._running = True
        self.discover_button.configure(state="disabled")
        self.status.set("ONE GET requested. No fallback or automatic retry.")
        self._listed_provider = None
        self._ids = ()
        self.models.delete(0, "end")
        thread = threading.Thread(
            target=ModelCatalogWindow._worker,
            args=(provider, upstream, self._transport, self._results),
            daemon=True,
        )
        thread.start()
        self._poll_id = self.after(75, self._poll)

    @staticmethod
    def _worker(provider, upstream, transport, output):
        try:
            result = discover_once(
                provider, owner_approved=True, network_enabled=True,
                authorized_upstream=upstream, transport=transport,
            )
            output.put(("ok", result))
        except BaseException:
            # Provider response bodies/exception text may contain secrets.
            output.put(("error", None))

    def _poll(self):
        self._poll_id = None
        if not self._ready():
            if not self._closed:
                self._dismiss()
            return
        try:
            kind, result = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(75, self._poll)
            return
        self._running = False
        if kind != "ok":
            self.status.set("GET failed or rejected. No retries. Credentials were not logged.")
            return
        ids = tuple(result["ids"])
        provider = result["provider"]
        if not ids:
            self.status.set("GET returned no usable model IDs. NOT provider-account proof.")
            return
        self._ids = ids
        self._listed_provider = provider
        for item in ids:
            self.models.insert("end", item)
        self.status.set(
            str(len(ids)) + " IDs listed from " + provider + " (of " +
            str(result["total_sanitized_model_ids"]) + " sanitized). "
            "UNTRUSTED catalogue. No price, availability or account eligibility verified."
        )

    def _use_selected(self):
        if not self._ready() or self._running:
            return
        positions = self.models.curselection()
        if len(positions) != 1 or self._listed_provider is None:
            self.status.set("Select a discovered model ID first")
            return
        index = positions[0]
        if not 0 <= index < len(self._ids):
            self.status.set("Invalid model selection")
            return
        identifier = self._ids[index]
        if not safe_model_id(identifier):
            self.status.set("Invalid model ID from provider")
            return
        center = self._center
        center.provider.set(self._listed_provider)
        center.model.set(identifier)
        # A provider's list NEVER makes any model a verified/free price.
        center.input_price.set("")
        center.output_price.set("")
        center.price_date.set(date.today().isoformat())
        center.reviewed.set(False)
        center.fixed.set(False)
        center.network.set(False)
        center.upstream.set(False)
        center.status.set(
            "Discovered model ID staged, NOT registered for execution. "
            "Owner MUST check both real prices, review route, then Add quote. "
            "No account inference access proven."
        )
        self._dismiss()

    def _dismiss(self):
        if self._closed:
            return
        self._closed = True
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        self._ids = ()
        self._listed_provider = None
        if getattr(self._center, "_catalog_window", None) is self:
            self._center._catalog_window = None
            self._center._catalog_lock = False
        self.destroy()
        # Closing cannot undo an already dispatched GET.
