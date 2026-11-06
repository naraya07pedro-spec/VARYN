"""Focused regression for scalable registry and non-dispatching task ledger."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from varyn.integration_catalog import load_catalog, display_catalog
from varyn.unlimited_task_store import TaskStore, TaskRejected


class CatalogAndTaskTests(unittest.TestCase):
    def test_all_catalog_entries_are_metadata_only(self):
        entries = load_catalog()
        self.assertGreaterEqual(len(entries), 30)
        self.assertEqual(len({(x.kind,x.id) for x in entries}),len(entries))
        self.assertTrue(all(x.available is False for x in entries))
        summary = json.loads(display_catalog())
        self.assertEqual(summary["connected_accounts"],0)
        self.assertEqual(summary["runnable_external_integrations"],0)

    def test_many_tasks_not_artificially_capped_and_pages_bounded(self):
        with TemporaryDirectory() as root:
            with TaskStore(Path(root)/"tasks.sqlite3") as store:
                for i in range(260):
                    store.create("Synthetic task "+str(i),due_utc="2026-11-06T07:00:00+00:00")
                self.assertEqual(store.count(),260)
                self.assertEqual(len(store.list(limit=200)),200)
                self.assertEqual(len(store.list(limit=200,offset=200)),60)
                self.assertEqual(len(store.mark_due(now="2026-11-07T07:00:00Z")),100)
                self.assertEqual(store.count(status="due"),100)
                self.assertEqual(len(store.mark_due(now="2026-11-07T07:00:00Z",batch_size=200)),160)
                self.assertEqual(store.count(status="due"),260)

    def test_validation_no_execution_or_hidden_side_effects(self):
        with TemporaryDirectory() as root:
            with TaskStore(Path(root)/"tasks.sqlite") as store:
                with self.assertRaises(TaskRejected):
                    store.create("")
                with self.assertRaises(TaskRejected):
                    store.create("a",due_utc="2026-11-06T08:00:00")
                key=store.create("No network job")
                with self.assertRaises(TaskRejected):
                    store.transition(key,"completed")
                store.transition(key,"cancelled")
                self.assertEqual(store.count(status="cancelled"),1)
                self.assertEqual(store.mark_due(now="2030-01-01T00:00:00+00:00"),[])


if __name__=="__main__":
    unittest.main()
