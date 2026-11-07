"""Owner-visible read-only GitHub agent window for the VARYN consumer chat.

Worker threads never create Tk widgets or approve their own tool calls.
Every network request and public read is reviewed through the existing
owner desktop modal. This is experimental, not a background daemon.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
import json
import os
import tkinter as tk
from tkinter import ttk

from varyn.agent_execution_loop import OwnerApprovedAgentLoop
from varyn.agent_loop_journal import AgentLoopJournal
from varyn.gateway_chat import KEY_ENVS
from varyn.model_registry import Registry
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.universal_gateway import UniversalGateway


class OwnerAgentWindow(tk.Toplevel):
    """Explicit owner action, one public GET max, no private GitHub scopes."""

    def __init__(self, chat):
        super().__init__(chat)
        self.chat = chat
        self.desktop = chat.desktop
        self._closed = False
        self._busy = False
        self._after_id = None
        self._approval_requests = Queue()
        self._completions = Queue()
        self._lock = Lock()
        self._waiters = []
        self._tool = None
        self.title("VARYN | Public GitHub Agent (experimental)")
        self.geometry("750x580")
        self.minsize(540, 390)
        self.transient(chat.winfo_toplevel())
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        body = ttk.Frame(self, padding=15)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Read-only GitHub agent",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(body, wraplength=680, justify="left",
                  text="Uses your configured OpenRouter or DeepSeek model. "
                  "Can inspect ONE public repository only. "
                  "Every outgoing model request and GitHub read requires "
                  "a separate owner review. No writes or private repos.").pack(
                      anchor="w", pady=(7, 10))
        self.goal = tk.Text(body, height=4, wrap="word")
        self.goal.pack(fill="x")
        self.goal.insert("1.0",
                         "Inspect the public GitHub repository "
                         "naraya07pedro-spec/VARYN and summarize its status.")
        self.allow_read = tk.BooleanVar(master=self, value=False)
        self.allow_send_observation = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(
            body, variable=self.allow_read,
            text="Allow ONE reviewed public GitHub read",
        ).pack(anchor="w", pady=(9, 0))
        ttk.Checkbutton(
            body, variable=self.allow_send_observation,
            text="Allow public metadata in second reviewed AI request",
        ).pack(anchor="w", pady=(3, 9))
        row = ttk.Frame(body)
        row.pack(fill="x")
        self.start = ttk.Button(
            row, text="Review and run", command=self.run)
        self.start.pack(side="left")
        self.status = tk.StringVar(
            master=self, value="OFFLINE. Select an AI model and allow "
                               "one internet request in Chat first.")
        ttk.Label(body, textvariable=self.status, wraplength=660).pack(
            anchor="w", pady=(12, 7))
        self.output = tk.Text(body, state="disabled", wrap="word", height=11)
        self.output.pack(fill="both", expand=True)

    def _show(self, text):
        if self._closed:
            return
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def _config(self):
        # All Tk access occurs on the owner UI thread.
        from varyn.simple_chat import _PROVIDER
        provider = _PROVIDER.get(self.chat.mode.get())
        if provider is None:
            raise ValueError("Choose OpenRouter or DeepSeek in the chat settings")
        offer = self.chat._offers.get(provider)
        if offer is None:
            raise ValueError("Configure a reviewed model and price in chat settings")
        secret = (self.chat._session_keys.get(provider)
                  or os.environ.get(KEY_ENVS[provider], ""))
        if not isinstance(secret, str) or not secret.strip():
            raise ValueError("Provider API key is unavailable in this session")
        if (not self.desktop._universal_model_live_capability
                or not self.chat.allow_network.get()):
            raise PermissionError("Enable one approved online agent session in Chat")
        return provider, offer, secret

    def run(self):
        if self._busy or self._closed:
            return
        task = self.goal.get("1.0", "end-1c").strip()
        if not 1 <= len(task) <= 800:
            self.status.set("Enter a task of 1 to 800 characters.")
            return
        try:
            provider, offer, secret = self._config()
            # Quote is verified by Registry again before each request.
            Registry([offer])
        except (ValueError, PermissionError, AttributeError):
            self.status.set("Choose a live model, configure its quote and "
                            "key, then enable online permission in Chat.")
            return
        read = self.allow_read.get()
        upload = self.allow_send_observation.get()
        self.allow_read.set(False)
        self.allow_send_observation.set(False)
        self.chat.allow_network.set(False)
        self.start.configure(state="disabled")
        self._busy = True
        self.status.set("Preparing the first exact-request review...")
        self._show("")
        Thread(
            target=self._worker,
            args=(task, provider, offer, secret, read, upload),
            daemon=True,
        ).start()
        self._after_id = self.after(70, self._poll)

    def _request_review(self, kind, preview):
        pending = {"kind": kind, "preview": preview,
                   "event": Event(), "value": False}
        with self._lock:
            if self._closed:
                return False
            self._waiters.append(pending)
        self._approval_requests.put(pending)
        pending["event"].wait(timeout=120)
        with self._lock:
            if pending in self._waiters:
                self._waiters.remove(pending)
            return pending["value"] if pending["event"].is_set() else False

    def _worker(self, task, provider, offer, secret, read, upload):
        tool = None
        journal = None
        try:
            location = Path(
                os.environ.get("LOCALAPPDATA")
                or (Path.home() / "AppData" / "Local")) / "VARYN"
            location.mkdir(parents=True, exist_ok=True)
            if location.is_symlink():
                raise ValueError("Local journal root cannot be a link")
            journal = AgentLoopJournal(location / "agent-loop.sqlite3")
            journal.recover()  # Mark interrupted actions for review; never replay.
            tool = PublicGithubToolGateway()
            with self._lock:
                self._tool = tool
            model = UniversalGateway(
                Registry([offer]), allow_network=True,
                budget=self.desktop._universal_model_budget, api_key=secret)
            loop = OwnerApprovedAgentLoop(model, tool, journal)
            result = loop.run(
                task, provider=provider,
                review_model=lambda p: self._request_review("model", p),
                review_tool=lambda p: self._request_review("tool", p),
                allow_public_network=read, allow_metadata_upload=upload,
                input_estimate=512, max_output_tokens=512,
                ceiling_micro_usd=100000)
            self._completions.put(("result", result))
        except BaseException:
            # Avoid echoing provider exception bodies, prompts, or credentials.
            self._completions.put(("error", None))
        finally:
            if tool is not None:
                tool.close()
            with self._lock:
                self._tool = None
            if journal is not None:
                journal.close()

    def _review_on_ui(self, pending):
        if self._closed:
            pending["event"].set()
            return
        data = pending["preview"]
        if pending["kind"] == "model":
            content = data["exact_outgoing_prompt"]
            heading = ("Approve ONE request to " + data["provider"] +
                       " (" + data["phase"] + ")")
            warning = ("This exact text will leave the PC. "
                       "Provider estimates are not billing limits. "
                       "No automatic retries.")
        else:
            content = json.dumps({
                "tool": data.tool, "repository": data.repository,
                "review_digest": data.digest,
                "access": "public metadata only",
            }, indent=2)
            heading = "Approve ONE read-only public GitHub GET"
            warning = ("Only public GitHub metadata will be retrieved; "
                       "this step does not upload it to an AI model.")
        digest = sha256(content.encode("utf-8")).hexdigest()
        approved = False
        try:
            approved = self.desktop._review_scrollable_manual_text(
                title="VARYN | Exact agent action review",
                heading=heading, digest=digest, content=content,
                warning=warning, approve_label="Approve this one action",
            ) is True
        except Exception:
            approved = False
        with self._lock:
            pending["value"] = approved and not self._closed
            pending["event"].set()

    def _poll(self):
        self._after_id = None
        if self._closed:
            return
        try:
            while True:
                pending = self._approval_requests.get_nowait()
                self._review_on_ui(pending)
        except Empty:
            pass
        try:
            kind, result = self._completions.get_nowait()
        except Empty:
            self._after_id = self.after(70, self._poll)
            return
        self._busy = False
        self.start.configure(state="normal")
        if kind != "result":
            self.status.set("Agent stopped safely. Check model access, "
                            "local budget or journal; no automatic retry.")
            return
        status = result.get("status", "unknown")
        self.status.set("Agent finished with status: " + status)
        if status == "completed":
            self._show(result.get("answer", ""))
        elif status in ("observation_only", "synthesis_denied"):
            self._show(json.dumps(result.get("public_metadata", {}),
                                  indent=2, ensure_ascii=False))
        else:
            self._show("No external action beyond the approved steps.")

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        with self._lock:
            for pending in self._waiters:
                pending["value"] = False
                pending["event"].set()
            if self._tool is not None:
                self._tool.revoke_active()
        self.destroy()
