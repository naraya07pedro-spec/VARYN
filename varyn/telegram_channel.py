"""Owner-started, allowlisted Telegram Bot API long-poll channel.

Not a BotFather integration, not WhatsApp, not 24/7 cloud hosting.
No legacy ChatGPT credentials and no provider calls without /ask + /confirm.
"""
from __future__ import annotations

from datetime import date
import json
import os
import queue
import re
import secrets
import threading
import time
import urllib.request
import urllib.error

from varyn.gateway_chat import KEY_ENVS, SafeProviderHTTPError
from varyn.model_registry import Registry, RegistryRejected, Offer
from varyn.universal_gateway import UniversalGateway
from varyn.providers import ProviderError
from varyn.usage_budget import BudgetExceeded

_TOKEN = re.compile(r"\A[0-9]{5,20}:[A-Za-z0-9_-]{20,100}\Z")
_UID = re.compile(r"\A[1-9][0-9]{3,18}\Z")


class TelegramRejected(ValueError):
    pass


def validate_config(token, user_id, offer, *, key=None):
    if type(token) is not str or not _TOKEN.fullmatch(token):
        raise TelegramRejected("Invalid Telegram bot token format")
    if type(user_id) is not str or not _UID.fullmatch(user_id):
        raise TelegramRejected("Enter your numeric Telegram user ID")
    if type(offer) is not Offer or offer.provider not in ("openrouter", "deepseek"):
        raise TelegramRejected("Configure a real model in AI Settings first")
    if not offer.eligible(date.today()):
        raise TelegramRejected("Model price review must be current")
    if key is None:
        key = os.environ.get(KEY_ENVS[offer.provider], "")
    if type(key) is not str or not key.strip():
        raise TelegramRejected("Model provider API key missing")
    return int(user_id)


class TelegramChannel:
    """Explicitly owner-started polling, one authorized private user only.

    Commands: /start /help /status /ask text /confirm CODE /cancel.
    Each approved outgoing /ask is capped to one call, with no retries.
    """

    def __init__(self, token, user_id, offer, *, budget, callback=None, transport=None):
        from varyn.usage_budget import UsageBudget
        self.allowed_id = validate_config(token, user_id, offer)
        if type(budget) is not UsageBudget:
            raise TelegramRejected("Missing shared request budget")
        self._token = token
        self.offer = offer
        self._budget = budget
        self.callback = callback
        self._transport = transport
        self._stop = threading.Event()
        self._thread = None
        self._pending = None
        self._offset = None
        self._requests = 0

    def _api(self, method, params=None, timeout=15):
        if self._transport is not None:
            return self._transport(method, params or {})
        request = urllib.request.Request(
            "https://api.telegram.org/bot" + self._token + "/" + method,
            data=json.dumps(params or {}, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(131073)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            # Never log or chain a request URL containing the bot token.
            raise TelegramRejected("Telegram network request failed") from None
        if len(raw) > 131072:
            raise TelegramRejected("Telegram response exceeds limit")
        try:
            data = json.loads(raw)
        except (UnicodeError, ValueError):
            raise TelegramRejected("Invalid Telegram response") from None
        if type(data) is not dict or data.get("ok") is not True:
            raise TelegramRejected("Telegram API did not accept request")
        return data.get("result")

    def _report(self, message):
        if self.callback is not None:
            try:
                self.callback(message)
            except Exception:
                pass

    def _send(self, message):
        # Always send only to the explicitly configured owner.
        self._api("sendMessage", {
            "chat_id": self.allowed_id,
            "text": str(message)[:3500],
            "disable_web_page_preview": True,
        })

    def _prepare(self, text):
        if len(text) > 3500 or not text.strip():
            return "Please send a question of 1–3500 characters."
        code = secrets.token_hex(3).upper()
        self._pending = (code, text, time.monotonic() + 120)
        self._send(
            "VARYN will send this question to " + self.offer.provider +
            " / " + self.offer.model + " (provider may charge for it).\n\n" +
            text +
            "\n\nReply /confirm " + code + " within 2 minutes to approve " +
            "one request, or /cancel. No automatic retry."
        )
        return None

    def _confirm(self, code):
        pending = self._pending
        self._pending = None
        if pending is None or code != pending[0] or time.monotonic() > pending[2]:
            return "No valid pending request. Start again with /ask."
        if self._requests >= 15:
            return "Session Telegram limit reached (15 requests). Restart deliberately."
        self._requests += 1
        try:
            registry = Registry([self.offer])
            estimate = registry.choose(
                input_estimate=512, output_limit=512,
                ceiling_micro_usd=1000000000, today=date.today(),
            )[1]
            gateway = UniversalGateway(
                registry, allow_network=True,
                budget=self._budget,
            )
            answer = gateway.generate(
                pending[1], input_estimate=512, max_output_tokens=512,
                ceiling_micro_usd=estimate, provider=self.offer.provider,
                approve_request=True, allow_real_task=True,
                timeout_seconds=25,
            )
            return answer["reply"].text[:3400] or "Provider returned an empty reply."
        except SafeProviderHTTPError as exc:
            return "Provider declined request: " + exc.category + ". No retry."
        except (RegistryRejected, ProviderError, BudgetExceeded, ValueError,
                PermissionError, OSError):
            return "Request failed or local budget exhausted. No retry."
        except Exception:
            return "Request failed. No retry."

    def process_message(self, update):
        """Never respond to unauthorized accounts, groups or bot messages."""
        if type(update) is not dict:
            return
        message = update.get("message")
        if type(message) is not dict:
            return
        chat, sender = message.get("chat"), message.get("from")
        if type(chat) is not dict or type(sender) is not dict:
            return
        if (chat.get("type") != "private" or
                chat.get("id") != self.allowed_id or
                sender.get("id") != self.allowed_id or
                sender.get("is_bot") is True):
            return
        text = message.get("text")
        if type(text) is not str or len(text) > 4000:
            return
        text = text.strip()
        if text in ("/start", "/help"):
            self._send("VARYN Telegram (owner-only)\n/ask your question — preview\n"
                       "/confirm CODE — approve ONE provider request\n"
                       "/cancel — cancel\n/status — status.\n"
                       "Replies use your own model API credits.")
        elif text == "/status":
            self._send(
                "Connected to " + self.offer.provider + "/" + self.offer.model +
                ". Requests this session: " + str(self._requests) +
                ". This bot runs only while the VARYN desktop is open."
            )
        elif text == "/cancel":
            self._pending = None
            self._send("Pending request cancelled.")
        elif text.startswith("/ask "):
            response = self._prepare(text[5:].strip())
            if response:
                self._send(response)
        elif text.startswith("/confirm "):
            self._send(self._confirm(text[9:].strip().upper()))
        else:
            self._send("Use /ask followed by your question. Ordinary messages "
                       "do not trigger provider calls.")

    def run_once(self, updates):
        if type(updates) is not list:
            raise TelegramRejected("Invalid Telegram updates")
        for update in updates[:100]:
            if type(update) is not dict or type(update.get("update_id")) is not int:
                continue
            uid = update["update_id"]
            if self._offset is not None and uid < self._offset:
                continue
            self._offset = uid + 1
            self.process_message(update)

    def start(self):
        if self._thread is not None:
            raise TelegramRejected("Channel already started")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="VARYN-Telegram", daemon=True,
        )
        self._thread.start()

    def _loop(self):
        try:
            self._api("getMe", {}, timeout=8)
            # Discard prior backlog rather than reading historical messages.
            initial = self._api("getUpdates", {
                "timeout":0,"limit":100,"allowed_updates":["message"],
            })
            if type(initial) is list:
                for entry in initial:
                    if type(entry) is dict and type(entry.get("update_id")) is int:
                        self._offset = max(
                            self._offset or 0, entry["update_id"]+1,
                        )
            self._report("Telegram connected (owner-only).")
        except TelegramRejected:
            self._report("Telegram authentication or network failed.")
            return
        while not self._stop.is_set():
            try:
                updates = self._api(
                    "getUpdates",
                    {"offset":self._offset, "limit":30, "timeout":10,
                     "allowed_updates":["message"]}, timeout=16,
                )
                self.run_once(updates)
            except TelegramRejected:
                self._report("Telegram connection interrupted. No provider request.")
                if self._stop.wait(5):
                    break
            except Exception:
                self._report("Telegram stopped after unexpected error.")
                break
        self._report("Telegram channel stopped.")

    def stop(self):
        self._stop.set()
        self._pending = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()
