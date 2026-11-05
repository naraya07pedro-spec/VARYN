"""17S-28: focused owner-facing relay window for ACTUAL official app manual use.

One window for a user-authored synthetic task, manual browser open/copy,
unverified reply pasteback, and opt-in per-project note. Every operation
delegates to the existing VarynDesktop owner approval, TTL, provenance
and clipboard gates. This class never talks to a browser/AI model itself.
"""
import tkinter as tk
from tkinter import ttk, filedialog

from varyn.official_draft_resume import (
    make_draft, save_new, load_existing, review_text, digest,
    SyntheticDraftRejected,
)
from varyn.dpapi_vault import SealedDataError, UnsupportedPlatformError

from varyn.official_manual_relay import OFFICIAL_APP_LINKS
from varyn.native_history_import_gui import NativeHistoryImportGuide
from varyn.owner_pilot_checklist_gui import OwnerPilotChecklist
from varyn.guided_trio_flow import GuidedThreeAppFlow, GuidedTrioRejected
from varyn.guided_reply_ledger import GuidedLedgerRejected


class OfficialRelayWorkbench(tk.Toplevel):
    """No silent transfer, background request, remote state or disk usage."""

    def __init__(self, parent):
        if getattr(parent, "_closing", True):
            raise RuntimeError("Cannot open relay workbench while desktop closes")
        super().__init__(parent)
        self._owner = parent
        self._native_history_window = None
        self._owner_checklist_window = None
        self.title("VARYN | Official apps: manual workbench, NO sync")
        self.geometry("680x630")
        self.minsize(510, 430)
        self.transient(parent)
        self.target = tk.StringVar(master=self, value="chatgpt")
        self.project = tk.StringVar(master=self, value="VARYN")
        self.topic = tk.StringVar(master=self, value="next_step")
        self.include_context = tk.BooleanVar(master=self, value=False)
        self._guided_flow = GuidedThreeAppFlow()
        self._guided_ledger_window = None
        self.guided_label = tk.StringVar(
            master=self, value="Guided ChatGPT -> Claude -> Gemini: OFF"
        )
        self.stage_label = tk.StringVar(
            master=self, value="Local manual workbench. No app connected."
        )
        self.detail_label = tk.StringVar(master=self, value="")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._dismiss)
        self.refresh()

    def _build(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(
            top, text="Official AI app handoff | MANUAL ONLY",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            top, text="No consumer-app sync, account login, provider API, "
                      "automatic clipboard reading or private file access.",
            wraplength=630,
        ).pack(anchor="w", pady=(4, 4))
        ttk.Label(
            top, textvariable=self.stage_label, wraplength=630,
        ).pack(anchor="w")
        ttk.Button(
            top,
            text="17S-30 | Official one-time ChatGPT/Claude ZIP import to Gemini",
            command=self._open_native_history_import,
        ).pack(anchor="w", pady=(8, 4))
        ttk.Label(
            top,
            text="New: Gemini supports user-driven native history ZIP import "
                 "for eligible personal accounts. No VARYN file reading or sync.",
            wraplength=630,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Button(
            top, text="17S-32 | Owner PC acceptance checklist",
            command=self._open_owner_checklist,
        ).pack(anchor="w", pady=(3, 5))
        ttk.Button(
            top, text="17S-33 | Save encrypted synthetic draft (manual)",
            command=self._save_encrypted_draft,
        ).pack(anchor="w", pady=(2, 3))
        ttk.Button(
            top, text="17S-33 | Restore encrypted draft (manual)",
            command=self._restore_encrypted_draft,
        ).pack(anchor="w", pady=(0, 4))

        guided = ttk.Frame(self, padding=(12, 6))
        guided.pack(fill="x")
        ttk.Label(
            guided, textvariable=self.guided_label, wraplength=640,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Button(
            guided, text="17S-35 | Start three-app guided review",
            command=self._start_guided,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Button(
            guided, text="17S-35 | Prepare next app after reviewed reply",
            command=self._advance_guided,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Button(
            guided, text="17S-36 | View complete locally reviewed replies (RAM)",
            command=self._view_guided_ledger,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Button(
            guided, text="17S-35 | Discard guided flow and relay RAM",
            command=self._discard_guided,
        ).pack(anchor="w", pady=(0, 5))

        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        canvas = tk.Canvas(area, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=(12, 8))
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        line = ttk.Frame(body)
        line.pack(fill="x", pady=(0, 9))
        ttk.Label(line, text="Official app:").pack(side="left", padx=(0, 8))
        ttk.Combobox(
            line, values=tuple(OFFICIAL_APP_LINKS),
            textvariable=self.target, state="readonly", width=14,
        ).pack(side="left", padx=(0, 12))
        ttk.Button(
            line, text="1. Open official site (consent)",
            command=self._open_browser,
        ).pack(side="left")

        ttk.Label(
            body, text="2. Your synthetic task (never loaded from disk)",
        ).pack(anchor="w")
        self.task = tk.Text(body, height=4, wrap="word")
        self.task.pack(fill="x", pady=(3, 5))
        self.task.insert(
            "1.0",
            "SYNTHETIC: Suggest two steps to organize a fictional task list.",
        )

        scope = ttk.Frame(body)
        scope.pack(fill="x", pady=(0, 5))
        ttk.Label(scope, text="Project:").pack(side="left")
        ttk.Entry(
            scope, textvariable=self.project, width=14,
        ).pack(side="left", padx=(5, 10))
        ttk.Label(scope, text="Topic:").pack(side="left")
        ttk.Entry(
            scope, textvariable=self.topic, width=14,
        ).pack(side="left", padx=(5, 0))
        ttk.Checkbutton(
            body,
            text="Include only reviewed notes for this project in next packet",
            variable=self.include_context,
        ).pack(anchor="w", pady=(0, 5))
        ttk.Button(
            body, text="2. Review EXACT packet and copy to clipboard",
            command=self._copy,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            body, text="Paste the approved packet into the actual app yourself. "
                       "VARYN cannot observe delivery.",
            wraplength=610,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            body, text="3. Paste the external app reply here (UNVERIFIED source)",
        ).pack(anchor="w")
        self.reply = tk.Text(body, height=5, wrap="word")
        self.reply.pack(fill="x", pady=(3, 5))
        ttk.Button(
            body, text="3. Review EXACT pasted reply and stage in RAM",
            command=self._accept_reply,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            body, text="4. Optional owner-written working note (RAM only)",
        ).pack(anchor="w")
        self.note = tk.Text(body, height=3, wrap="word")
        self.note.pack(fill="x", pady=(3, 5))
        self.note.insert(
            "1.0", "SYNTHETIC: Next step for this fictional project.",
        )
        ttk.Button(
            body, text="4. Review project note / show conflicts",
            command=self._review_note,
        ).pack(anchor="w", pady=(0, 5))
        ttk.Label(
            body, text="Next: choose another official app, write a new "
                       "SYNTHETIC: task, and separately approve its packet.",
            wraplength=610,
        ).pack(anchor="w", pady=(0, 12))

        cleanup = ttk.Frame(body)
        cleanup.pack(fill="x")
        ttk.Button(
            cleanup, text="Discard relay RAM",
            command=self._discard_relay,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            cleanup, text="Discard project RAM notes",
            command=self._discard_notes,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            cleanup, text="Refresh status",
            command=self.refresh,
        ).pack(side="left")
        ttk.Label(
            body, textvariable=self.detail_label, wraplength=620,
        ).pack(anchor="w", pady=(9, 8))

        bottom = ttk.Frame(self, padding=(12, 8))
        bottom.pack(fill="x")
        ttk.Button(
            bottom, text="Close workbench (RAM relay stays until Discard)",
            command=self._dismiss,
        ).pack(anchor="w")

    def _sync_guided_label(self):
        state = self._guided_flow.status()
        if state["phase"] == "idle":
            label = "Guided ChatGPT -> Claude -> Gemini: OFF"
        else:
            label = ("Guided " + str(state["stage"]) + "/3: " +
                     str(state["provider"]) + " | " + state["phase"] +
                     " | manual transfer, provider origin UNVERIFIED")
        self.guided_label.set(label)

    def _start_guided(self):
        if not self._allowed():
            return
        try:
            selection = self._guided_flow.start(
                self.task.get("1.0", "end-1c").strip(),
                self._owner._official_relay.status(),
            )
        except GuidedTrioRejected:
            self.detail_label.set(
                "BLOCKED: discard current relay/guided flow and use a "
                "harmless SYNTHETIC: task (max 650 characters)."
            )
            return
        self.target.set(selection["provider"])
        self._sync_guided_label()
        self.detail_label.set(
            "Stage 1 ready. Open ChatGPT with consent, then review the "
            "EXACT clipboard packet; paste it yourself into the official app."
        )

    def _advance_guided(self):
        if not self._allowed():
            return
        try:
            selection = self._guided_flow.prepare_next(
                self._owner._official_relay.status()
            )
        except GuidedTrioRejected:
            self.detail_label.set(
                "BLOCKED: copy to the current app and review its manual "
                "reply first; next stage never skips user review."
            )
            return
        self.target.set(selection["provider"])
        self.task.delete("1.0", "end")
        self.task.insert("1.0", selection["task"])
        # The previous editable reply must not be accidentally appended to
        # the next app's claimed reply. The reviewed relay still retains it.
        self.reply.delete("1.0", "end")
        self._sync_guided_label()
        self.detail_label.set(
            "Next stage prepared locally. No browser opened and nothing "
            "copied or sent. Approve each official-app action separately."
        )

    def _discard_guided(self):
        if not self._allowed():
            return
        self._owner._discard_official_app_relay()
        self._clear_guided_ledger_view()
        self._guided_flow.reset()
        self.reply.delete("1.0", "end")
        self._sync_guided_label()
        self.detail_label.set(
            "Guided flow and relay RAM discarded. Existing OS clipboard "
            "cannot be recalled. Project notes require separate discard."
        )

    def _clear_guided_ledger_view(self):
        viewer = getattr(self, "_guided_ledger_window", None)
        if viewer is not None:
            try:
                if viewer.winfo_exists():
                    viewer.destroy()
            except tk.TclError:
                pass
        self._guided_ledger_window = None

    def _view_guided_ledger(self):
        if not self._allowed():
            return
        try:
            content = self._guided_flow.ledger.full_review_text()
        except GuidedLedgerRejected:
            self.detail_label.set("No locally reviewed replies available.")
            return
        self._clear_guided_ledger_view()
        viewer = tk.Toplevel(self)
        self._guided_ledger_window = viewer
        viewer.title("VARYN | Full local staged replies (unverified)")
        viewer.geometry("700x530")
        viewer.minsize(500, 330)
        viewer.transient(self)
        root = ttk.Frame(viewer, padding=10)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="RAM ONLY; claimed provider origins unverified. "
                  "No export, browser, provider API or native account sync.",
                  wraplength=650).pack(anchor="w", pady=(0, 8))
        area = ttk.Frame(root)
        area.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(area)
        scroll.pack(side="right", fill="y")
        reader = tk.Text(area, wrap="word")
        reader.pack(side="left", fill="both", expand=True)
        reader.configure(yscrollcommand=scroll.set)
        scroll.configure(command=reader.yview)
        reader.insert("1.0", content)
        reader.configure(state="disabled")
        ttk.Button(root, text="Close local record view",
                   command=self._clear_guided_ledger_view).pack(
                       anchor="e", pady=(8, 0))
        viewer.protocol("WM_DELETE_WINDOW", self._clear_guided_ledger_view)

    def _draft_from_fields(self):
        return make_draft(
            target=self.target.get(),
            project=self.project.get(),
            topic=self.topic.get(),
            task=self.task.get("1.0", "end-1c").strip(),
            note=self.note.get("1.0", "end-1c").strip(),
        )

    def _review_draft(self, draft, *, restoring=False):
        return self._owner._review_scrollable_manual_text(
            title="VARYN | Review exact local encrypted draft",
            heading=("RESTORE owner-selected local draft; NO relay approval"
                     if restoring else
                     "SAVE only the five synthetic owner-authored fields"),
            digest=digest(draft),
            content=review_text(draft),
            warning="Windows DPAPI, bound to your Windows profile. "
                    "No reply, provider credentials, permission or sync state. "
                    "Never use sensitive or real customer content.",
            approve_label=("Approve replace of displayed draft fields"
                           if restoring else "Approve new encrypted file"),
        )

    def _save_encrypted_draft(self):
        if not self._allowed():
            return
        try:
            draft = self._draft_from_fields()
            approved = self._review_draft(draft)
            if not approved or not self._allowed():
                self.detail_label.set("Encrypted draft save declined.")
                return
            # Modal callbacks may be reentrant. Never save a changed draft.
            if self._draft_from_fields() != draft:
                self.detail_label.set("BLOCKED: fields changed after review.")
                return
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Choose NEW local encrypted .varyn file (no overwrite)",
                defaultextension=".varyn",
                filetypes=[("Encrypted VARYN draft", "*.varyn")],
            )
            if not path or not self._allowed():
                return
            if self._draft_from_fields() != draft:
                self.detail_label.set("BLOCKED: fields changed after file picker.")
                return
            save_new(path, draft)
            self.detail_label.set(
                "New Windows DPAPI encrypted synthetic draft saved locally. "
                "Not a synced conversation or restored relay permission."
            )
        except (SyntheticDraftRejected, SealedDataError,
                UnsupportedPlatformError, OSError, ValueError):
            self.detail_label.set(
                "BLOCKED: synthetic draft invalid or encrypted save failed. "
                "Existing files are never overwritten."
            )

    def _restore_encrypted_draft(self):
        if not self._allowed():
            return
        relay = self._owner._official_relay.status()
        notes = self._owner._working_context.status()
        if (relay["hops_used"] or relay["awaiting_user_pasteback"] or
                relay["reply_in_ram"] or relay["return_review_pending"] or
                notes["saved_count"] or
                self.reply.get("1.0", "end-1c").strip()):
            self.detail_label.set(
                "BLOCKED: discard active relay/notes and clear pasted-reply "
                "editor before restoring draft fields."
            )
            return
        try:
            original = self._draft_from_fields()
            path = filedialog.askopenfilename(
                parent=self, title="Select one encrypted synthetic .varyn draft",
                filetypes=[("Encrypted VARYN draft", "*.varyn")],
            )
            if not path or not self._allowed():
                return
            draft = load_existing(path)
            if not self._review_draft(draft, restoring=True):
                self.detail_label.set("Encrypted draft restore declined.")
                return
            if not self._allowed() or self._draft_from_fields() != original:
                self.detail_label.set("BLOCKED: active fields changed during restore.")
                return
            current_relay = self._owner._official_relay.status()
            current_notes = self._owner._working_context.status()
            if (current_relay != relay or current_notes != notes or
                    self.reply.get("1.0", "end-1c").strip()):
                self.detail_label.set("BLOCKED: relay or notes changed during restore.")
                return
            self.target.set(draft["target"])
            self.project.set(draft["project"])
            self.topic.set(draft["topic"])
            for widget, content in ((self.task, draft["task"]),
                                    (self.note, draft["note"])):
                widget.delete("1.0", "end")
                widget.insert("1.0", content)
            self.include_context.set(False)
            self.refresh()
            self.detail_label.set(
                "Restored five synthetic draft fields only. Relay approvals, "
                "unverified replies and context sharing were NOT restored."
            )
        except (SyntheticDraftRejected, SealedDataError,
                UnsupportedPlatformError, OSError, ValueError):
            self.detail_label.set(
                "BLOCKED: selected DPAPI draft invalid, inaccessible or incompatible."
            )

    def _open_native_history_import(self):
        if not self._allowed():
            return
        prior = self._native_history_window
        if prior is not None and prior.winfo_exists():
            prior.lift()
            prior.focus_set()
            return
        self._native_history_window = NativeHistoryImportGuide(self)

    def _open_owner_checklist(self):
        if not self._allowed():
            return
        prior = self._owner_checklist_window
        if prior is not None and prior.winfo_exists():
            prior.lift()
            prior.focus_set()
            return
        self._owner_checklist_window = OwnerPilotChecklist(self)

    def _allowed(self):
        return not self._owner._closing and not self._owner._busy

    def _synthetic(self, widget, max_chars):
        value = widget.get("1.0", "end-1c").strip()
        if not value.startswith("SYNTHETIC:") or len(value) > max_chars:
            self.detail_label.set(
                "BLOCKED: use only a harmless SYNTHETIC: sample (max " +
                str(max_chars) + " characters). No action taken."
            )
            return None
        return value

    def _open_browser(self):
        if not self._allowed():
            return
        self._owner._open_selected_official_app(target=self.target.get())
        self.refresh()

    def _copy(self):
        if not self._allowed():
            return
        task = self._synthetic(self.task, 1000)
        if task is None:
            return
        relay = self._owner._official_relay
        before = relay.status()
        provider = self.target.get()
        if self._guided_flow.active:
            try:
                self._guided_flow.require_copy(provider, before, task)
            except GuidedTrioRejected:
                self.detail_label.set(
                    "BLOCKED: guided provider or stage mismatch. "
                    "Discard guided flow to use free-form manual relay."
                )
                return
        try:
            history = (self._guided_flow.history_selection()
                       if self._guided_flow.active and
                       self._guided_flow.status()["stage"] in (2, 3)
                       else None)
        except (GuidedTrioRejected, GuidedLedgerRejected):
            self.detail_label.set("BLOCKED: incomplete prior local guided history.")
            return
        self._owner._copy_official_app_relay(
            task=task, target=provider,
            project=self.project.get(),
            include_context=self.include_context.get() is True,
            guided_history=history,
        )
        after = relay.status()
        if self._guided_flow.active:
            if (after["hops_used"] == before["hops_used"] + 1 and
                    after["awaiting_user_pasteback"]):
                try:
                    self._guided_flow.copied(before, after, provider, task)
                except GuidedTrioRejected:
                    self._guided_flow.reset()
                    self.detail_label.set(
                        "Guided flow local state mismatch; reset. "
                        "Discard relay RAM before starting again."
                    )
        self.refresh()

    def _accept_reply(self):
        if not self._allowed():
            return
        reply = self.reply.get("1.0", "end-1c").strip()
        if not reply or len(reply) > 1600:
            self.detail_label.set(
                "BLOCKED: type a bounded harmless pasted reply (max 1600)."
            )
            return
        relay = self._owner._official_relay
        before = relay.status()
        if self._guided_flow.active:
            try:
                self._guided_flow.require_reply(before)
            except GuidedTrioRejected:
                self.detail_label.set(
                    "BLOCKED: current guided stage has no approved outgoing copy."
                )
                return
        self._owner._review_official_app_reply(reply=reply)
        after = relay.status()
        if self._guided_flow.active:
            if (after["reply_in_ram"] and
                    not after["awaiting_user_pasteback"] and
                    after["return_receipt_available"]):
                try:
                    self._guided_flow.reviewed_reply(
                        before, after, reply_text=reply,
                        receipt=relay.last_return_receipt(),
                    )
                except (GuidedTrioRejected, GuidedLedgerRejected):
                    self._clear_guided_ledger_view()
                    self._guided_flow.reset()
                    self.detail_label.set(
                        "Guided reply mismatch; flow reset. "
                        "Discard relay RAM before starting again."
                    )
        self.refresh()

    def _review_note(self):
        if not self._allowed():
            return
        note = self._synthetic(self.note, 320)
        if note is None:
            return
        self._owner._review_project_working_note(
            project=self.project.get(),
            topic=self.topic.get(),
            note=note,
        )
        self.refresh()

    def _discard_relay(self):
        if not self._allowed():
            return
        self._owner._discard_official_app_relay()
        self._guided_flow.reset()
        self.reply.delete("1.0", "end")
        self.refresh()

    def _discard_notes(self):
        if not self._allowed():
            return
        self._owner._discard_project_working_notes()
        self.include_context.set(False)
        self.refresh()

    def refresh(self):
        self._sync_guided_label()
        if not self._allowed():
            return
        relay = self._owner._official_relay.status()
        notes = self._owner._working_context.status()
        count = relay["hops_used"]
        if relay["awaiting_user_pasteback"]:
            instruction = (
                "Awaiting manual reply: you must paste from the selected app."
            )
        elif relay["reply_in_ram"]:
            instruction = (
                "Unverified pasted reply staged. Select another app "
                "and review a NEW outgoing packet."
            )
        elif count >= relay["hops_limit"]:
            instruction = "Three-hop limit reached. Discard relay RAM to restart."
        else:
            instruction = "Ready for owner-reviewed manual clipboard handoff."
        self.stage_label.set("Local copies: " + str(count) + "/" +
                             str(relay["hops_limit"]) + " | " + instruction)
        self.detail_label.set(
            "Working notes in RAM: " + str(notes["saved_count"]) +
            " | context sharing " +
            ("OPTED IN" if self.include_context.get() else "OFF") +
            " | no remote delivery/account/history verification"
        )

    def _dismiss(self):
        self._clear_guided_ledger_view()
        self._guided_flow.reset()
        # A closed workbench removes only its own editable widgets.
        # The owner can explicitly discard relay/board state in the main UI.
        child = getattr(self, "_native_history_window", None)
        if child is not None:
            try:
                if child.winfo_exists():
                    child._dismiss()
            except tk.TclError:
                pass
            self._native_history_window = None
        checklist = getattr(self, "_owner_checklist_window", None)
        if checklist is not None:
            try:
                if checklist.winfo_exists():
                    checklist._dismiss()
            except tk.TclError:
                pass
            self._owner_checklist_window = None
        if getattr(self._owner, "_relay_workbench", None) is self:
            self._owner._relay_workbench = None
        self.destroy()
