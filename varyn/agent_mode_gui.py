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
from varyn.grounded_github import GroundingRejected
from varyn.learning_kernel import LearningKernel
from varyn.owner_live_evaluation import OwnerReviewedLiveEvaluation, PUBLIC_CASE_REPOSITORIES
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
        self.geometry("770x680")
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
        self.store_verified_facts = tk.BooleanVar(master=self, value=False)
        self.use_learned_skill = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(
            body, variable=self.allow_read,
            text="Allow ONE reviewed public GitHub read",
        ).pack(anchor="w", pady=(9, 0))
        ttk.Checkbutton(
            body, variable=self.allow_send_observation,
            text="Allow public metadata in second reviewed AI request",
        ).pack(anchor="w", pady=(3, 2))
        ttk.Checkbutton(
            body, variable=self.store_verified_facts,
            text="Store hashed fact-match receipts AND failure categories (local only)",
        ).pack(anchor="w", pady=(3, 2))
        ttk.Checkbutton(
            body, variable=self.use_learned_skill,
            text="Include an existing learned skill in exact AI request review",
        ).pack(anchor="w", pady=(3, 9))
        row = ttk.Frame(body)
        row.pack(fill="x")
        self.start = ttk.Button(
            row, text="Review and run", command=self.run)
        self.start.pack(side="left")
        self.eval_optin = tk.BooleanVar(master=self, value=False)
        self.eval_checkbox = ttk.Checkbutton(
            body, variable=self.eval_optin,
            text="I authorize a separate 5-GitHub-read / 10-AI-call evaluation "
                 "session (may incur actual provider charges)",
        )
        self.eval_checkbox.pack(anchor="w", pady=(10, 4))
        eval_row = ttk.Frame(body)
        eval_row.pack(fill="x")
        self.eval_status_button = ttk.Button(
            eval_row, text="Check learning readiness",
            command=self.check_learning_readiness)
        self.eval_status_button.pack(side="left")
        self.eval_button = ttk.Button(
            eval_row, text="Run live learning evaluation",
            command=self.run_live_evaluation)
        self.eval_button.pack(side="left", padx=(12, 0))
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
        save_receipt = self.store_verified_facts.get()
        use_skill = self.use_learned_skill.get()
        self.allow_read.set(False)
        self.allow_send_observation.set(False)
        self.store_verified_facts.set(False)
        self.use_learned_skill.set(False)
        self.chat.allow_network.set(False)
        self.start.configure(state="disabled")
        self._busy = True
        self.status.set("Preparing the first exact-request review...")
        self._show("")
        Thread(
            target=self._worker,
            args=(task, provider, offer, secret, read, upload,
                  save_receipt, use_skill),
            daemon=True,
        ).start()
        self._after_id = self.after(70, self._poll)

    def _learning_location(self):
        root = Path(
            os.environ.get("LOCALAPPDATA")
            or (Path.home() / "AppData" / "Local")) / "VARYN"
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError("Learning storage root cannot be a link")
        return root

    def _learning_readiness(self, provider, offer, secret):
        # This only checks local evidence and request budgets. NO network.
        root = self._learning_location()
        with LearningKernel(root / "learning.sqlite3") as kernel:
            gateway = UniversalGateway(
                Registry([offer]), allow_network=False,
                budget=self.desktop._universal_model_budget, api_key=secret)
            tool = PublicGithubToolGateway(max_requests=5)
            try:
                runner = OwnerReviewedLiveEvaluation(gateway, tool, kernel)
                return runner.readiness(
                    provider=provider, max_total_estimate_micro_usd=100000)
            finally:
                tool.close()

    def check_learning_readiness(self):
        if self._closed or self._busy:
            return
        from varyn.simple_chat import _PROVIDER
        provider = _PROVIDER.get(self.chat.mode.get())
        offer = self.chat._offers.get(provider) if provider else None
        secret = (self.chat._session_keys.get(provider)
                  or os.environ.get(KEY_ENVS.get(provider, ""), "")) if provider else ""
        if offer is None or not secret:
            self.status.set("Learning readiness: configure a live provider, "
                            "model pricing and API key in Chat.")
            return
        try:
            info = self._learning_readiness(provider, offer, secret)
        except Exception:
            self.status.set("Learning readiness unavailable. Check local "
                            "database and reviewed model pricing.")
            return
        self.status.set(
            "Learning: " + info["status"] +
            " | verified successes " + str(info["verified_successes"]) +
            " | recorded failures " + str(info["verified_failures"]) +
            " | remaining session budget required: 10 AI requests."
        )

    def run_live_evaluation(self):
        if self._closed or self._busy:
            return
        if self.eval_optin.get() is not True:
            self.status.set("Live learning is disabled until the separate "
                            "evaluation-session checkbox is enabled.")
            return
        try:
            provider, offer, secret = self._config()
            info = self._learning_readiness(provider, offer, secret)
        except Exception:
            self.status.set("Configure a fresh live model, API key, and one "
                            "online session permission in Chat first.")
            return
        if info["status"] != "ready":
            self.status.set(
                "Learning not started: " + info["status"] +
                ". Requires 2 distinct verified public fact receipts, "
                "1 recorded mismatch, and 10 available model requests.")
            return
        summary = json.dumps({
            "purpose": "ONE live comparison of an offline fixed skill and "
                       "the current baseline on 5 public GitHub repositories",
            "provider": provider, "model": offer.model,
            "public_repositories": PUBLIC_CASE_REPOSITORIES,
            "maximum_github_gets": 5,
            "maximum_model_calls": 10,
            "maximum_reserved_output_tokens": 2560,
            "estimated_total_micro_usd": info["estimated_micro_usd"],
            "real_billing_hard_cap": False,
            "requirements": "All fifteen requests require separate "
                            "explicit owner confirmation. Cancel at any point.",
        }, indent=2)
        approved = self.desktop._review_scrollable_manual_text(
            title="VARYN | Authorize one live evaluation session",
            heading="Up to 5 GitHub GETs + 10 billable AI calls",
            digest=sha256(summary.encode("utf-8")).hexdigest(),
            content=summary,
            warning="Provider billing may exceed estimates. There is no "
                    "provider-enforced monetary ceiling. Public metadata "
                    "only; no private repo or write action. NO auto-retries.",
            approve_label="Review each individual evaluation request",
        ) is True
        if not approved or self._closed:
            self.status.set("Live evaluation was not authorized. No requests sent.")
            return
        self.eval_optin.set(False)
        self.chat.allow_network.set(False)
        self.start.configure(state="disabled")
        self.eval_button.configure(state="disabled")
        self.eval_status_button.configure(state="disabled")
        self._busy = True
        self.status.set("Live evaluation running: approve each public read "
                        "and model request separately. No auto-retries.")
        self._show("Five approved GitHub cases will be collected. Then a "
                   "10-request model comparison will run only if all "
                   "prior checks pass.")
        Thread(target=self._learning_worker,
               args=(provider, offer, secret), daemon=True).start()
        self._after_id = self.after(70, self._poll)

    def _learning_worker(self, provider, offer, secret):
        learning = None
        tool = None
        try:
            learning = LearningKernel(
                self._learning_location() / "learning.sqlite3")
            tool = PublicGithubToolGateway(max_requests=5)
            with self._lock:
                self._tool = tool
            model = UniversalGateway(
                Registry([offer]), allow_network=True,
                budget=self.desktop._universal_model_budget, api_key=secret)
            evaluation = OwnerReviewedLiveEvaluation(model, tool, learning)
            result = evaluation.run(
                provider=provider, owner_enabled=True,
                review_model=lambda p: self._request_review("model", p),
                review_tool=lambda p: self._request_review("tool", p),
                max_total_estimate_micro_usd=100000,
                input_estimate=512, output_limit=256)
            self._completions.put(("learning", result))
        except BaseException:
            self._completions.put(("learning_error", None))
        finally:
            if tool is not None:
                tool.close()
            with self._lock:
                self._tool = None
            if learning is not None:
                learning.close()

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

    def _worker(self, task, provider, offer, secret, read, upload,
                save_receipt, use_skill):
        tool = None
        journal = None
        learning = None
        try:
            location = Path(
                os.environ.get("LOCALAPPDATA")
                or (Path.home() / "AppData" / "Local")) / "VARYN"
            location.mkdir(parents=True, exist_ok=True)
            if location.is_symlink():
                raise ValueError("Local journal root cannot be a link")
            journal = AgentLoopJournal(location / "agent-loop.sqlite3")
            journal.recover()  # Mark interrupted actions for review; never replay.
            if save_receipt or use_skill:
                learning = LearningKernel(location / "learning.sqlite3")
            tool = PublicGithubToolGateway()
            with self._lock:
                self._tool = tool
            model = UniversalGateway(
                Registry([offer]), allow_network=True,
                budget=self.desktop._universal_model_budget, api_key=secret)
            loop = OwnerApprovedAgentLoop(
                model, tool, journal, learning_kernel=learning)
            result = loop.run(
                task, provider=provider,
                review_model=lambda p: self._request_review("model", p),
                review_tool=lambda p: self._request_review("tool", p),
                allow_public_network=read, allow_metadata_upload=upload,
                input_estimate=512, max_output_tokens=512,
                ceiling_micro_usd=100000, verify_public_facts=True,
                persist_grounded_receipt=save_receipt,
                include_learned_skill=use_skill)
            self._completions.put(("result", result))
        except GroundingRejected:
            self._completions.put(("fact_mismatch", None))
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
            if learning is not None:
                learning.close()

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
        self.eval_button.configure(state="normal")
        self.eval_status_button.configure(state="normal")
        if kind == "learning":
            self.status.set(
                "Learning evaluation: " + result.get("status", "unknown") +
                " | public reads " + str(result.get("public_reads", 0)) +
                " | AI calls " + str(result.get("model_calls", 0)))
            self._show(
                "Model quality change requires independent held-out "
                "verification. Status: " + result.get("status", "unknown") +
                "
Provider billing is not capped by local estimates.")
            return
        if kind == "learning_error":
            self.status.set("Evaluation stopped or was denied. No automatic "
                            "retry. Any consumed budget remains reserved.")
            self._show("Check local run history before attempting a new "
                       "session. Previous provider charges may still apply.")
            return
        if kind == "fact_mismatch":
            self.status.set("AI facts failed GitHub verification. "
                            "No success receipt saved. A hashed failure category "
                            "is stored only if feedback opt-in was enabled.")
            self._show("The AI report did not match the approved tool evidence.")
            return
        if kind != "result":
            self.status.set("Agent stopped safely. Check model access, "
                            "local budget or journal; no automatic retry.")
            return
        status = result.get("status", "unknown")
        detail = ""
        if result.get("verified_public_facts"):
            detail = " · Facts checked against public GitHub tool data"
            saved = result.get("learning_receipt_status")
            if saved == "recorded":
                detail += " · Hashed evidence saved"
            elif saved == "duplicate":
                detail += " · Existing evidence reused"
            elif saved == "not_recorded":
                detail += " · Evidence saving failed"
        self.status.set("Agent finished with status: " + status + detail)
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
