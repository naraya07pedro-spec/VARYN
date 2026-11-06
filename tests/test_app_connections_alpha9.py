"""Regression tests for actual read-only app API adapters and model browsing.

No real keys, no internet and no user account resources in these tests.
"""
from datetime import date
import json
import os
import re
import unittest
from unittest.mock import patch

from varyn.app_api_connections import (
    probe_connection, browse_resources, AppConnectionError,
)
from varyn.consumer_model_picker import fetch_models, ModelListError
from varyn.model_registry import Offer
from varyn.telegram_channel import TelegramChannel
from varyn.usage_budget import UsageBudget


class OfficialReadOnlyAppTests(unittest.TestCase):
    def test_netlify_connect_and_site_listing(self):
        sites = [
            {"name": "my-site", "admin_url": "https://app.netlify.com/sites/my-site"},
            {"name": "unsafe-site", "admin_url": "https://attacker.invalid/sites/x"},
        ]
        transport = lambda name, key: json.dumps(sites).encode("utf-8")
        result = probe_connection("netlify", "synthetic-token", transport=transport)
        self.assertTrue(result["verified_read_only_probe"])
        self.assertEqual(result["label"], "2 accessible sites")
        urls = browse_resources("netlify", "synthetic-token", transport=transport)
        self.assertEqual(urls, (("my-site", "https://app.netlify.com/sites/my-site"),))

    def test_supabase_connect_and_project_listing(self):
        projects = [
            {"ref": "abcdefghijklmnopqrst", "name": "VARYN"},
            {"ref": "../invalid", "name": "Ignore this untrusted ref"},
        ]
        transport = lambda name, key: json.dumps(projects).encode("utf-8")
        result = probe_connection("supabase", "synthetic-token", transport=transport)
        self.assertEqual(result["label"], "2 accessible projects")
        records = browse_resources("supabase", "synthetic-token", transport=transport)
        self.assertEqual(records, (
            ("VARYN", "https://supabase.com/dashboard/project/abcdefghijklmnopqrst"),
        ))

    def test_probes_refuse_unknown_token_or_malformed_response(self):
        for provider in ("netlify", "supabase"):
            with self.assertRaises(AppConnectionError):
                probe_connection(provider, "bad", transport=lambda a,b: b"[]")
            with self.assertRaises(AppConnectionError):
                probe_connection(provider, "synthetic-token",
                                 transport=lambda a,b: b'{"id":"fake"}')

    def test_openrouter_catalog_browsing_without_key_is_only_read_only(self):
        model = {"data":[
            {"id":"demo/sample:free","name":"Sample (free)",
             "pricing":{"prompt":"0","completion":"0"}},
            {"id":"demo/paid","name":"Sample Paid",
             "pricing":{"prompt":"0.000001","completion":"0.000002"}},
        ]}
        out = fetch_models("openrouter", "", transport=lambda a,b:json.dumps(model).encode())
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].label, "Sample (free)")
        self.assertEqual(out[0].input_usd_m, "0")
        with self.assertRaises(ModelListError):
            fetch_models("deepseek", "", transport=lambda a,b:json.dumps(model).encode())


class TelegramKeyTransferTests(unittest.TestCase):
    def test_pasted_in_memory_key_is_used_not_a_fake_env_key(self):
        offer = Offer("openrouter","demo/model",100000,100000,
                      date.today().isoformat(),True,True,True)
        sent=[]
        authorized_id = 123456789
        def fake_api(method, params):
            sent.append((method,params))
            return None
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            bot = TelegramChannel(
                "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1",str(authorized_id),
                offer, budget=UsageBudget(), transport=fake_api,
                api_key="session-key-not-written-to-disk",
            )
        self.assertEqual(bot._api_key,"session-key-not-written-to-disk")
        def inbound(content):
            return {"message":{"chat":{"id":authorized_id,"type":"private"},
                    "from":{"id":authorized_id,"is_bot":False},"text":content}}
        bot.process_message(inbound("/ask Describe a task"))
        code = re.search(r"/confirm ([A-F0-9]{6})",sent[0][1]["text"]).group(1)
        used=[]
        class TestGateway:
            def __init__(self, registry, **kwargs):
                used.append(kwargs.get("api_key"))
            def generate(self, *args, **kwargs):
                class Reply:
                    text="TEST_REPLY"
                return {"reply":Reply()}
        with patch("varyn.telegram_channel.UniversalGateway",TestGateway):
            bot.process_message(inbound("/confirm "+code))
        self.assertEqual(used,["session-key-not-written-to-disk"])
        self.assertEqual(sent[-1][1]["text"],"TEST_REPLY")
        bot.stop()

    def test_confirmation_preview_keeps_full_question_or_rejects_oversize(self):
        offer = Offer("openrouter","demo/model",100000,100000,
                      date.today().isoformat(),True,True,True)
        sent=[]
        bot=TelegramChannel(
            "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1","123456789",offer,
            budget=UsageBudget(),api_key="sample-only-key",
            transport=lambda method,params:sent.append(params),
        )
        question="a"*2200
        self.assertIsNone(bot._prepare(question))
        self.assertIn(question,sent[-1]["text"])
        self.assertIn("/confirm",sent[-1]["text"])
        self.assertIsNotNone(bot._prepare("b"*3000))
        bot.stop()


if __name__ == "__main__":
    unittest.main()
