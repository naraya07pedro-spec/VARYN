"""VARYN Tkinter MVP: offline chat and explicitly confirmed optional live calls.

Run: python -m varyn.desktop
The UI never touches Tk widgets from worker threads, never reads local memory,
and never persists a transcript. Real providers require account API credentials.
"""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from varyn.desktop_controller import DesktopController, DEFAULT_MODELS, PROVIDERS
from varyn.providers import ProviderError
from varyn.desktop_lifecycle import DesktopRequestState
from varyn.desktop_approval import DesktopApprovalController
from varyn.agent_runtime import AgentRejected, AgentLimitReached
from varyn.tool_protocol import stage_tool_intent


class VarynDesktop(tk.Tk):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller or DesktopController(allow_live_providers=True)
        self.title("VARYN  |  Local AI Workspace (Opt-in Live MVP)")
        self.geometry("760x650")
        self.minsize(540, 480)
        self.configure(bg="#111827")
        self.provider = tk.StringVar(value="fake")
        self.model = tk.StringVar(value="fake-test")
        self.consent_network = tk.BooleanVar(value=False)
        self.consent_context = tk.BooleanVar(value=False)
        self.status_line = tk.StringVar(value="")
        self._results = queue.Queue()
        self._lifecycle = DesktopRequestState()
        self._approval = DesktopApprovalController()
        self._busy = False
        self._closing = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._refresh_status()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("V.TFrame", background="#111827")
        style.configure("V.TLabel", background="#111827", foreground="#e5e7eb",
                        font=("Segoe UI", 10))
        style.configure("Title.V.TLabel", background="#111827",
                        foreground="#f9fafb", font=("Segoe UI", 17, "bold"))
        outer = ttk.Frame(self, style="V.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="VARYN", style="Title.V.TLabel").pack(anchor="w")
        ttk.Label(
            outer, text="LOCAL-FIRST  |  OFFLINE BY DEFAULT  |  API LIVE IS OPT-IN",
            style="V.TLabel",
        ).pack(anchor="w", pady=(0, 14))
        settings = ttk.Frame(outer, style="V.TFrame")
        settings.pack(fill="x", pady=(0, 8))
        ttk.Label(settings, text="Provider", style="V.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        provider_menu = ttk.Combobox(
            settings, values=PROVIDERS, state="readonly", textvariable=self.provider,
            width=15,
        )
        provider_menu.grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        provider_menu.bind("<<ComboboxSelected>>", self._provider_changed)
        ttk.Label(settings, text="Model (exact provider model ID)", style="V.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Entry(settings, textvariable=self.model, width=27).grid(
            row=1, column=1, sticky="we", pady=4
        )
        settings.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            outer, text="Allow a confirmed API request to selected provider",
            variable=self.consent_network, command=self._permissions_changed,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(
            outer, text="Allow context sharing (not loaded automatically)",
            variable=self.consent_context, command=self._permissions_changed,
        ).pack(anchor="w", pady=(2, 8))
        ttk.Label(outer, textvariable=self.status_line, style="V.TLabel").pack(
            anchor="w", pady=(0, 10)
        )
        self.transcript = tk.Text(
            outer, height=14, wrap="word", bg="#1f2937", fg="#f3f4f6",
            insertbackground="#f9fafb", relief="flat", padx=12, pady=12,
            state="disabled", font=("Segoe UI", 10),
        )
        self.transcript.pack(fill="both", expand=True)
        ttk.Label(outer, text="Message (synthetic data only)", style="V.TLabel").pack(
            anchor="w", pady=(10, 2)
        )
        self.prompt = tk.Text(
            outer, height=3, wrap="word", bg="#f9fafb", fg="#111827",
            relief="flat", padx=8, pady=6, font=("Segoe UI", 10),
        )
        self.prompt.pack(fill="x")
        controls = ttk.Frame(outer, style="V.TFrame")
        controls.pack(fill="x", pady=10)
        self.send_button = ttk.Button(controls, text="Send", command=self._send)
        self.send_button.pack(side="left")
        ttk.Button(controls, text="Clear RAM chat", command=self._clear).pack(
            side="left", padx=8
        )
        ttk.Button(controls, text="Discard pending reply", command=self._discard).pack(
            side="left"
        )
        ttk.Button(
            controls, text="Demo agent approval", command=self._agent_demo,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            outer, text="Review structured tool intent (untrusted JSON)",
            command=self._review_tool_intent,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            outer, text="History and usage counters reset on restart. Live APIs may bill.",
            style="V.TLabel",
        ).pack(anchor="w")
        self._append(
            "SYSTEM", "Only fake mode is free and offline. Live mode requires an "
            "API key set outside this app, network consent, and confirmation "
            "of each individual request. Do not input private data."
        )

    def _provider_changed(self, _event=None):
        self.model.set(DEFAULT_MODELS[self.provider.get()])
        self._refresh_status()

    def _permissions_changed(self):
        self.controller.set_network_consent(self.consent_network.get())
        self.controller.set_context_consent(self.consent_context.get())
        self._refresh_status()

    def _refresh_status(self):
        state = self.controller.status()
        self.status_line.set(
            f"{'LIVE ENABLED' if state['network_enabled'] else 'NETWORK OFF'}"
            f" | Requests {state['requests_used']}/{state['requests_limit']}"
            f" | Reserved output {state['output_tokens_reserved']}/"
            f"{state['output_tokens_limit']} tokens"
            f"{' | REQUEST IN FLIGHT' if self._busy else ''}"
        )

    def _append(self, who, message):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{who}: {message}\n\n")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _send(self):
        if self._busy:
            return
        question = self.prompt.get("1.0", "end-1c")
        selected_provider = self.provider.get()
        selected_model = self.model.get()
        if not question.strip():
            self._append("NOTICE", "Type a message before sending")
            return
        live = selected_provider != "fake"
        if live:
            if not self.consent_network.get():
                self._append("NOTICE", "Enable the network checkbox first")
                return
            if not selected_model.strip():
                self._append("NOTICE", "Enter the exact provider model ID first")
                return
            # No context is attached by UI; consent alone never loads memory.
            if not messagebox.askyesno(
                "Confirm external API call",
                f"Send this typed message to {selected_provider} using "
                f"model {selected_model}?\n\n"
                "This transmits your text to an external API and may cost money. "
                "No local memory is attached.",
                parent=self,
            ):
                return
        request_id = self._lifecycle.begin()
        self._busy = True
        self.send_button.configure(state="disabled")
        self._refresh_status()
        worker = threading.Thread(
            target=self._send_worker,
            args=(request_id, question, selected_provider, selected_model, live),
            daemon=True,
        )
        worker.start()
        self.after(75, self._poll_result)

    def _send_worker(self, request_id, question, provider, model, live):
        # No Tk widget access from the worker thread.
        try:
            result = self.controller.send(
                question, provider=provider, model=model,
                confirm_live_request=live,
            )
            self._results.put((request_id, "ok", question, result.answer))
        except (ValueError, PermissionError, ProviderError) as error:
            self._results.put((request_id, "error", "", str(error)))
        except Exception:
            # Don't echo potentially sensitive raw exception details in UI.
            self._results.put((request_id, "error", "", "Request failed; retry not automatic"))

    def _poll_result(self):
        if self._closing:
            return
        try:
            request_id, kind, question, message = self._results.get_nowait()
        except queue.Empty:
            self.after(75, self._poll_result)
            return
        if not self._lifecycle.finish(request_id):
            if self._lifecycle.busy:
                self.after(75, self._poll_result)
            return
        if kind == "ok":
            self._append("YOU", question.strip())
            self._append("VARYN", message)
            self.prompt.delete("1.0", "end")
        else:
            self._append("NOTICE", message)
        self._busy = False
        self.send_button.configure(state="normal")
        self._refresh_status()

    def _clear(self):
        if self._busy:
            self._append("NOTICE", "Cannot clear while a request is in flight")
            return
        self.controller.clear_history()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self._refresh_status()

    def _discard(self):
        if not self._lifecycle.busy:
            return
        # The provider MAY STILL complete and charge: only hide its reply.
        if not messagebox.askyesno(
            "Discard reply (not remote cancellation)",
            "Hide this pending reply? The API request will keep running and may still be billed.",
            parent=self,
        ):
            return
        self.controller.discard_pending_history()
        self._lifecycle.discard_visible()
        self._busy = False
        self.send_button.configure(state="normal")
        self._append("NOTICE", "Reply hidden; remote API request was not canceled")
        self._refresh_status()

    def _review_tool_intent(self):
        if self._busy:
            self._append("AGENT", "Finish or discard the current chat request first")
            return
        raw = self.prompt.get("1.0", "end-1c")
        try:
            preview = stage_tool_intent(raw, self._approval)
        except (AgentRejected, AgentLimitReached) as error:
            self._append("AGENT", "Tool intent rejected: " + str(error))
            return
        self._confirm_agent_proposal(preview)

    def _confirm_agent_proposal(self, preview):
        content = (
            f"Tool: {preview.tool}\n"
            f"Proposal ID: {preview.proposal_id}\n"
            f"Digest: {preview.digest}\n\n"
            f"Effect: {preview.summary}\n\n"
            f"Risk: {preview.risk}\n\n"
            "This is UNTRUSTED input. Approve the exact synthetic action?"
        )
        approved = messagebox.askyesno("Review tool intent", content, parent=self)
        try:
            result = self._approval.decide(
                preview.proposal_id, preview.digest, approved=approved,
            )
        except (AgentRejected, AgentLimitReached) as error:
            self._append("AGENT", "Decision failed: " + str(error))
            return
        self._append("AGENT", "Tool intent " + result["status"])

    def _agent_demo(self):
        # Fixed synthetic proposal, never generated by a model or external text.
        # UI confirmation binds to immutable proposal id + exact digest.
        try:
            preview = self._approval.propose(
                "stage_note", {"text": "Synthetic desktop approval test"}
            )
        except (AgentRejected, AgentLimitReached) as error:
            self._append("AGENT", str(error))
            return
        confirm_text = (
            f"Tool: {preview.tool}\n"
            f"Proposal: {preview.proposal_id}\n"
            f"SHA-256: {preview.digest}\n\n"
            f"Action: {preview.summary}\n\n"
            f"Risk: {preview.risk}\n\n"
            "Approve this EXACT synthetic action?"
        )
        approved = messagebox.askyesno(
            "VARYN agent action approval", confirm_text, parent=self,
        )
        try:
            result = self._approval.decide(
                preview.proposal_id, preview.digest, approved=approved,
            )
        except (AgentRejected, AgentLimitReached) as error:
            self._append("AGENT", "Approval failed: " + str(error))
            return
        self._append("AGENT", "Synthetic action " + result["status"])

    def _close(self):
        if self._lifecycle.busy and not messagebox.askyesno(
            "Close without canceling remote API",
            "A request is in flight. Closing hides its result but cannot cancel remote processing or billing. Close anyway?",
            parent=self,
        ):
            return
        self._approval.reject_all_pending()
        self.controller.discard_pending_history()
        self._lifecycle.close()
        self._closing = True
        self.destroy()


def main():
    try:
        window = VarynDesktop()
    except tk.TclError:
        raise SystemExit("A graphical desktop session is required")
    window.mainloop()


if __name__ == "__main__":
    main()
