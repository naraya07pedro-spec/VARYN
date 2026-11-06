"""Owner usability: tested live-catalog parsing, session keys, and app adapters.

All test provider payloads are fictional and no network requests are made.
"""
from datetime import date
import json
import os
from unittest.mock import patch
import unittest

from varyn.consumer_model_picker import (
    parse_list, fetch_models, ModelListError,
)
from varyn.app_api_connections import (
    probe_connection, browse_resources, AppConnectionError,
)
from varyn.model_registry import Offer, Registry
from varyn.universal_gateway import UniversalGateway


class OwnerModelPickerTests(unittest.TestCase):
    def test_openrouter_catalog_uses_actual_provider_model_ids_and_prices(self):
        raw = json.dumps({"data":[
            {"id":"anthropic/fake-sonnet-test","name":"Fictional Sonnet",
             "pricing":{"prompt":"0.000002","completion":"0.000009"}},
            {"id":"free/test-model:free","name":"Free fictional model",
             "pricing":{"prompt":"0","completion":"0"}},
            {"id":"bad model id","name":"No"},
            {"id":"unpriced/model","name":"No published price",
             "pricing":{"prompt":None,"completion":None}},
        ]}).encode()
        out = parse_list("openrouter",raw)
        listed={x.id:x for x in out}
        self.assertEqual(listed["anthropic/fake-sonnet-test"].input_usd_m,"2.000000")
        self.assertEqual(listed["anthropic/fake-sonnet-test"].output_usd_m,"9.000000")
        self.assertEqual(listed["free/test-model:free"].input_usd_m,"0")
        self.assertIsNone(listed["unpriced/model"].input_usd_m)
        self.assertNotIn("bad model id",listed)

    def test_deepseek_model_list_uses_published_peak_rate_snapshot(self):
        raw=json.dumps({"data":[{"id":"deepseek-flash","name":"DeepSeek Flash"},
             {"id":"deepseek-v4-pro","name":"DeepSeek Pro"}]}).encode()
        rows={x.id:x for x in parse_list("deepseek",raw)}
        self.assertEqual(rows["deepseek-flash"].input_usd_m,"0.30")
        self.assertEqual(rows["deepseek-v4-pro"].output_usd_m,"3.96")

    def test_catalog_needs_exact_owner_key_but_transport_is_bounded(self):
        raw=json.dumps({"data":[{"id":"test/ok","name":"OK",
            "pricing":{"prompt":"0","completion":"0"}}]}).encode()
        self.assertEqual(
            fetch_models("openrouter","fictional-key",transport=lambda p,k:raw)[0].id,
            "test/ok",
        )
        with self.assertRaises(ModelListError):
            fetch_models("unknown","fictional-key",transport=lambda p,k:raw)

    def test_gateway_accepts_a_ram_only_key_without_environment_mutation(self):
        model=Offer("openrouter","fictional/model",200000,800000,
                    date.today().isoformat(),True,True,True)
        sends=[]
        def send(provider,payload,key,timeout):
            sends.append((provider,payload,key,timeout))
            return json.dumps({
                "choices":[{"finish_reason":"stop",
                            "message":{"content":"Fictional answer"}}],
                "model":"fictional/model",
                "usage":{"prompt_tokens":10,"completion_tokens":10},
            }).encode()
        with patch.dict(os.environ,{"OPENROUTER_API_KEY":""}):
            gate=UniversalGateway(
                Registry([model]),allow_network=True,transport=send,
                api_key="session-example-only",
            )
            result=gate.generate(
                "SYNTHETIC: safe example",provider="openrouter",
                input_estimate=256,max_output_tokens=256,
                ceiling_micro_usd=1000000000,approve_request=True,
            )
        self.assertEqual(len(sends),1)
        self.assertEqual(sends[0][2],"session-example-only")
        self.assertEqual(result["reply"].text,"Fictional answer")


class AppConnectionTests(unittest.TestCase):
    def test_github_readonly_probe_from_official_account_shape(self):
        raw=json.dumps({"login":"exampleuser","id":234}).encode()
        result=probe_connection("github","fictional-personal-token",
                    transport=lambda service,key:raw)
        self.assertEqual(result["label"],"exampleuser")
        self.assertTrue(result["verified_read_only_probe"])

    def test_notion_readonly_probe(self):
        raw=json.dumps({"object":"user","name":"Workspace Integration",
                        "id":"fake-id"}).encode()
        result=probe_connection("notion","fictional-integration-token",
                    transport=lambda service,key:raw)
        self.assertEqual(result["label"],"Workspace Integration")

    def test_resources_expose_only_official_https_destinations(self):
        raw=json.dumps([
            {"full_name":"exampleuser/demo","html_url":"https://github.com/exampleuser/demo"},
            {"full_name":"bad","html_url":"https://evil.example/phishing"},
        ]).encode()
        got=browse_resources("github","fictional-personal-token",
                  transport=lambda service,key:raw)
        self.assertEqual(got,(("exampleuser/demo","https://github.com/exampleuser/demo"),))

    def test_invalid_account_result_fails_closed(self):
        with self.assertRaises(AppConnectionError):
            probe_connection("notion","fictional-integration-token",
                transport=lambda service,key:b'{"access_token":"secret"}')
        with self.assertRaises(AppConnectionError):
            probe_connection("dropbox","fictional-key",
                transport=lambda service,key:b'{}')


if __name__=="__main__":
    unittest.main()
