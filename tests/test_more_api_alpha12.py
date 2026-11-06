"""Synthetic acceptance for 5 MORE real official provider adapters.

Deliberately no owner token, networking or mutation. The Windows UI smoke
separately confirms Connect/Browse/Disconnect controls render correctly.
"""
import json
import unittest

from varyn.more_api_connections import (
    APPS, TOKEN_PAGES, probe_more_api, browse_more_api, MoreAPIError,
)

KEY = "synthetic-private-token-no-network"
DATA = {
    "slack": {
        "account": {"ok":True,"team_id":"T123456","team":"Studio","user":"automation"},
        "list": {"ok":True,"channels":[{"id":"C1","name":"engineering"}]},
        "label":"Slack: Studio",
    },
    "linear": {
        "account": {"data":{"viewer":{"id":"user_1","name":"Engineer"}}},
        "list": {"data":{"issues":{"nodes":[
            {"identifier":"ENG-7","title":"Build workflow",
             "url":"https://linear.app/team/issue/ENG-7/build-workflow"},
        ]}}},
        "label":"Linear: Engineer",
    },
    "hubspot": {
        "account": {"results":[]},
        "list": {"results":[{"id":"100","properties":{
            "firstname":"Ada","lastname":"Smith","email":"ada@example.com",
        }}]},
        "label":"HubSpot contacts API authorized",
    },
    "dropbox": {
        "account": {"account_id":"dbid:123","name":{"display_name":"Owner"}},
        "list": {"entries":[{"name":"Project Folder",".tag":"folder"}]},
        "label":"Dropbox: Owner",
    },
    "discord": {
        "account": {"id":"123456789123456789","username":"project-bot","bot":True},
        "list": [{"id":"123456789123456789","name":"Studio Server"}],
        "label":"Discord bot: project-bot",
    },
}


class MoreAPIAdaptersTests(unittest.TestCase):
    def test_supported_providers_have_real_probes_and_browse(self):
        self.assertEqual(len(APPS),5)
        for service in APPS:
            with self.subTest(service=service):
                spec=DATA[service]
                calls=[]
                def transport(app, listing, credential):
                    calls.append((app,listing,credential))
                    return json.dumps(spec["list" if listing else "account"]).encode()
                probe=probe_more_api(service,KEY,transport=transport)
                self.assertEqual(probe["label"],spec["label"])
                self.assertTrue(probe["verified_read_only_probe"])
                rows=browse_more_api(service,KEY,transport=transport)
                self.assertEqual(len(rows),1)
                self.assertTrue(rows[0][1].startswith("https://"))
                self.assertEqual(calls,[(service,False,KEY),(service,True,KEY)])
                self.assertIn(service,TOKEN_PAGES)

    def test_redirect_payload_cannot_open_arbitrary_url(self):
        doc=DATA["linear"]["list"]
        poisoned=json.loads(json.dumps(doc))
        poisoned["data"]["issues"]["nodes"][0]["url"]="https://evil.invalid/steal"
        rows=browse_more_api("linear",KEY,
            transport=lambda *_:json.dumps(poisoned).encode())
        self.assertEqual(rows[0][1],"https://linear.app/")

    def test_discord_requires_bot_not_regular_user_token(self):
        payload={"id":"123456789123456789","username":"owner","bot":False}
        with self.assertRaises(MoreAPIError):
            probe_more_api("discord",KEY,
                transport=lambda *_:json.dumps(payload).encode())

    def test_linear_graphql_error_is_not_mistaken_for_a_connection(self):
        payload={"data":{"viewer":{"id":"a","name":"User"}},
                 "errors":[{"message":"Forbidden"}]}
        with self.assertRaises(MoreAPIError):
            probe_more_api("linear",KEY,
                transport=lambda *_:json.dumps(payload).encode())

    def test_slack_error_is_not_connected(self):
        with self.assertRaises(MoreAPIError):
            probe_more_api("slack",KEY,
                transport=lambda *_:b'{"ok":false,"error":"missing_scope"}')

    def test_malformed_tokens_and_unknown_service_fail_closed(self):
        for service in (*APPS,"fake-provider"):
            with self.assertRaises(MoreAPIError):
                probe_more_api(service,"short",transport=lambda *_:b"{}")
        with self.assertRaises(MoreAPIError):
            probe_more_api("slack",KEY,transport=lambda *_:b"not json")
        with self.assertRaises(MoreAPIError):
            browse_more_api("hubspot",KEY,
                transport=lambda *_:b'{"not_results":[]}')

    def test_discord_guild_id_must_be_numeric(self):
        records=browse_more_api("discord",KEY,transport=lambda *_:
            json.dumps([{"id":"javascript:alert(1)","name":"malicious"},
                        {"id":"123456789123456789","name":"good"}]).encode())
        self.assertEqual(records,[("good","https://discord.com/channels/123456789123456789")] if type(records) is list else (("good","https://discord.com/channels/123456789123456789"),))


if __name__=="__main__":
    unittest.main()
