"""17S-40: owner-operated cost-quote review and model API control window.

Quotes are operator assertions, NOT fetched/verifiable market prices.
No API keys are entered, shown, or written here. No persistent memory.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from varyn.gateway_chat import KEY_ENVS, SafeProviderHTTPError
from varyn.model_catalog_window import ModelCatalogWindow
from varyn.provider_readiness import (
    readiness, local_observation, receipt_json, save_new, ReadinessRejected,
)
from varyn.model_registry import Offer, Registry, RegistryRejected
from varyn.providers import ProviderError
from varyn.universal_gateway import UniversalGateway
from varyn.usage_budget import BudgetExceeded, UsageBudget

PROVIDERS = ("fake", "openrouter", "deepseek", "9router")
_TASK = "SYNTHETIC: classify a fictional widget as a harmless test."
_MAX_QUOTES = 12


class ModelCenterRejected(ValueError):
    """Reject without echoing untrusted model/user content."""


def price_to_micro(value):
    """Owner-entered USD per million tokens, exact to six decimals."""
    if type(value) is not str or not 1 <= len(value) <= 24:
        raise ModelCenterRejected("Invalid price field")
    try:
        d = Decimal(value)
        micro = d * 1000000
        if not d.is_finite() or not 0 <= d <= 10000 or micro != micro.to_integral_value():
            raise ModelCenterRejected("Price must be 0..10000 USD, <=6 decimals")
        return int(micro)
    except InvalidOperation as exc:
        raise ModelCenterRejected("Invalid price field") from exc


def create_reviewed_offer(*, provider, model, input_usd, output_usd,
                          date_text, reviewed, fixed):
    if reviewed is not True or fixed is not True:
        raise ModelCenterRejected("Explicit price and route review required")
    return Offer(
        provider, model,
        price_to_micro(input_usd), price_to_micro(output_usd),
        date_text, owner_reviewed=True, route_fixed=True, enabled=True,
    )


def build_exact_preview(offer, task, input_estimate, output_limit, estimated):
    if type(offer) is not Offer or type(task) is not str:
        raise ModelCenterRejected("Invalid reviewed offer")
    if type(estimated) is not int or estimated < 0:
        raise ModelCenterRejected("Invalid estimated cost")
    data = {
        "format": "varyn.model_center_request.v1",
        "provider": offer.provider, "model": offer.model,
        "task": task,
        "input_tokens_ESTIMATED_NOT_ACTUAL": input_estimate,
        "max_output_tokens": output_limit,
        "maximum_ESTIMATED_USD": str(Decimal(estimated) / 1000000),
        "operator_price_date": offer.price_date,
        "quote_owner_reviewed": offer.owner_reviewed,
        "provider_price_independently_verified": False,
        "native_consumer_memory_sync": False,
        "actual_bill_hard_cap": False,
    }
    if offer.provider == "9router":
        data["warning"] = (
            "9Router is a localhost gateway and may switch UPSTREAM "
            "models/credentials despite the locally selected route."
        )
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


class ModelControlCenter(tk.Toplevel):
    def __init__(self, owner, *, budget=None, transport=None):
        super().__init__(owner)
        self._owner = owner
        self._budget = budget if budget is not None else UsageBudget(
            max_requests=6, max_reserved_output_tokens=6144,
        )
        self._transport = transport
        self._offers = []
        self._running = False
        self._closed = False
        self._results = queue.Queue()
        self._poll_id = None
        self._active_offer = None
        self._last_receipt = None
        self._catalog_window = None
        self._catalog_lock = False
        self.title("VARYN 17S-40 | Model Control Center")
        self.geometry("760x640")
        self.minsize(540, 440)
        self.transient(owner)
        self.provider = tk.StringVar(master=self, value="fake")
        self.model = tk.StringVar(master=self, value="fake-test")
        self.input_price = tk.StringVar(master=self, value="0")
        self.output_price = tk.StringVar(master=self, value="0")
        self.price_date = tk.StringVar(master=self, value=date.today().isoformat())
        self.reviewed = tk.BooleanVar(master=self, value=False)
        self.fixed = tk.BooleanVar(master=self, value=False)
        self.network = tk.BooleanVar(master=self, value=False)
        self.upstream = tk.BooleanVar(master=self, value=False)
        self.selection = tk.StringVar(master=self, value="auto")
        self.input_tokens = tk.StringVar(master=self, value="128")
        self.output_tokens = tk.StringVar(master=self, value="128")
        self.ceiling = tk.StringVar(master=self, value="0")
        self.status = tk.StringVar(
            master=self, value="OFFLINE. Enter OWN verified quote; no live calls."
        )
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._dismiss)

    def _build(self):
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(root, orient="vertical")
        scroll.pack(side="right", fill="y")
        canvas = tk.Canvas(root, highlightthickness=0, borderwidth=0)
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.configure(command=canvas.yview)
        shell = ttk.Frame(canvas, padding=10)
        window = canvas.create_window((0, 0), window=shell, anchor="nw")
        shell.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(
                -1 if event.delta > 0 else 1, "units",
            ),
        )
        ttk.Label(shell, text="17S-40 | Owner-reviewed model registry (RAM only)").pack(anchor="w")
        ttk.Label(
            shell, wraplength=695,
            text="No provider price feed, no unlimited-free guarantee. "
                 "Only fictional SYNTHETIC: requests. Billing cap NOT enforced. "
                 "Never enter an API key here; use your own OS environment.",
        ).pack(anchor="w", pady=(2, 7))
        quote = ttk.LabelFrame(shell, text="1. Register exact model and owner-reviewed prices")
        quote.pack(fill="x", pady=(0, 6))
        line = ttk.Frame(quote)
        line.pack(fill="x", padx=6, pady=4)
        ttk.Label(line, text="Provider").pack(side="left")
        ttk.Combobox(line, textvariable=self.provider, state="readonly",
                     values=PROVIDERS, width=12).pack(side="left", padx=5)
        ttk.Label(line, text="Model ID").pack(side="left")
        ttk.Entry(line, textvariable=self.model, width=27).pack(side="left", padx=5)
        line = ttk.Frame(quote)
        line.pack(fill="x", padx=6, pady=4)
        ttk.Label(line, text="Input USD / 1M").pack(side="left")
        ttk.Entry(line, textvariable=self.input_price, width=10).pack(side="left", padx=3)
        ttk.Label(line, text="Output USD / 1M").pack(side="left")
        ttk.Entry(line, textvariable=self.output_price, width=10).pack(side="left", padx=3)
        ttk.Label(line, text="Quote date").pack(side="left")
        ttk.Entry(line, textvariable=self.price_date, width=12).pack(side="left", padx=3)
        ttk.Checkbutton(
            quote, text="I personally checked BOTH prices (not a provider guarantee)",
            variable=self.reviewed,
        ).pack(anchor="w", padx=6)
        ttk.Checkbutton(
            quote, text="I reviewed the fixed local route (upstream 9Router may differ)",
            variable=self.fixed,
        ).pack(anchor="w", padx=6)
        buttons = ttk.Frame(quote)
        buttons.pack(fill="x", padx=6, pady=4)
        ttk.Button(buttons, text="Add reviewed quote", command=self._add).pack(side="left")
        ttk.Button(buttons, text="Clear quotes (RAM)", command=self._clear).pack(
            side="left", padx=(6, 0),
        )
        self.listbox = tk.Listbox(quote, height=4)
        self.listbox.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(
            quote,
            text="17S-43 | Discover model IDs (official GET /models)",
            command=self._open_catalog,
        ).pack(anchor="w", padx=6, pady=(0, 6))

        control = ttk.LabelFrame(shell, text="2. Inspect the selected model and request")
        control.pack(fill="x", pady=(0, 6))
        line = ttk.Frame(control)
        line.pack(fill="x", padx=6, pady=4)
        ttk.Label(line, text="Selection").pack(side="left")
        self.combo = ttk.Combobox(
            line, textvariable=self.selection, state="readonly",
            values=("auto",), width=24,
        )
        self.combo.pack(side="left", padx=5)
        for text, var, width in (
            ("Input estimate", self.input_tokens, 7),
            ("Max output", self.output_tokens, 7),
            ("Est. ceiling USD", self.ceiling, 9),
        ):
            ttk.Label(line, text=text).pack(side="left")
            ttk.Entry(line, textvariable=var, width=width).pack(side="left", padx=3)
        ttk.Checkbutton(
            control, text="Allow one approved live model API request (OFF by default)",
            variable=self.network,
        ).pack(anchor="w", padx=6)
        ttk.Checkbutton(
            control, text="9Router ONLY: I verified and authorize its upstream account use",
            variable=self.upstream,
        ).pack(anchor="w", padx=6)
        ttk.Label(control, text="Fictional task to transmit; no local memory included").pack(
            anchor="w", padx=6,
        )
        self.task = tk.Text(control, height=3, wrap="word")
        self.task.pack(fill="x", padx=6, pady=4)
        self.task.insert("1.0", _TASK)
        buttons = ttk.Frame(control)
        buttons.pack(fill="x", padx=6, pady=4)
        ttk.Button(
            buttons, text="Preview cheapest eligible route (NO network)",
            command=self._preview,
        ).pack(side="left")
        self.send_button = ttk.Button(
            buttons, text="Review exact request & send ONCE",
            command=self._send,
        )
        self.send_button.pack(side="left", padx=(6, 0))
        readiness_buttons = ttk.Frame(control)
        readiness_buttons.pack(fill="x", padx=6, pady=(0, 5))
        ttk.Button(
            readiness_buttons, text="17S-41 | Check readiness (NO network)",
            command=self._check_readiness,
        ).pack(side="left")
        self.receipt_button = ttk.Button(
            readiness_buttons,
            text="17S-41 | Review & save content-free receipt",
            command=self._save_receipt, state="disabled",
        )
        self.receipt_button.pack(side="left", padx=(7, 0))
        ttk.Label(shell, textvariable=self.status, wraplength=710).pack(
            anchor="w", pady=(4, 6),
        )
        self.answer = tk.Text(shell, height=7, wrap="word")
        self.answer.pack(fill="both", expand=True)
        self.answer.insert("1.0", "No model was called.")
        self.answer.configure(state="disabled")
        ttk.Button(shell, text="Close and discard RAM quotes", command=self._dismiss).pack(
            anchor="e", pady=(5, 0),
        )

    def _allowed(self):
        return (not self._closed and not self._owner._closing and
                not self._owner._busy and not self._catalog_lock)

    def _open_catalog(self):
        if not self._allowed() or self._running:
            return
        # Lock this model center while its separately reviewed GET is pending.
        self._catalog_lock = True
        try:
            self._catalog_window = ModelCatalogWindow(self)
        except BaseException:
            self._catalog_lock = False
            self._catalog_window = None
            raise

    def _refresh_options(self):
        items = ["auto"] + [x.provider + ":" + x.model for x in self._offers]
        self.combo.configure(values=tuple(items))
        self.listbox.delete(0, "end")
        for x in self._offers:
            self.listbox.insert("end", x.provider + " | " + x.model +
                                " | owner quote " + x.price_date)
        if self.selection.get() not in items:
            self.selection.set("auto")

    def _add(self):
        if not self._allowed() or self._running:
            return
        try:
            entry = create_reviewed_offer(
                provider=self.provider.get(), model=self.model.get(),
                input_usd=self.input_price.get(), output_usd=self.output_price.get(),
                date_text=self.price_date.get(), reviewed=self.reviewed.get(),
                fixed=self.fixed.get(),
            )
            if len(self._offers) >= _MAX_QUOTES:
                raise ModelCenterRejected("Maximum 12 RAM quotes")
            Registry(self._offers + [entry])
            self._offers.append(entry)
            self.reviewed.set(False)
            self.fixed.set(False)
            self._refresh_options()
            self.status.set("Quote added to RAM. Owner assertions, not verified prices.")
        except (ValueError, RegistryRejected, ModelCenterRejected):
            self.status.set("BLOCKED: invalid, duplicate or unreviewed model/price.")

    def _clear(self):
        if not self._allowed() or self._running:
            return
        self._offers.clear()
        self._last_receipt = None
        self.receipt_button.configure(state="disabled")
        self._refresh_options()
        self.network.set(False)
        self.upstream.set(False)
        self.status.set("Quotes cleared; network and upstream opt-in reset OFF.")

    def _plan(self):
        if not self._offers:
            raise ModelCenterRejected("Add at least one owner-reviewed quote")
        provider_model = self.selection.get()
        if provider_model != "auto":
            exact = [x for x in self._offers if x.provider + ":" + x.model == provider_model]
            if len(exact) != 1:
                raise ModelCenterRejected("Invalid explicit model selection")
            candidates = Registry(exact)
        else:
            candidates = Registry(self._offers)
        input_estimate = int(self.input_tokens.get())
        output_limit = int(self.output_tokens.get())
        ceiling_micro = price_to_micro(self.ceiling.get())
        chosen, estimated = candidates.choose(
            input_estimate=input_estimate, output_limit=output_limit,
            ceiling_micro_usd=ceiling_micro, today=date.today(),
        )
        task = self.task.get("1.0", "end-1c")
        if not task.startswith("SYNTHETIC:") or len(task) > 4000:
            raise ModelCenterRejected("Only bounded synthetic tasks")
        return chosen, estimated, task, input_estimate, output_limit, ceiling_micro

    def _preview(self):
        if not self._allowed() or self._running:
            return
        try:
            chosen, estimated, task, input_estimate, out, ceiling = self._plan()
            message = (
                "PREVIEW ONLY: " + chosen.provider + "/" + chosen.model +
                " | est. $" + str(Decimal(estimated) / 1000000) +
                " | ceiling est. $" + str(Decimal(ceiling) / 1000000) +
                " | not a billing cap | no network call."
            )
            self.status.set(message)
        except (ValueError, RegistryRejected, ModelCenterRejected):
            self.status.set("BLOCKED: no fresh approved quote within estimate ceiling.")

    def _check_readiness(self):
        if not self._allowed() or self._running:
            return
        try:
            chosen, _amount, _task, _inp, _out, _ceiling = self._plan()
            state = readiness(
                chosen,
                live_capability=self._owner._universal_model_live_capability,
                enabled_network=self.network.get(),
                upstream_authorized=self.upstream.get(),
            )
            if chosen.provider == "fake":
                self.status.set(
                    "FAKE only: simulated request; no API endpoint or provider key."
                )
            elif state["ready_for_live_attempt"]:
                self.status.set(
                    "READY FOR ONE OWNER-APPROVED ATTEMPT, NOT CONNECTED/VERIFIED: "
                    + chosen.provider + "/" + chosen.model + "; "
                    + state["key_env_name"] + " is configured. "
                    "No network call was made."
                )
            else:
                self.status.set(
                    "NOT READY (NO network): " + ", ".join(state["missing"])
                    + "; expected env " + state["key_env_name"] +
                    "; credential " + (
                        "present" if state["key_present"] else "missing"
                    ) + ". No request dispatched."
                )
        except (ValueError, RegistryRejected, ModelCenterRejected,
                ReadinessRejected):
            self.status.set(
                "BLOCKED: register and select a fresh reviewed model quote first."
            )

    def _save_receipt(self):
        if not self._allowed() or self._running or self._last_receipt is None:
            return
        try:
            receipt = self._last_receipt
            text = receipt_json(receipt)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            confirmed = self._owner._review_scrollable_manual_text(
                title="VARYN | Save local model observation (metadata only)",
                heading="Adapter parsed a response; provider account NOT attested",
                digest=digest, content=text,
                warning="Only locally observed metadata, no prompt, reply, "
                        "API key, token, or provider-billing proof. "
                        "This is NOT native ChatGPT/Claude/Gemini memory sync. "
                        "New file only; user must explicitly choose path.",
                approve_label="Approve metadata-only NEW receipt",
            )
            if not confirmed or not self._allowed():
                self.status.set("Receipt review declined; no file written.")
                return
            if self._running or self._last_receipt is not receipt:
                self.status.set("BLOCKED: observation changed during review.")
                return
            target = filedialog.asksaveasfilename(
                parent=self,
                title="Save NEW metadata-only model observation JSON",
                defaultextension=".json",
                filetypes=[("Local observation", "*.json")],
            )
            if not target or not self._allowed() or self._last_receipt is not receipt:
                self.status.set("Receipt file selection cancelled.")
                return
            save_new(target, receipt)
            self.status.set(
                "Saved a NEW metadata-only observation file. "
                "Provider authenticity and actual billing remain unverified."
            )
        except (ReadinessRejected, OSError, ValueError):
            self.status.set(
                "BLOCKED: invalid receipt, missing path or existing file. "
                "No overwrite allowed."
            )

    def _send(self):
        if not self._allowed() or self._running:
            return
        try:
            selection = self._plan()
            chosen, estimated, task, input_estimate, out, ceiling = selection
            live = chosen.provider != "fake"
            if live and (not self.network.get() or
                         not self._owner._universal_model_live_capability):
                raise PermissionError("Network disabled in this window or desktop")
            if chosen.provider == "9router" and not self.upstream.get():
                raise PermissionError("Local 9Router upstream authorization missing")
            snapshot = (
                tuple(self._offers), self.selection.get(), self.task.get("1.0", "end-1c"),
                self.input_tokens.get(), self.output_tokens.get(), self.ceiling.get(),
                self.network.get(), self.upstream.get(),
            )
            content = build_exact_preview(chosen, task, input_estimate, out, estimated)
            digest = hashlib.sha256(content.encode()).hexdigest()
            approved = self._owner._review_scrollable_manual_text(
                title="VARYN | EXACT model API request review",
                heading="One NEW " + chosen.provider + " model request, NOT consumer app sync",
                digest=digest,
                content=content,
                warning="Potential REAL BILLING; quote/estimated tokens are NOT caps. "
                        "For 9Router, upstream provider may change. "
                        "No provider account history, clipboard or memory sync. "
                        "No retry or fallback at VARYN layer.",
                approve_label="Approve ONE exact model request",
            )
            if not approved or not self._allowed():
                self.status.set("Request declined. No dispatch or reserved quota.")
                return
            new_snapshot = (
                tuple(self._offers), self.selection.get(), self.task.get("1.0", "end-1c"),
                self.input_tokens.get(), self.output_tokens.get(), self.ceiling.get(),
                self.network.get(), self.upstream.get(),
            )
            if new_snapshot != snapshot or self._plan() != selection:
                raise ModelCenterRejected("Request changed during approval")
            self.network.set(False)
            self.upstream.set(False)
            self._last_receipt = None
            self.receipt_button.configure(state="disabled")
            self._active_offer = chosen
            self._running = True
            self.send_button.configure(state="disabled")
            self.status.set("Approved one request. Awaiting result; no automatic retry.")
            registry = Registry([chosen])
            gateway = UniversalGateway(
                registry, allow_network=live, budget=self._budget,
                transport=self._transport,
            )
            thread = threading.Thread(
                target=ModelControlCenter._worker,
                args=(gateway, selection, chosen.provider == "9router",
                      self._results),
                daemon=True,
            )
            thread.start()
            self._poll_id = self.after(80, self._poll)
        except (ValueError, PermissionError, RegistryRejected, ModelCenterRejected):
            self.status.set(
                "BLOCKED: consent, quote, budget preview or request changed. "
                "No dispatch."
            )

    @staticmethod
    def _worker(gateway, selection, upstream_approved, output_queue):
        chosen, estimated, task, input_estimate, out, ceiling = selection
        try:
            result = gateway.generate(
                task, input_estimate=input_estimate, max_output_tokens=out,
                ceiling_micro_usd=ceiling, provider=chosen.provider,
                approve_request=True, authorized_upstream=upstream_approved,
            )
            output_queue.put(("ok", result))
        except SafeProviderHTTPError as exc:
            output_queue.put(("http_error", exc.category))
        except (ProviderError, RegistryRejected, BudgetExceeded,
                PermissionError, ValueError, OSError):
            output_queue.put(("error", None))
        except BaseException:
            output_queue.put(("error", None))

    def _poll(self):
        self._poll_id = None
        if self._closed or self._owner._closing:
            return
        try:
            kind, data = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(80, self._poll)
            return
        self._running = False
        self.send_button.configure(state="normal")
        if kind == "ok":
            if (data["reply"].provider != "fake" and
                    self._transport is None and self._active_offer is not None):
                try:
                    self._last_receipt = local_observation(
                        data, quoted_offer=self._active_offer,
                    )
                    self.receipt_button.configure(state="normal")
                except ReadinessRejected:
                    self._last_receipt = None
            self.answer.configure(state="normal")
            self.answer.delete("1.0", "end")
            self.answer.insert("1.0", data["reply"].text)
            self.answer.configure(state="disabled")
            claimed = data.get("provider_reported_model")
            claimed_text = (
                "Provider-claimed model label: " + claimed
                if claimed is not None else
                "Provider returned no usable model label"
            )
            mismatch = data.get("provider_reported_model_matches_selected")
            if mismatch is False:
                claimed_text += "; MODEL LABEL DIFFERS FROM SELECTION"
            self.status.set(
                "Completed: selected " + data["reply"].provider + "/" +
                data["reply"].model + ". " + claimed_text +
                ". Untrusted answer RAM-only; model origin and actual billing "
                "NOT independently verified."
            )
        elif kind == "http_error":
            # Category comes only from SafeProviderHTTPError's static allowlist.
            # Never display remote error body, headers, or untrusted reason.
            hints = {
                "bad_request": "HTTP 400: request or parameters refused",
                "authentication": "HTTP 401: check API key locally",
                "billing": "HTTP 402: check provider billing or credits",
                "access_denied": "HTTP 403: check account/model permission",
                "model_or_endpoint": "HTTP 404: check selected model ID",
                "timeout": "HTTP 408: provider or intermediary timed out",
                "conflict": "HTTP 409: provider reported a conflict",
                "invalid_parameters": "HTTP 422: provider rejected parameters",
                "rate_limited": "HTTP 429: rate limit or capacity restriction",
                "server_error": "HTTP 5xx: provider/intermediary server failure",
                "other_http": "Other provider/intermediary HTTP error",
            }
            self.status.set(
                hints.get(data, hints["other_http"]) +
                ". No response body exposed. Budget reservation retained; "
                "actual billing unknown. No automatic retry."
            )
        else:
            self.status.set(
                "Provider failed or response denied. Budget reservation retained; "
                "actual billing unknown. No retry attempted."
            )

    def _dismiss(self):
        if self._closed:
            return
        self._closed = True
        catalog = self._catalog_window
        if catalog is not None and catalog.winfo_exists():
            catalog._dismiss()
        self._catalog_window = None
        self._catalog_lock = False
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        if getattr(self._owner, "_model_center", None) is self:
            self._owner._model_center = None
        self._offers.clear()
        self._last_receipt = None
        self._active_offer = None
        self.destroy()
        # In-flight requests, if any, cannot be unsent; never redispatch.
