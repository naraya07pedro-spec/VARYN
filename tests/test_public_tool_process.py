"""17S-4 public GitHub child-process transport, no live network.

Actual OS process smoke uses --offline-self-test; all GET paths use fake Popen.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from threading import Event
from unittest.mock import patch

from varyn.public_tool_process import ProcessRepoFetcher
from varyn.public_github_tool import PublicGithubToolGateway, PublicToolRejected
from varyn.public_tool_worker import PublicGithubToolWorker


REPO = "naraya07pedro-spec/VARYN"


def metadata(repository=REPO):
    return {"format": "varyn.github_public_repo_metadata.v1",
            "repository": repository, "default_branch": "main",
            "stars": 1, "open_items_including_prs": 0, "archived": False,
            "public": True, "read_only": True,
            "untrusted_external_data": True, "provider_handoff": False}


def intent():
    return json.dumps({"format": "varyn.public_tool_intent.v1",
                       "tool": "github_public_repo_metadata",
                       "arguments": {"repository": REPO}})


def until(fn, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(0.01)
    return fn()


class FakeProcess:
    def __init__(self, *, block=False, body=None, returncode=0):
        self.started = Event()
        self.released = Event()
        if not block:
            self.released.set()
        self.done = False
        self.killed = False
        self.returncode = returncode
        self.payload = None
        self.body = body if body is not None else json.dumps(metadata()).encode()

    def communicate(self, *, input, timeout):
        self.payload = input
        self.started.set()
        if not self.released.wait(timeout):
            raise subprocess.TimeoutExpired("test-child", timeout)
        self.done = True
        return self.body, b""

    def poll(self):
        return self.returncode if self.done else None

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.released.set()


class ProcessBoundaryTests(unittest.TestCase):
    def test_actual_child_launch_offline_isolated_no_site(self):
        command = ProcessRepoFetcher._command()
        self.assertEqual(command[1:3], ["-I", "-S"])
        self.assertTrue(Path(command[3]).is_file())
        complete = subprocess.run(
            command + ["--offline-self-test"], input=b"", capture_output=True,
            env=ProcessRepoFetcher._environment(), shell=False,
            close_fds=True, timeout=8,
        )
        self.assertEqual(complete.returncode, 0, complete.stderr[:200])
        result = json.loads(complete.stdout.decode())
        self.assertEqual(result["format"], "varyn.public_tool_child.self_test.v1")
        self.assertTrue(result["isolated_mode"])
        self.assertTrue(result["no_site"])
        self.assertFalse(result["network_used"])

    def test_spawn_has_fixed_entry_no_shell_no_proxy_env_or_tokens(self):
        record = {}
        proc = FakeProcess()
        def spawn(*args, **kwargs):
            record["args"] = args
            record["kwargs"] = kwargs
            return proc

        fetch = ProcessRepoFetcher(spawn=spawn)
        with patch.dict(os.environ, {
            "GITHUB_TOKEN": "SHOULD_NEVER_PASS",
            "OPENAI_API_KEY": "NOPE",
            "HTTPS_PROXY": "https://evil-proxy",
            "PYTHONPATH": "/evil/import",
        }):
            result = fetch(REPO)
        self.assertEqual(result["repository"], REPO)
        args = record["args"][0]
        self.assertEqual(args[1:3], ["-I", "-S"])
        self.assertEqual(args[3], str(Path(__file__).resolve().parent.parent /
                                     "varyn" / "public_tool_child.py"))
        kwargs = record["kwargs"]
        self.assertIs(kwargs["shell"], False)
        self.assertIs(kwargs["close_fds"], True)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertNotIn("HTTPS_PROXY", kwargs["env"])
        self.assertNotIn("PYTHONPATH", kwargs["env"])
        self.assertNotIn("GITHUB_TOKEN", kwargs["env"])
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
        self.assertEqual(json.loads(proc.payload)["arguments"]["repository"], REPO)
        self.assertNotIn("SHOULD_NEVER_PASS", proc.payload.decode())

    def test_process_revocation_kills_child_and_drops_response(self):
        proc = FakeProcess(block=True)
        fetch = ProcessRepoFetcher(spawn=lambda *a, **k: proc)
        gate = PublicGithubToolGateway(fetcher=fetch)
        worker = PublicGithubToolWorker(gate)
        try:
            review = gate.propose(intent(), network_consent=True)
            worker.submit(review, network_consent=True)
            self.assertTrue(proc.started.wait(2))
            self.assertTrue(worker.busy)
            begin = time.monotonic()
            worker.revoke()
            self.assertLess(time.monotonic() - begin, 1)
            self.assertTrue(proc.killed)
            self.assertTrue(until(lambda: not worker.busy))
            self.assertIsNone(worker.poll())
            self.assertEqual(gate.status()["used"], 1)
        finally:
            proc.released.set()
            worker.close()

    def test_close_terminates_child_and_blocks_future_calls(self):
        proc = FakeProcess(block=True)
        fetch = ProcessRepoFetcher(spawn=lambda *a, **k: proc)
        gate = PublicGithubToolGateway(fetcher=fetch)
        worker = PublicGithubToolWorker(gate)
        try:
            review = gate.propose(intent(), network_consent=True)
            worker.submit(review, network_consent=True)
            self.assertTrue(proc.started.wait(2))
            worker.close()
            self.assertTrue(proc.killed)
            self.assertTrue(fetch.status()["closed"])
            self.assertTrue(until(lambda: not worker.busy))
            self.assertIsNone(worker.poll())
            with self.assertRaises(PublicToolRejected):
                fetch(REPO)
        finally:
            proc.released.set()

    def test_child_timeout_blocks_no_retry_and_reaps(self):
        proc = FakeProcess(block=True)
        def timeout_now(*, input, timeout):
            raise subprocess.TimeoutExpired("test-child", timeout)
        proc.communicate = timeout_now
        fetch = ProcessRepoFetcher(spawn=lambda *a, **k: proc, timeout_seconds=1)
        with self.assertRaises(PublicToolRejected):
            fetch(REPO)
        self.assertTrue(proc.killed)
        self.assertEqual(fetch.status()["attempts"], 1)

    def test_invalid_child_output_is_rejected(self):
        for body in (b"{}", b"not-json", b"a" * 4097,
                     json.dumps({**metadata(), "repository": "evil/repo"}).encode()):
            proc = FakeProcess(body=body)
            fetch = ProcessRepoFetcher(spawn=lambda *a, **k: proc)
            with self.subTest(body=body[:30]), self.assertRaises(PublicToolRejected):
                fetch(REPO)

    def test_cannot_spawn_concurrent_child_calls(self):
        proc = FakeProcess(block=True)
        fetch = ProcessRepoFetcher(spawn=lambda *a, **k: proc)
        from threading import Thread
        failures = []
        t = Thread(target=lambda: failures.append(
            self._run_fetch_catching(fetch)), daemon=True)
        t.start()
        try:
            self.assertTrue(proc.started.wait(2))
            with self.assertRaises(PublicToolRejected):
                fetch(REPO)
        finally:
            fetch.cancel()
            proc.released.set()
            t.join(timeout=2)
        self.assertEqual(len(failures), 1)

    @staticmethod
    def _run_fetch_catching(fetch):
        try:
            return fetch(REPO)
        except PublicToolRejected:
            return None

    def test_rejected_repository_never_spawns(self):
        fetch = ProcessRepoFetcher(spawn=lambda *a, **k:
                                  (_ for _ in ()).throw(AssertionError("spawn")))
        for bad in ("https://localhost/x", "a/../../etc", "file:///secret", ""):
            with self.subTest(bad=bad), self.assertRaises(PublicToolRejected):
                fetch(bad)


if __name__ == "__main__":
    unittest.main()
