"""Focused product acceptance for user-selected encrypted memory and Telegram."""
from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import zipfile

from varyn.owner_memory_import import (
    parse_chatgpt_export, import_selected, load_vault,
    search_memory, MemoryImportRejected,
)
from varyn.telegram_channel import TelegramChannel, TelegramRejected
from varyn.model_registry import Offer
from varyn.usage_budget import UsageBudget


def sample_export(path):
    raw = [
        {
            "id":"conversation-1",
            "title":"Project requirements",
            "mapping":{
                "a":{"message":{"author":{"role":"user"},"create_time":1,
                    "content":{"parts":["Please remember the deployment plan."]}}},
                "b":{"message":{"author":{"role":"assistant"},"create_time":2,
                    "content":{"parts":["Review deployments before shipping."]}}},
                "c":{"message":{"author":{"role":"tool"},"create_time":3,
                    "content":{"parts":["PRIVATE TOOL OUTPUT SHOULD NOT IMPORT"]}}},
            },
        },
        {
            "id":"conversation-2",
            "title":"Travel plans",
            "mapping":{
                "z":{"message":{"author":{"role":"user"},"create_time":4,
                    "content":{"parts":["Visit Bali this month."]}}},
            },
        },
    ]
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr("conversations.json",json.dumps(raw))
        archive.writestr("../unsafe.txt","IGNORED")
    return raw


class ImportAndPrivacyTests(unittest.TestCase):
    def test_zip_preview_reads_only_text_and_never_extracts_archive(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"chatgpt.zip"
            sample_export(path)
            rows=parse_chatgpt_export(path)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]["title"],"Project requirements")
            self.assertNotIn("PRIVATE TOOL OUTPUT",rows[0]["content"])
            self.assertFalse((Path(folder)/"unsafe.txt").exists())

    def test_invalid_zip_rejected_without_import(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/"broken.zip"
            p.write_bytes(b"bad ZIP")
            with self.assertRaises(MemoryImportRejected):
                parse_chatgpt_export(p)

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
    def test_user_selected_records_saved_encrypted_and_searchable(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/"source.zip"
            vault=Path(folder)/"context.varyn"
            sample_export(path)
            rows=parse_chatgpt_export(path)
            result=import_selected(rows,[rows[0]["source"]],path=vault)
            self.assertEqual(result,{"added":1,"total":1})
            self.assertNotIn(b"deployment plan",vault.read_bytes())
            self.assertEqual(len(load_vault(vault)),1)
            self.assertEqual(len(search_memory("deployment",path=vault)),1)
            self.assertEqual(search_memory("Bali",path=vault),[])
            self.assertEqual(import_selected(rows,[rows[0]["source"]],path=vault)["added"],0)


class TelegramChannelTests(unittest.TestCase):
    def setUp(self):
        self.offer=Offer(
            "openrouter","test-model",100000,100000,
            date.today().isoformat(),True,True,True,
        )
        self.budget=UsageBudget()

    def _bot(self,transport):
        with patch.dict(os.environ,{"OPENROUTER_API_KEY":"synthetic-only-api-key"}):
            return TelegramChannel(
                "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1",
                "123456789", self.offer,budget=self.budget,
                transport=transport,
            )

    def test_unauthorized_sender_and_groups_do_not_respond(self):
        calls=[]
        bot=self._bot(lambda action,payload:calls.append((action,payload)))
        bot.process_message({"message":{"chat":{"type":"private","id":123456789},
                                            "from":{"id":999999},"text":"/start"}})
        bot.process_message({"message":{"chat":{"type":"group","id":123456789},
                                            "from":{"id":123456789},"text":"/ask test"}})
        self.assertEqual(calls,[])

    def test_owner_ask_requires_second_explicit_confirm(self):
        calls=[]
        bot=self._bot(lambda action,payload:calls.append((action,payload)))
        owner=lambda msg:{"message":{"chat":{"type":"private","id":123456789},
                                      "from":{"id":123456789},"text":msg}}
        bot.process_message(owner("/ask Explain the deployment plan"))
        self.assertEqual(len(calls),1)
        self.assertEqual(bot._requests,0)
        self.assertIn("/confirm",calls[0][1]["text"])
        bot.process_message(owner("/confirm WRONG"))
        self.assertEqual(bot._requests,0)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(entry[1]["chat_id"]==123456789 for entry in calls))

    def test_missing_allowlist_or_credential_is_rejected(self):
        with patch.dict(os.environ,{"OPENROUTER_API_KEY":"valid"},clear=False):
            with self.assertRaises(TelegramRejected):
                TelegramChannel(
                    "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1",
                    "0",self.offer,budget=self.budget,
                )


if __name__ == "__main__":
    unittest.main()
