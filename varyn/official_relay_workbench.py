"""17S-28: focused owner-facing relay window for ACTUAL official app manual use.

One window for a user-authored synthetic task, manual browser open/copy,
unverified reply pasteback, and opt-in per-project note. Every operation
delegates to the existing VarynDesktop owner approval, TTL, provenance
and clipboard gates. This class never talks to a browser/AI model itself.
"""
import tkinter as tk
from tkinter import ttk

from varyn.official_manual_relay import OFFICIAL_APP_LINKS


class OfficialRelayWorkbench(tk.Toplevel):
    """No silent transfer, background request, remote state or disk usage."""

    def __init__(self, parent):
        if getattr(parent, "_closing", True):
            raise RuntimeError("Cannot open relay workbench while desktop closes")
        super().__init__(parent)
        self._owner = parent
        self.title("VARYN | Official apps: manual workbench, NO sync")
        self.geometry("680x630")
        self.minsize(510, 430)
        self.transient(parent)
        self.target = tk.StringVar(master=self, value="chatgpt")
        self.project = tk.StringVar(master=self, value="VARYN")
        self.topic = tk.StringVar(master=self, value="next_step")
        self.include_context = tk.BooleanVar(master=self, value=False)
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
        self._owner._copy_official_app_relay(
            task=task, target=self.target.get(),
            project=self.project.get(),
            include_context=self.include_context.get() is True,
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
        self._owner._review_official_app_reply(reply=reply)
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
        self.refresh()

    def _discard_notes(self):
        if not self._allowed():
            return
        self._owner._discard_project_working_notes()
        self.include_context.set(False)
        self.refresh()

    def refresh(self):
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
        # A closed workbench removes only its own editable widgets.
        # The owner can explicitly discard relay/board state in the main UI.
        if getattr(self._owner, "_relay_workbench", None) is self:
            self._owner._relay_workbench = None
        self.destroy()
