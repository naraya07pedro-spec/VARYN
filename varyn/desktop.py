"""Lightweight standard-library Tkinter VARYN desktop window.

Run: python -m varyn.desktop
This stage is OFFLINE ONLY. Provider dropdown options are previews, not live
integrations. No web server, account, local model, persistent chat or API calls.
"""
import tkinter as tk
from tkinter import ttk

from varyn.desktop_controller import DesktopController, DEFAULT_MODELS, PROVIDERS


class VarynDesktop(tk.Tk):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller or DesktopController()
        self.title("VARYN  |  Local AI Workspace (Offline MVP)")
        self.geometry("760x620")
        self.minsize(540, 480)
        self.configure(bg="#111827")
        self.provider = tk.StringVar(value="fake")
        self.model = tk.StringVar(value="fake-test")
        self.consent_network = tk.BooleanVar(value=False)
        self.consent_context = tk.BooleanVar(value=False)
        self.status_line = tk.StringVar(value="")
        self._build()
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
            outer,
            text="LOCAL-FIRST   |   OFFLINE SIMULATION ONLY   |   NO API REQUESTS",
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
        ttk.Label(settings, text="Model (not connected)", style="V.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Entry(settings, textvariable=self.model, width=27).grid(
            row=1, column=1, sticky="we", pady=4
        )
        settings.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            outer, text="Network permission requested (live mode still disabled)",
            variable=self.consent_network, command=self._permissions_changed,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(
            outer, text="Allow reference context (not loaded automatically)",
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
        buttons = ttk.Frame(outer, style="V.TFrame")
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="Send offline", command=self._send).pack(side="left")
        ttk.Button(buttons, text="Clear RAM chat", command=self._clear).pack(
            side="left", padx=8
        )
        ttk.Label(
            outer, text="No history saved. Quota resets when the application restarts.",
            style="V.TLabel",
        ).pack(anchor="w")
        self._append(
            "SYSTEM", "This is a synthetic, offline UI test. Select fake to send. "
            "OpenAI, Anthropic and Gemini entries are previews only."
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
            f"NETWORK OFF  |  Requests {state['requests_used']}/{state['requests_limit']}  "
            f"| Reserved output {state['output_tokens_reserved']}/"
            f"{state['output_tokens_limit']} tokens"
        )

    def _append(self, who, message):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{who}: {message}\n\n")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _send(self):
        message = self.prompt.get("1.0", "end-1c")
        try:
            reply = self.controller.send(
                message, provider=self.provider.get(), model=self.model.get(),
            )
        except (ValueError, PermissionError, RuntimeError) as error:
            # The exceptions reaching UI are bounded generic messages; no
            # raw HTTP or API exception is exposed in this offline stage.
            self._append("NOTICE", str(error))
            self._refresh_status()
            return
        self._append("YOU", message.strip())
        self._append("VARYN", reply.answer)
        self.prompt.delete("1.0", "end")
        self._refresh_status()

    def _clear(self):
        self.controller.clear_history()
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self._refresh_status()


def main():
    try:
        window = VarynDesktop()
    except tk.TclError:
        raise SystemExit("A graphical desktop session is required")
    window.mainloop()


if __name__ == "__main__":
    main()
