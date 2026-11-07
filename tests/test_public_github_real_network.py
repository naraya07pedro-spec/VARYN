"""ONE real anonymous GitHub REST GET in GitHub-hosted CI.

No model/API key, private repository, owner account, write permission or
generalized model evaluation is exercised. This is an external-network
acceptance of VARYN's *actual* fixed-host public metadata read path.
"""
from hashlib import sha256
import json
import unittest

from varyn.public_github_tool import PublicGithubToolGateway


class RealAnonymousPublicGithubAcceptance(unittest.TestCase):
    def test_genuine_public_read_from_fixed_host(self):
        gateway = PublicGithubToolGateway(max_requests=1)
        try:
            intent = json.dumps({
                "format": "varyn.public_tool_intent.v1",
                "tool": "github_public_repo_metadata",
                "arguments": {"repository": "python/cpython"},
            })
            proposal = gateway.propose(intent, network_consent=True)
            # CI's explicitly scoped approval is NOT owner-device consent;
            # it authorizes only this one harmless public GitHub GET.
            reply = gateway.decide(
                proposal.proposal_id, proposal.digest,
                approved=True, network_consent=True)
            self.assertEqual(reply["status"], "completed")
            self.assertTrue(reply["network_dispatched"])
            fields = reply["result"]
            self.assertEqual(fields["repository"], "python/cpython")
            self.assertTrue(fields["public"])
            self.assertTrue(fields["read_only"])
            self.assertIs(type(fields["archived"]), bool)
            self.assertIs(type(fields["stars"]), int)
            self.assertIs(type(fields["open_items_including_prs"]), int)
            self.assertEqual(gateway.status()["used"], 1)
            self.assertEqual(gateway.status()["in_flight"], 0)
            canonical = json.dumps({
                key: fields[key] for key in (
                    "repository", "default_branch", "stars",
                    "open_items_including_prs", "archived")
            }, sort_keys=True, separators=(",", ":"))
            print("LIVE_PUBLIC_GITHUB_READ_OK=1")
            print("LIVE_PUBLIC_GITHUB_SOURCE=github_anonymous_fixed_host")
            print("LIVE_PUBLIC_GITHUB_FACT_SHA256=" +
                  sha256(canonical.encode()).hexdigest())
            print("LIVE_REAL_MODEL_PROVIDER_CALLED=0")
        finally:
            gateway.close()


if __name__ == "__main__":
    unittest.main()
