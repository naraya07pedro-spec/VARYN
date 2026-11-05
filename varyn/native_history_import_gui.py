"""17S-30: owner-driven *official Gemini* native import of ChatGPT/Claude ZIP.

The actual ZIP stays in the user's custody, and the official website handles
selection, reading and upload. VARYN only opens pinned official support pages
and Gemini homepage after explicit, exact owner review. No background sync.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from varyn.native_export_inventory import (
    ExportInventoryRejected, inspect_export_zip_metadata,
)
from varyn.native_history_import import (
    NativeHistoryRejected, NativeHistoryTransfer,
    native_destination_info, source_export_instructions,
)


class NativeHistoryImportGuide(tk.Toplevel):
    def __init__(self, workbench):
        super().__init__(workbench)
        self._workbench = workbench
        self._session = NativeHistoryTransfer()
        self._metadata_inventory = None
        self.title("VARYN | Official one-time chat import TO Gemini")
        self.geometry("670x650")
        self.minsize(500, 440)
        self.transient(workbench)
        self.source = tk.StringVar(master=self, value="chatgpt")
        self.ack_account = tk.BooleanVar(master=self, value=False)
        self.ack_region = tk.BooleanVar(master=self, value=False)
        self.ack_zip = tk.BooleanVar(master=self, value=False)
        self.ack_privacy = tk.BooleanVar(master=self, value=False)
        self.result = tk.StringVar(master=self, value="not_checked")
        self.status_line = tk.StringVar(
            master=self, value="No browser request. No ZIP opened by VARYN."
        )
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._dismiss)

    def _build(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="both", expand=True)
        canvas = tk.Canvas(top, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=8)
        win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win, width=e.width))
        ttk.Label(
            body, text="Official native ZIP import: ChatGPT/Claude → Gemini",
            font=("Segoe UI", 13, "bold"), wraplength=590,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            body, text="This is a provider-supported ONE-TIME import, not "
                       "two-way synchronization or VARYN reading your history.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 10))
        line = ttk.Frame(body)
        line.pack(anchor="w", pady=(0, 8))
        ttk.Label(line, text="Source:").pack(side="left")
        ttk.Combobox(
            line, textvariable=self.source, state="readonly",
            values=("chatgpt", "claude"), width=13,
        ).pack(side="left", padx=(8, 12))
        ttk.Button(
            line, text="1. Read OFFICIAL export instructions",
            command=self._open_export_guide,
        ).pack(side="left")
        info = native_destination_info()
        ttk.Label(
            body, text="2. Download the official export ZIP yourself. "
                       "Optional: explicitly inspect only its ZIP directory "
                       "metadata locally. This does not read chat messages, "
                       "validate file contents, or upload anything.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 5))
        ttk.Button(
            body, text="17S-31 | Inspect selected ZIP metadata locally (optional)",
            command=self._inspect_selected_zip,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            body, text="3. Gemini's Settings > Import memory to Gemini > "
                       "Import chats > Add accepts a supported ZIP. "
                       "The official guide says up to 5 GB per ZIP and "
                       "5 ZIP uploads per day, if eligible.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            body, text="4. Important privacy: imported chats are saved in "
                       "Google Activity and may be used to improve Google "
                       "services, including training generative AI models. "
                       "Review Google's current policies before uploading.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 12))
        ttk.Checkbutton(
            body, variable=self.ack_account,
            text="I confirm I'm 18+ and using a PERSONAL Google account",
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            body, variable=self.ack_region,
            text="I confirm I'm not in EEA, Switzerland, or the UK",
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            body, variable=self.ack_zip,
            text="I obtained the export ZIP; any optional local metadata scan "
                 "requires separate consent",
        ).pack(anchor="w", pady=3)
        ttk.Checkbutton(
            body, variable=self.ack_privacy,
            text="I understand Google's storage/data-use implications",
        ).pack(anchor="w", pady=(3, 12))
        ttk.Button(
            body, text="5. Review and open official Gemini import page",
            command=self._open_gemini,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            body, text="In Gemini, choose the import controls and upload the "
                       "ZIP DIRECTLY there, not into VARYN. A browser-open "
                       "request is NOT proof any file was uploaded.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(body, textvariable=self.status_line,
                  wraplength=590).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            body, text="6. Optional fixed SELF-REPORT only. VARYN cannot "
                       "check Gemini's account or resulting chats.",
            wraplength=590,
        ).pack(anchor="w", pady=(0, 5))
        reportline = ttk.Frame(body)
        reportline.pack(anchor="w", pady=(0, 5))
        ttk.Combobox(
            reportline, textvariable=self.result, state="readonly",
            values=("not_checked", "owner_reported_uploaded",
                    "owner_reported_partial", "owner_reported_failed"),
            width=26,
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            reportline, text="Record self-report in RAM",
            command=self._report,
        ).pack(side="left")
        ttk.Button(
            body, text="Reset attempt and acknowledgements",
            command=self._reset,
        ).pack(anchor="w", pady=(10, 4))
        ttk.Label(
            body, text="No account write permission, cookies, message-body "
                       "reading, saved file paths or automatic sync. Optional "
                       "metadata-only ZIP inspection is entirely local.",
            wraplength=590,
        ).pack(anchor="w", pady=(6, 5))
        ttk.Button(
            body, text="Close native import guide",
            command=self._dismiss,
        ).pack(anchor="w", pady=(8, 5))

    def _ack(self):
        return {
            "adult_personal_account": self.ack_account.get() is True,
            "supported_region": self.ack_region.get() is True,
            "zip_export_ready": self.ack_zip.get() is True,
            "google_activity_privacy_ack": self.ack_privacy.get() is True,
        }

    def _allowed(self):
        return (not getattr(self._workbench._owner, "_closing", True)
                and not getattr(self._workbench._owner, "_busy", True))

    def _inspect_selected_zip(self):
        """Separate opt-in, file picker + exact review BEFORE touching ZIP."""
        if not self._allowed():
            return
        source = self.source.get()
        if source not in ("chatgpt", "claude"):
            self.status_line.set("Unsupported source for metadata inspection.")
            return
        self._metadata_inventory = None
        if not messagebox.askyesno(
            "VARYN | Optional local ZIP metadata",
            "This is OPTIONAL. Choose a local exported ZIP using the file "
            "picker. VARYN will see the chosen file path transiently and "
            "read ONLY bounded ZIP central-directory metadata after a second "
            "approval. It will NOT extract ZIP members, read conversation "
            "bodies, save the path, upload the ZIP or check Gemini. "
            "Pilot limit: 128 MiB / ZIP32. Continue to file selection?",
            parent=self,
        ):
            self.status_line.set("Local inventory cancelled; no ZIP selected.")
            return
        if not self._allowed() or self.source.get() != source:
            self.status_line.set("Source changed before file selection; refused.")
            return
        try:
            selected = filedialog.askopenfilename(
                parent=self,
                title="Select a ChatGPT/Claude export ZIP for metadata only",
                filetypes=[("ZIP archives", "*.zip")],
            )
        except (tk.TclError, OSError, ValueError):
            selected = ""
        if not selected or not self._allowed() or self.source.get() != source:
            self.status_line.set("No ZIP inspected; selection cancelled/changed.")
            return
        approved = self._workbench._owner._review_scrollable_manual_text(
            title="VARYN | Confirm local ZIP metadata read",
            heading="Local ZIP metadata only. No member data, account access "
                    "or network upload.",
            digest="17S-31: ZIP32 bounded inventory, no archive extraction",
            content="Selected ZIP via YOUR local file picker. Declared source: " +
                    source + "\n\nInspect ZIP central-directory metadata "
                    "without opening any archived file payload. Hard limits: "
                    "128 MiB ZIP size, 2 MiB directory, 5,000 entries; "
                    "ZIP64 not supported. Does not expose filenames, chat "
                    "titles, messages, metadata IDs or local paths in report. "
                    "May detect unsafe/malformed ZIP; will NOT prove the "
                    "export was issued by a provider, or is importable.",
            warning="VARYN briefly receives your chosen local file path in "
                    "memory to open it. The result is metadata-only, RAM-only; "
                    "no file upload, content extraction, disk output or "
                    "background file scan. No consent means NO read.",
            approve_label="Approve LOCAL ZIP envelope inspection only",
        )
        if not approved or not self._allowed() or self.source.get() != source:
            self.status_line.set("No ZIP read; review declined or changed.")
            return
        try:
            report = inspect_export_zip_metadata(selected, source)
        except ExportInventoryRejected:
            self.status_line.set(
                "ZIP envelope not inspected: unsupported, oversized or "
                "unsafe metadata. No messages extracted or uploaded."
            )
            return
        self._metadata_inventory = report
        self.status_line.set(
            "Local metadata ONLY: " + str(report["zip_entry_count"]) +
            " ZIP entries; " + str(report["archive_bytes"]) +
            " archive bytes; ChatGPT filename hints " +
            str(report["chatgpt_named_conversation_json_hints"]) +
            ". Contents NOT read, source/Google import NOT verified."
        )

    def _open_export_guide(self):
        if not self._allowed():
            return
        try:
            details = source_export_instructions(self.source.get())
        except NativeHistoryRejected:
            self.status_line.set("Unsupported source. No browser opened.")
            return
        approved = messagebox.askyesno(
            "VARYN | Open official source guide",
            "Open this public OFFICIAL source provider export guide in "
            "your system browser? VARYN will not access your account.\n\n" +
            details["export_guide_url"],
            parent=self,
        )
        if not approved or not self._allowed():
            return
        if self.source.get() != details["source"]:
            self.status_line.set(
                "Source changed during review. Guide launch refused."
            )
            return
        try:
            opened = webbrowser.open_new_tab(details["export_guide_url"])
        except (OSError, ValueError):
            opened = False
        self.status_line.set(
            "Official source help page launch requested (not export proof)."
            if opened else "Failed to open official help page."
        )

    def _open_gemini(self):
        if not self._allowed():
            return
        try:
            review = self._session.prepare(self.source.get(), self._ack())
        except NativeHistoryRejected:
            self.status_line.set(
                "BLOCKED: complete all 4 eligibility/ZIP/privacy "
                "acknowledgements, or reset previous attempt."
            )
            return
        info = native_destination_info()
        full_text = (
            "USER-DRIVEN HISTORY TRANSFER ONLY\n"
            "Source: " + review.source +
            "\nDestination: " + review.target +
            "\nPinned site: " + review.target +
            " (" + info["destination_url"] + ")" +
            "\nOfficial import guide: " + info["official_help_url"] +
            "\n\n" + info["privacy_warning"] +
            "\n\nAll four acknowledgements were explicitly checked. "
            "No file is uploaded or account accessed by VARYN. "
            "An optional prior local ZIP envelope read, if you chose it, "
            "did not read messages and did not upload data."
        )
        approved = self._workbench._owner._review_scrollable_manual_text(
            title="VARYN | Review Gemini native import and privacy",
            heading="This browser open is NOT chat-history sync, "
                    "not remote import verification, and NOT a file upload.",
            digest=review.consent_digest,
            content=full_text,
            warning="Google will process data uploaded DIRECTLY in its "
                    "official site; no upload occurs in VARYN.",
            approve_label="Approve opening Gemini homepage ONLY",
        )
        if not approved:
            try:
                self._session.decide(
                    review, approved=False, browser_opened=False,
                    acknowledgements=self._ack(),
                )
            except NativeHistoryRejected:
                pass
            self.status_line.set("Import guide declined; no browser opened.")
            return
        if not self._allowed() or self.source.get() != review.source:
            self._session.reset()
            self.status_line.set("Source changed during review. Refused.")
            return
        # Review remained exact; the consent policy is checked once again,
        # before the browser action. NEVER submit a ZIP or account token.
        if tuple(self._ack().items()) != review.acknowledgements:
            self._session.reset()
            self.status_line.set("Eligibility/privacy checks changed. Refused.")
            return
        try:
            opened = webbrowser.open_new_tab(info["destination_url"])
        except (OSError, ValueError):
            opened = False
        try:
            event = self._session.decide(
                review, approved=True, browser_opened=bool(opened),
                acknowledgements=self._ack(),
            )
        except NativeHistoryRejected:
            self.status_line.set("Review expired or changed. No import verified.")
            return
        self.status_line.set(
            "Gemini homepage launch requested. Complete ZIP upload IN GEMINI "
            "yourself; no account/import verification by VARYN."
            if event["status"] == "official_browser_open_requested"
            else "Browser launch failed; no import verified."
        )

    def _report(self):
        if not self._allowed():
            return
        try:
            self._session.report(self.result.get())
        except NativeHistoryRejected:
            self.status_line.set("No reviewed Gemini browser request or invalid result.")
            return
        self.status_line.set(
            "Saved only fixed owner SELF-REPORT in RAM: " +
            self.result.get() + ". Provider-side import remains UNVERIFIED."
        )

    def _reset(self):
        if not self._allowed():
            return
        self._session.reset()
        self._metadata_inventory = None
        for var in (self.ack_account, self.ack_region,
                    self.ack_zip, self.ack_privacy):
            var.set(False)
        self.result.set("not_checked")
        self.status_line.set("Attempt reset. No external account data altered.")

    def _dismiss(self):
        self._session.reset()
        self._metadata_inventory = None
        if getattr(self._workbench, "_native_history_window", None) is self:
            self._workbench._native_history_window = None
        self.destroy()
