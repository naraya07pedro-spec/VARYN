"""Local metadata-only failure feedback from independently checked public facts.

No model inference, prompt storage, user notes, credentials, or retries.
This is a trusted-host component, not a public API or identity boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import sqlite3

from varyn.grounded_github import GroundingRejected, _facts
from varyn.learning_kernel import LearningKernel


class FeedbackRejected(ValueError):
    pass


_CATEGORIES = {
    "Model fact does not match observation": "fact_mismatch",
    "Model fact field type mismatch": "type_mismatch",
    "Model must return exact fact schema": "schema_mismatch",
    "Model did not provide valid JSON facts": "invalid_json",
    "Duplicate JSON key": "duplicate_json_key",
    "Bounded JSON fact claim required": "invalid_json",
}
_HEX32 = re.compile(r"\A[0-9a-f]{32}\Z")


class VerifiedFailureLedger:
    """One non-sensitive failure record per actual agent run.

    A GroundingRejected produced by the host's deterministic verifier is
    required. External model text cannot authorize a failure or write.
    """
    def __init__(self, kernel):
        if not isinstance(kernel, LearningKernel):
            raise TypeError("Expected trusted LearningKernel")
        self.kernel = kernel
        self.kernel.db.execute("""
            CREATE TABLE IF NOT EXISTS grounded_failure_feedback(
                run_hash TEXT PRIMARY KEY,
                evidence_hash TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

    def record(self, run_id, error, observation, *,
               owner_opted_in=False):
        if owner_opted_in is not True:
            raise PermissionError("Failure feedback storage is disabled")
        if (type(run_id) is not str or _HEX32.fullmatch(run_id) is None
                or not isinstance(error, GroundingRejected)
                or type(observation) is not dict
                or observation.get("status") != "completed"
                or observation.get("network_dispatched") is not True):
            raise FeedbackRejected("Verified run and tool observation required")
        facts = _facts(observation.get("result"))
        reason = _CATEGORIES.get(str(error), "other_validation_failure")
        canonical = json.dumps(
            facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        evidence_hash = sha256(canonical.encode("utf-8")).hexdigest()
        run_hash = sha256(run_id.encode("ascii")).hexdigest()
        try:
            self.kernel.db.execute(
                "INSERT INTO grounded_failure_feedback"
                "(run_hash,evidence_hash,category,created_at) VALUES(?,?,?,?)",
                (run_hash, evidence_hash, reason,
                 datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError:
            return {"status": "duplicate", "category": reason}
        return {"status": "recorded", "category": reason}

    def summary(self):
        data = self.kernel.db.execute(
            "SELECT category,COUNT(*) FROM grounded_failure_feedback "
            "GROUP BY category ORDER BY category").fetchall()
        return {
            "family": "github_public_facts",
            "total_failed_fact_checks": sum(n for _, n in data),
            "categories": {kind: count for kind, count in data},
            "stored_raw_model_text": False,
            "stored_prompt_text": False,
            "automatically_promotes_skills": False,
        }

    def recent_fingerprints(self, limit=8):
        if type(limit) is not int or not 1 <= limit <= 32:
            raise FeedbackRejected("Invalid failure window")
        return [
            row[0] for row in self.kernel.db.execute(
                "SELECT run_hash FROM grounded_failure_feedback "
                "ORDER BY created_at DESC, run_hash DESC LIMIT ?", (limit,))
        ]
