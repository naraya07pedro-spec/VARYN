"""17S-32: local, owner-entered checklist inside the portable Tk workbench.

This is NOT a machine attestation of human clicks or provider authorization.
The form captures only ten fixed pass/fail/not_checked values in memory.
Nothing is read from private files, browsers, history, or account sessions.
"""
import json
import tkinter as tk
from tkinter import messagebox, ttk

from varyn.official_relay_pilot import _STEPS as _MANUAL_STEPS
from varyn.owner_pilot_launcher import _PROJECT_STEPS, combined_owner_report

_CHOICES = ("not_checked", "pass", "fail")
_CHECKS = _MANUAL_STEPS + _PROJECT_STEPS
_KEYS = tuple(key for key, _ in _CHECKS)


def build_portable_owner_report(answers):
    """Strict fixed-choice self-report. Never accept free-text observations."""
    if (type(answers) is not dict or set(answers) != set(_KEYS) or
            any(type(value) is not str or value not in _CHOICES
                for value in answers.values())):
        raise ValueError("Only ten fixed owner observations are allowed")
    base = combined_owner_report(
        {key: answers[key] for key, _ in _MANUAL_STEPS},
        {key: answers[key] for key, _ in _PROJECT_STEPS},
    )
    base["format"] = "varyn.owner_portable_checklist.v1"
    base["report_kind"] = "owner_entered_self_report_not_independently_verified"
    base["entrypoint"] = "local_portable_workbench"
    base["machine_verified_human_click"] = False
    base["official_app_delivery_verified"] = False
    base["device_identity_collected"] = False
    base["private_history_read"] = False
    base["report_saved_or_uploaded"] = False
    base["clipboard_copy_requires_separate_consent"] = True
    return base


class OwnerPilotChecklist(tk.Toplevel):
    """One local window, exact report review, optional separately approved copy."""

    def __init__(self, workbench):
        super().__init__(workbench)
        self._workbench = workbench
        self.title("VARYN | 17S-32 Owner PC manual acceptance (self-report)")
        self.geometry("700x690")
        self.minsize(510, 410)
        self.transient(workbench)
        self.fields = {
            key: tk.StringVar(master=self, value="not_checked")
            for key in _KEYS
        }
        self.stage = tk.StringVar(
            master=self, value="Nothing checked or copied. Run each step yourself."
        )
        self._reviewed_answers = None
        self._reviewed_json = None
        self._build()
        for value in self.fields.values():
            value.trace_add("write", self._invalidate)
        self.protocol("WM_DELETE_WINDOW", self._dismiss)

    def _build(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(
            top, text="Owner PC acceptance | MANUAL SELF-REPORT",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            top,
            text="Perform each step in the existing VARYN workbench and your own "
                 "official-app browser. Use harmless SYNTHETIC: inputs only. "
                 "Choose pass, fail, or not_checked; no text or account details.",
            wraplength=660,
        ).pack(anchor="w", pady=(5, 5))
        ttk.Label(
            top,
            text="A pass is your own statement, NOT independently verified "
                 "human clicks, remote delivery, identity, or automatic sync.",
            wraplength=660,
        ).pack(anchor="w", pady=(0, 5))

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=canvas.yview,
        )
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        body = ttk.Frame(canvas, padding=(12, 8))
        item = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(item, width=event.width),
        )
        for index, (key, prompt) in enumerate(_CHECKS, 1):
            group = ttk.Frame(body)
            group.pack(fill="x", pady=(0, 11))
            ttk.Label(
                group, text=str(index) + ". " + key, 
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                group, text=prompt, wraplength=620,
            ).pack(anchor="w", pady=(2, 3))
            ttk.Combobox(
                group, values=_CHOICES, state="readonly",
                textvariable=self.fields[key], width=17,
            ).pack(anchor="w")

        ttk.Separator(body).pack(fill="x", pady=(3, 7))
        ttk.Label(
            body, text="Fixed JSON preview (no filenames, conversations, "
                       "account identifiers, credentials or timestamps):",
            wraplength=620,
        ).pack(anchor="w")
        self.report = tk.Text(body, height=15, wrap="word")
        self.report.pack(fill="x", pady=(4, 8))
        self.report.configure(state="disabled")

        footer = ttk.Frame(self, padding=(12, 9))
        footer.pack(fill="x")
        ttk.Label(
            footer, textvariable=self.stage, wraplength=650,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Button(
            footer, text="Review fixed self-report", command=self._review,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            footer, text="Copy reviewed report (separate consent)",
            command=self._copy,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            footer, text="Close / discard local report",
            command=self._dismiss,
        ).pack(side="left")

    def _allowed(self):
        return bool(self.winfo_exists() and self._workbench._allowed())

    def observations(self):
        return {key: field.get() for key, field in self.fields.items()}

    def _show(self, content):
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        if content:
            self.report.insert("1.0", content)
        self.report.configure(state="disabled")

    def _invalidate(self, *_ignored):
        self._reviewed_answers = None
        self._reviewed_json = None
        self._show("")
        self.stage.set("Changed answer: old preview invalid. Review again.")

    def _review(self):
        if not self._allowed():
            return
        answers = self.observations()
        try:
            report = build_portable_owner_report(answers)
        except ValueError:
            self._invalidate()
            self.stage.set("Invalid checklist choice. Nothing copied.")
            return
        payload = json.dumps(report, sort_keys=True, indent=2)
        self._reviewed_answers = answers
        self._reviewed_json = payload
        self._show(payload)
        self.stage.set(
            "Preview only. Not saved/uploaded. Copy requires a separate "
            "YES. Copy may remain on the Windows clipboard after exit."
        )

    def _copy(self):
        if not self._allowed():
            return
        if (self._reviewed_answers is None or
                self.observations() != self._reviewed_answers or
                self._reviewed_json is None):
            self.stage.set("BLOCKED: review the exact current report first.")
            return
        approved = messagebox.askyesno(
            "VARYN | Copy self-report?",
            "Copy this fixed self-report to the Windows clipboard? "
            "It contains no transcript or credentials. Clipboard data may "
            "remain after VARYN closes. No upload is performed.",
            parent=self, default="no",
        )
        if not approved:
            self.stage.set("Copy declined. Existing clipboard unchanged.")
            return
        # Revalidate after the modal; an answer change invalidates approval.
        if (self._reviewed_answers is None or
                self.observations() != self._reviewed_answers or
                self._reviewed_json is None):
            self.stage.set("BLOCKED: report changed during review.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._reviewed_json)
            self.update_idletasks()
        except tk.TclError:
            self.stage.set("Clipboard unavailable; report was not copied.")
            return
        self.stage.set(
            "Fixed self-report copied locally. Paste it only where you "
            "choose. No provider delivery or human identity was verified."
        )

    def _dismiss(self):
        self._reviewed_answers = None
        self._reviewed_json = None
        self._show("")
        if getattr(self._workbench, "_owner_checklist_window", None) is self:
            self._workbench._owner_checklist_window = None
        self.destroy()
