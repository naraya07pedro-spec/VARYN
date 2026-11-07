"""Evidence-gated reflection using VARYN LearningKernel.

A trusted host supplies *declassified* short lessons from independently
verified task outcomes, a reflector, and a separate held-out evaluator.
No LLM, network, scheduler, or executable-code permissions are built in.
"""
from hashlib import sha256
import json
import re

from varyn.learning_kernel import LearningKernel, LearningRejected
from varyn.safety import assert_no_obvious_secrets


class ReflectionRejected(ValueError):
    pass


class VerifiedReflectionWorker:
    """Propose -> compare -> promote/reject with source-set deduplication.

    The reflector is allowed to propose text, never to choose its own
    evaluation cases or authorize promotion. Callbacks are trusted host inputs,
    not authentication of their real-world provenance.
    """
    def __init__(self, kernel):
        if not isinstance(kernel, LearningKernel):
            raise TypeError("LearningKernel is required")
        self.kernel = kernel
        self.kernel.db.execute(
            "CREATE TABLE IF NOT EXISTS reflection_attempts("
            "family TEXT NOT NULL, batch_hash TEXT NOT NULL,"
            "status TEXT NOT NULL, candidate_id TEXT,"
            "PRIMARY KEY(family,batch_hash))"
        )

    def learn(self, family, lessons, *, reflector, evaluator, heldout_cases,
              allow_declassified_reflection=False,
              trusted_evaluator=False):
        if (type(family) is not str or
                re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", family) is None or
                type(lessons) is not list or not 2 <= len(lessons) <= 8 or
                not callable(reflector) or not callable(evaluator) or
                type(heldout_cases) is not tuple or
                not 5 <= len(heldout_cases) <= 40 or
                len(set(heldout_cases)) != len(heldout_cases) or
                any(type(c) is not str or not 1 <= len(c) <= 128
                    for c in heldout_cases)):
            raise ReflectionRejected("Invalid bounded reflection inputs")
        if (allow_declassified_reflection is not True
                or trusted_evaluator is not True):
            raise PermissionError(
                "Host declassification and independent evaluation required")

        ids = []
        excerpts = []
        for item in lessons:
            if (type(item) is not dict
                    or set(item) != {"outcome_id", "lesson"}
                    or type(item["outcome_id"]) is not str
                    or re.fullmatch(r"[a-f0-9]{32}",
                                    item["outcome_id"]) is None
                    or type(item["lesson"]) is not str
                    or not 15 <= len(item["lesson"].strip()) <= 500
                    or any(ord(ch) < 32 and ch not in "\n\t"
                           for ch in item["lesson"])):
                raise ReflectionRejected("Invalid declassified lesson")
            assert_no_obvious_secrets(item["lesson"])
            ids.append(item["outcome_id"])
            excerpts.append(item["lesson"].strip())
        if len(ids) != len(set(ids)):
            raise ReflectionRejected("Repeated outcome receipt")
        marks = ",".join("?" for _ in ids)
        verified = self.kernel.db.execute(
            "SELECT COUNT(*) FROM outcomes "
            "WHERE family=? AND succeeded=1 AND id IN (" + marks + ")",
            [family, *ids]).fetchone()[0]
        if verified != len(ids):
            raise ReflectionRejected("Unverified or cross-family outcome")

        batch_hash = sha256(json.dumps(
            sorted(ids), separators=(",", ":")).encode()).hexdigest()
        try:
            self.kernel.db.execute(
                "INSERT INTO reflection_attempts VALUES(?,?,'pending',NULL)",
                (family, batch_hash))
        except Exception as exc:
            # A repeated batch is never sent to a model or re-evaluated.
            from sqlite3 import IntegrityError
            if isinstance(exc, IntegrityError):
                raise ReflectionRejected("Source batch already processed") from None
            raise

        try:
            previous = self.kernel.active_skill(family)
            # Held-out case IDs are deliberately NOT exposed to reflector.
            proposal = reflector({
                "family": family,
                "previous_skill": previous["text"] if previous else "",
                "lessons": tuple(excerpts),
                "untrusted_reference_only": True,
            })
            if type(proposal) is not str:
                raise ReflectionRejected("Reflector must return skill text")
            assert_no_obvious_secrets(proposal)
            candidate_id = self.kernel.propose_skill(family, proposal, ids)
            outcome = self.kernel.evaluate_and_select(
                candidate_id, heldout_cases, evaluator)
        except BaseException:
            self.kernel.db.execute(
                "UPDATE reflection_attempts SET status='needs_review' "
                "WHERE family=? AND batch_hash=?",
                (family, batch_hash))
            raise

        status = "promoted" if outcome["accepted"] else "rejected"
        self.kernel.db.execute(
            "UPDATE reflection_attempts SET status=?,candidate_id=? "
            "WHERE family=? AND batch_hash=?",
            (status, candidate_id, family, batch_hash))
        return {
            "status": status, "candidate_id": candidate_id,
            "family": family,
            "batch_sha256": batch_hash,
            "evaluation": outcome,
            "skills_are_untrusted_references": True,
            "model_weights_modified": False,
            "network_called_by_worker": False,
        }

    def batch_status(self, family, batch_hash):
        row = self.kernel.db.execute(
            "SELECT status,candidate_id FROM reflection_attempts "
            "WHERE family=? AND batch_hash=?",
            (family, batch_hash)).fetchone()
        return None if row is None else {
            "status": row[0], "candidate_id": row[1]}
