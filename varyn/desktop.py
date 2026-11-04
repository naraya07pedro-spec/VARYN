"""VARYN Tkinter MVP: offline chat and explicitly confirmed optional live calls.

Run: python -m varyn.desktop
The UI never touches Tk widgets from worker threads and never persists chat.
Local synthetic-note memory is only enabled by explicit --memory-db path,
and is NEVER automatically sent to any model. Real provider APIs require keys.
"""
import argparse
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from varyn.desktop_controller import DesktopController, DEFAULT_MODELS, PROVIDERS
from varyn.providers import ProviderError
from varyn.desktop_lifecycle import DesktopRequestState
from varyn.desktop_approval import DesktopApprovalController
from varyn.agent_recovery import AgentRecoveryJournal
from varyn.agent_runtime import AgentRejected, AgentLimitReached
from varyn.tool_protocol import stage_tool_intent
from varyn.native_tool_requests import NativeToolRequestClient
from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import SyntheticFixture
from varyn.desktop_collaboration import review_collaboration
from varyn.desktop_memory import DesktopMemory


class VarynDesktop(tk.Tk):
    def __init__(self, controller=None, *, agent_journal=None, memory_db=None):
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
        self._agent_journal = agent_journal
        self._memory = DesktopMemory(memory_db) if memory_db is not None else None
        self.memory_project = tk.StringVar(value="VARYN")
        self._approval = DesktopApprovalController(journal=agent_journal)
        self._native_client = NativeToolRequestClient(allow_network=True)
        self._file_grants = ScopedFileGrants(auto_expire=True)
        self._file_grant_id = None
        self._file_fixture = None
        self._busy = False
        self._closing = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._refresh_status()
        if self._approval.recovered is not None:
            stale = self._approval.recovered
            self._append(
                "RECOVERY", "Recovered metadata only: "
                f"{stale['needs_review']} proposals need fresh review, "
                f"{stale['needs_reconciliation']} dispatches need reconciliation. "
                "No saved action was resumed or replayed."
            )

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
        self.collaborate_button = ttk.Button(
            controls, text="Collaborate (3 roles)", command=self._open_collaboration,
        )
        self.collaborate_button.pack(side="left", padx=(8, 0))
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
            outer, text="Request native model tool proposal (live, may bill)",
            command=self._request_native_tool,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Button(
            outer, text="Review structured tool intent (untrusted JSON)",
            command=self._review_tool_intent,
        ).pack(anchor="w", pady=(0, 8))
        file_controls = ttk.Frame(outer, style="V.TFrame")
        file_controls.pack(fill="x", pady=(2, 8))
        ttk.Button(
            file_controls, text="Create & grant VARYN demo folder",
            command=self._grant_synthetic_folder,
        ).pack(side="left")
        ttk.Button(
            file_controls, text="Inspect test-folder count",
            command=self._inspect_synthetic_folder,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            file_controls, text="Revoke test-folder grant",
            command=self._revoke_synthetic_folder,
        ).pack(side="left", padx=(8, 0))
        self._build_memory_controls(outer)
        ttk.Label(
            outer, text="Chat RAM resets on restart. Local memory only with --memory-db; "
                        "plaintext synthetic notes; never auto-uploaded. Live APIs may bill.",
            style="V.TLabel",
        ).pack(anchor="w")
        self._append(
            "SYSTEM", "Only fake mode is free and offline. Live mode requires an "
            "API key set outside this app, network consent, and confirmation "
            "of each individual request. Do not input private data."
        )

    def _build_memory_controls(self, outer):
        """Memory must be explicitly activated by --memory-db at app launch."""
        row = ttk.Frame(outer, style="V.TFrame")
        row.pack(fill="x", pady=(2, 6))
        ttk.Label(row, text="Local project", style="V.TLabel").pack(
            side="left", padx=(0, 6),
        )
        ttk.Entry(row, textvariable=self.memory_project, width=12).pack(
            side="left", padx=(0, 8),
        )
        state = "normal" if self._memory is not None else "disabled"
        self.memory_save_button = ttk.Button(
            row, text="Save synthetic note", command=self._save_memory,
            state=state,
        )
        self.memory_save_button.pack(side="left", padx=(0, 5))
        self.memory_search_button = ttk.Button(
            row, text="Search project notes", command=self._search_memory,
            state=state,
        )
        self.memory_search_button.pack(side="left", padx=(0, 5))
        self.memory_delete_button = ttk.Button(
            row, text="Delete note ID", command=self._delete_memory,
            state=state,
        )
        self.memory_delete_button.pack(side="left")

    def _save_memory(self):
        if self._busy or self._closing or self._memory is None:
            return
        project = self.memory_project.get()
        note = self.prompt.get("1.0", "end-1c")
        try:
            self._memory._project(project)
            self._memory._note(note)
        except (ValueError, PermissionError):
            self._append("MEMORY", "Use project A-Z/0-9/_/- and a note starting SYNTHETIC: (max 1000).")
            return
        approved = messagebox.askyesno(
            "Save SYNTHETIC note in local plaintext SQLite?",
            f"Save EXACTLY this typed synthetic note to project {project}?\n\n"
            "The database is unencrypted and stays on this device. "
            "Nothing is sent to any AI provider. Not suitable for private data. "
            "You can delete it later by ID.",
            parent=self,
        )
        if not approved:
            self._append("MEMORY", "Save declined; nothing stored")
            return
        try:
            memory_id = self._memory.save(project, note, confirmed=True)
        except (ValueError, PermissionError, OSError):
            self._append("MEMORY", "Local synthetic note was not saved")
            return
        self._append("MEMORY", f"Synthetic note saved in project {project}, ID {memory_id}; no model upload")

    def _search_memory(self):
        if self._busy or self._closing or self._memory is None:
            return
        try:
            project = self.memory_project.get()
            query = self.prompt.get("1.0", "end-1c")
            rows = self._memory.search(project, query)
        except (ValueError, OSError):
            self._append("MEMORY", "Enter a valid project and 1..100-character search query")
            return
        self._append("MEMORY", f"Local-only search in project {project}: {len(rows)} notes found")
        for row in rows:
            self._append(
                "MEMORY " + str(row["id"]),
                row["content"][:1000],
            )

    def _delete_memory(self):
        if self._busy or self._closing or self._memory is None:
            return
        project = self.memory_project.get()
        raw_id = self.prompt.get("1.0", "end-1c").strip()
        if not raw_id.isascii() or not raw_id.isdecimal() or len(raw_id) > 12:
            self._append("MEMORY", "Enter a positive numeric note ID in the message box")
            return
        try:
            note_id = int(raw_id)
            self._memory._project(project)
            if note_id < 1:
                raise ValueError("Bad ID")
        except ValueError:
            self._append("MEMORY", "Invalid project or note ID")
            return
        if not messagebox.askyesno(
            "Permanently delete local synthetic note?",
            f"Delete ONLY note ID {note_id} from exact project {project}?\n\n"
            "No other projects will be modified. Deletion does not erase "
            "previous backups or secure-delete raw disk blocks.",
            parent=self,
        ):
            self._append("MEMORY", "Delete declined; nothing changed")
            return
        try:
            deleted = self._memory.delete(project, note_id, confirmed=True)
        except (ValueError, PermissionError, OSError):
            self._append("MEMORY", "Local delete failed")
            return
        self._append("MEMORY", "One local note deleted" if deleted else
                     "No matching note ID in this project")

    def _discard_synthetic_fixture(self):
        """Reclaim only a VARYN-owned disposable sample folder."""
        fixture, self._file_fixture = self._file_fixture, None
        if fixture is not None:
            try:
                fixture.close()
            except OSError:
                self._append("FILES", "Synthetic sample cleanup incomplete")

    def _grant_synthetic_folder(self):
        """Never accept user-selected paths in this experimental desktop."""
        if self._busy or self._closing:
            return
        consent = messagebox.askyesno(
            "Create a disposable VARYN sample folder?",
            "Create exactly two VARYN-generated, non-sensitive sample text "
            "files in a temporary folder, then grant local-only read access "
            "for at most 5 minutes / 10 operations?\n\n"
            "You cannot select Documents, Downloads, a cloud drive or any "
            "other personal folder in this experimental build. "
            "The temporary sample is cleaned up when its lease expires, "
            "is revoked or replaced, or the application closes. "
            "No file names or contents are sent to any AI provider.",
            parent=self,
        )
        if not consent:
            self._append("FILES", "Synthetic sample permission declined")
            return
        fixture = None
        try:
            fixture = SyntheticFixture()
            preview = self._file_grants.grant(
                fixture.root, user_confirmed=True,
                on_release=fixture.close,
            )
        except (PermissionError, ValueError, OSError, AgentRejected):
            if fixture is not None:
                try:
                    fixture.close()
                except OSError:
                    self._append("FILES", "Synthetic sample cleanup incomplete")
            self._append("FILES", "Synthetic sample creation or grant denied")
            return
        previous = self._file_grant_id
        old_fixture = self._file_fixture
        self._file_grant_id = preview.grant_id
        self._file_fixture = fixture
        if previous is not None:
            try:
                self._file_grants.revoke(previous)
            except AgentRejected:
                pass
        if old_fixture is not None:
            try:
                old_fixture.close()
            except OSError:
                self._append("FILES", "Previous synthetic sample cleanup incomplete")
        self._append(
            "FILES",
            f"Temporary VARYN-generated sample granted: "
            f"{preview.duration_seconds}s, {preview.max_operations} operations; "
            "read-only, not exposed to models. No folder path stored.",
        )

    def _inspect_synthetic_folder(self):
        """Count only; neither filenames nor contents enter the transcript."""
        if self._busy or self._closing:
            return
        if self._file_grant_id is None:
            self._append("FILES", "No active synthetic test-folder grant")
            return
        try:
            listing = self._file_grants.list_files(self._file_grant_id)
        except (PermissionError, AgentRejected):
            previous = self._file_grant_id
            self._file_grant_id = None
            if previous is not None:
                try:
                    self._file_grants.revoke(previous)
                except AgentRejected:
                    pass
            VarynDesktop._discard_synthetic_fixture(self)
            self._append("FILES", "Synthetic sample access expired or denied")
            return
        self._append(
            "FILES",
            f"Allowed top-level synthetic file count: {len(listing['files'])}"
            + (" (truncated at listing cap)" if listing["truncated"] else "")
            + ". No filenames or file contents uploaded or recorded in chat.",
        )

    def _revoke_synthetic_folder(self):
        if self._file_grant_id is not None:
            try:
                self._file_grants.revoke(self._file_grant_id)
            except AgentRejected:
                pass
            self._file_grant_id = None
        VarynDesktop._discard_synthetic_fixture(self)
        self._append("FILES", "Synthetic sample grant revoked and cleaned")

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
            f" | Native requests {self._native_client.budget.snapshot()['requests_reserved']}/"
            f"{self._native_client.budget.snapshot()['max_requests']}"
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
        self.collaborate_button.configure(state="disabled")
        self._refresh_status()
        worker = threading.Thread(
            target=self._send_worker,
            args=(request_id, question, selected_provider, selected_model, live),
            daemon=True,
        )
        worker.start()
        self.after(75, self._poll_result)

    def _open_collaboration(self):
        """Configure three roles in a separate normal-user Tk window."""
        if self._busy or self._closing:
            return
        dialog = tk.Toplevel(self)
        dialog.title("VARYN | Three-role collaboration")
        dialog.geometry("650x330")
        dialog.resizable(True, False)
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Analyst -> Critic -> Synthesizer | Offline fake by default",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        values = []
        for index, role in enumerate(("analyst", "critic", "synthesizer"), start=1):
            provider = tk.StringVar(master=dialog, value="fake")
            model = tk.StringVar(master=dialog, value="fake-test")
            ttk.Label(frame, text=role.capitalize()).grid(
                row=index, column=0, sticky="w", padx=(0, 10), pady=5,
            )
            menu = ttk.Combobox(
                frame, values=PROVIDERS, state="readonly",
                textvariable=provider, width=12,
            )
            menu.grid(row=index, column=1, sticky="w", padx=(0, 10))
            ttk.Entry(frame, textvariable=model, width=27).grid(
                row=index, column=2, sticky="we",
            )
            menu.bind(
                "<<ComboboxSelected>>",
                lambda _event, p=provider, m=model:
                    m.set(DEFAULT_MODELS[p.get()]),
            )
            values.append((provider, model))
        frame.columnconfigure(2, weight=1)
        ttk.Label(
            frame, text="Live model API requests may bill and share previous "
                        "stage results with later providers.",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(15, 6))

        def submit():
            task = self.prompt.get("1.0", "end-1c")
            selections = tuple((p.get(), m.get()) for p, m in values)
            if self._start_collaboration(task, selections):
                dialog.destroy()

        ttk.Button(
            frame, text="Review and run 3 stages", command=submit,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=10)

    def _start_collaboration(self, task, selections):
        """Review on Tk thread, then transfer immutable snapshot to worker."""
        if self._busy or self._closing:
            return False
        try:
            stages, approvals = review_collaboration(
                task, selections,
                network_enabled=self.consent_network.get()
                and self.controller.status()["network_enabled"],
                ask_approval=lambda prompt: messagebox.askyesno(
                    "Confirm each external AI stage", prompt, parent=self,
                ),
            )
            engine = self.controller.collaboration_engine()
            if self._closing or self._busy:
                return False
            request_id = self._lifecycle.begin()
        except (ValueError, PermissionError, RuntimeError):
            self._append(
                "COLLAB", "Plan invalid or approval declined. No stage started.",
            )
            return False
        self._busy = True
        self.send_button.configure(state="disabled")
        self.collaborate_button.configure(state="disabled")
        self._refresh_status()
        threading.Thread(
            target=self._collaboration_worker,
            args=(request_id, task, stages, approvals, engine),
            daemon=True,
        ).start()
        self.after(75, self._poll_result)
        return True

    def _collaboration_worker(self, request_id, task, stages, approvals, engine):
        """Background model work. Never access Tk from this thread."""
        try:
            result = engine.run(
                task, stages, live_confirmations=approvals,
            )
            self._results.put((request_id, "collaboration", "", result))
        except Exception:
            self._results.put((
                request_id, "collaboration_error", "",
                "Collaboration stopped. Earlier API stages may have billed; "
                "no automatic retry.",
            ))

    def _request_native_tool(self):
        if self._busy:
            return
        provider = self.provider.get()
        model = self.model.get()
        question = self.prompt.get("1.0", "end-1c")
        if provider == "fake":
            self._append("AGENT", "Choose an external provider for native tool proposals")
            return
        if not self.consent_network.get():
            self._append("AGENT", "Enable the network permission checkbox first")
            return
        if not question.strip() or not model.strip():
            self._append("AGENT", "A message and an exact model ID are required")
            return
        if not messagebox.askyesno(
            "Confirm native tool request",
            f"Send ONLY this typed message to {provider} using model {model}?\n\n"
            "This may incur API charges. No saved context is included. "
            "A returned tool call will ONLY become a review proposal; "
            "no tool will execute automatically. Proceed?", parent=self,
        ):
            return
        request_id = self._lifecycle.begin()
        self._busy = True
        self.send_button.configure(state="disabled")
        self.collaborate_button.configure(state="disabled")
        self._refresh_status()
        threading.Thread(
            target=self._native_tool_worker,
            args=(request_id, question, provider, model), daemon=True,
        ).start()
        self.after(75, self._poll_result)

    def _native_tool_worker(self, request_id, question, provider, model):
        # Parse only in worker; staging and approval belong on the Tk main thread.
        try:
            intent = self._native_client.request_intent(
                provider, question, model=model, confirm_external_request=True,
            )
            self._results.put((request_id, "native_intent", "", intent))
        except (ValueError, PermissionError, ProviderError, AgentRejected,
                AgentLimitReached) as error:
            self._results.put((request_id, "error", "", str(error)))
        except Exception:
            self._results.put((request_id, "error", "",
                               "Native request failed; no automatic retry"))

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
        if kind == "native_intent":
            # Only now, after the stale/close guard, create a pending proposal.
            try:
                preview = self._approval.propose(message.tool, message.arguments)
                self._confirm_agent_proposal(preview)
            except (AgentRejected, AgentLimitReached, ValueError, RuntimeError):
                self._append("AGENT", "Native proposal could not be staged or reviewed")
        elif kind == "collaboration":
            self._append("YOU", message["task"])
            for stage in message["stages"]:
                self._append(
                    "COLLAB " + stage["role"].upper(),
                    stage["provider"] + " / " + stage["model"]
                    + ": " + stage["text"],
                )
            self._append("VARYN SYNTHESIS", message["final_answer"])
            self.prompt.delete("1.0", "end")
        elif kind == "collaboration_error":
            self._append("COLLAB", message)
        elif kind == "ok":
            self._append("YOU", question.strip())
            self._append("VARYN", message)
            self.prompt.delete("1.0", "end")
        else:
            self._append("NOTICE", message)
        self._busy = False
        self.send_button.configure(state="normal")
        if hasattr(self, "collaborate_button"):
            self.collaborate_button.configure(state="normal")
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
        self._file_grants.revoke_all()
        self._file_grant_id = None
        VarynDesktop._discard_synthetic_fixture(self)
        if self._agent_journal is not None:
            self._agent_journal.close()
        if getattr(self, "_memory", None) is not None:
            self._memory.close()
        self.controller.discard_pending_history()
        self._lifecycle.close()
        self._closing = True
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="VARYN desktop")
    parser.add_argument("--agent-journal", metavar="PATH",
                        help="Opt-in metadata-only SQLite recovery file")
    parser.add_argument("--memory-db", metavar="PATH",
                        help="Explicit opt-in UNENCRYPTED local SQLite for SYNTHETIC notes only")
    args = parser.parse_args()
    journal = (AgentRecoveryJournal(args.agent_journal)
               if args.agent_journal else None)
    try:
        window = VarynDesktop(agent_journal=journal, memory_db=args.memory_db)
    except tk.TclError:
        if journal is not None:
            journal.close()
        raise SystemExit("A graphical desktop session is required")
    try:
        window.mainloop()
    finally:
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    main()
