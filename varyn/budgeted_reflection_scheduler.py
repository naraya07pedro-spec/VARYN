"""Opt-in, local, resource-bounded reflection scheduler for public facts.

One synchronous tick only. No daemon, model/network calls, timers, credentials,
automatic retries, arbitrary code execution, or provider billing guarantees.
The host owns the schedule trigger, independent benchmark and optional runner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

from varyn.grounded_benchmark import GroundedFactBenchmark
from varyn.learning_kernel import LearningKernel
from varyn.verified_failure_feedback import VerifiedFailureLedger
from varyn.verified_reflection import VerifiedReflectionWorker


class ScheduleRejected(ValueError):
    pass


_DEFAULT_SKILL = (
    "For public GitHub repository facts, first use the authorized read-only "
    "metadata tool. When constructing the final JSON, copy all five observed "
    "fields exactly, preserve each integer and boolean type, reject unknown "
    "fields and never substitute invented numbers or branch names."
)


def conservative_public_fact_reflector(context):
    """A fixed, local skill candidate, NOT an LLM or proof of improvement."""
    if (type(context) is not dict
            or context.get("family") != "github_public_facts"):
        raise ScheduleRejected("Invalid reflection context")
    return _DEFAULT_SKILL


class BudgetedReflectionScheduler:
    """Persistent per-day reservation and crash-safe no-replay semantics.

    The 'trust' flags are host assertions, NOT identity authentication. Never
    expose tick as a model-callable tool or a public HTTP endpoint. Even if
    the evaluation runner calls a model, this scheduler cannot bound provider
    billing; the runner MUST implement its own external request budget.
    """
    def __init__(self, kernel, ledger):
        if (not isinstance(kernel, LearningKernel)
                or not isinstance(ledger, VerifiedFailureLedger)
                or ledger.kernel is not kernel):
            raise TypeError("LearningKernel and matching feedback ledger required")
        self.kernel = kernel
        self.ledger = ledger
        self.kernel.db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_reflection_runs(
                id TEXT PRIMARY KEY,
                source_hash TEXT NOT NULL UNIQUE,
                day TEXT NOT NULL,
                started_utc TEXT NOT NULL,
                reserved_evaluator_calls INTEGER NOT NULL,
                status TEXT NOT NULL,
                candidate_id TEXT
            )
        """)

    def history(self, limit=10):
        if type(limit) is not int or not 1 <= limit <= 40:
            raise ScheduleRejected("Invalid history limit")
        return [
            {"day": row[0], "status": row[1],
             "reserved_evaluator_calls": row[2]}
            for row in self.kernel.db.execute(
                "SELECT day,status,reserved_evaluator_calls "
                "FROM scheduled_reflection_runs "
                "ORDER BY started_utc DESC,id DESC LIMIT ?", (limit,))
        ]

    def preflight(self, *, case_count=5,
                  max_cycles_per_utc_day=1,
                  max_evaluator_calls_per_utc_day=10, now=None):
        """Non-reserving readiness check before gathering live test data.

        This avoids fetching five GitHub cases when a crash/previous run
        has already consumed the exact evidence batch or daily quota.
        Still not a concurrency reservation: tick rechecks transactionally.
        """
        if (type(case_count) is not int or not 5 <= case_count <= 20
                or type(max_cycles_per_utc_day) is not int
                or not 1 <= max_cycles_per_utc_day <= 3
                or type(max_evaluator_calls_per_utc_day) is not int
                or not 10 <= max_evaluator_calls_per_utc_day <= 80):
            raise ScheduleRejected("Invalid evaluation preflight limits")
        current = datetime.now(timezone.utc) if now is None else now
        if (not isinstance(current, datetime) or current.tzinfo is None
                or current.utcoffset() is None):
            raise ScheduleRejected("UTC-aware clock required")
        day = current.astimezone(timezone.utc).date().isoformat()
        required = case_count * 2
        if required > max_evaluator_calls_per_utc_day:
            return {"status": "budget_exhausted", "reserved_calls": 0}
        failures = self.ledger.recent_fingerprints()
        if not failures:
            return {"status": "no_verified_failure", "reserved_calls": 0}
        sources = [
            row[0] for row in self.kernel.db.execute(
                "SELECT id FROM outcomes "
                "WHERE family='github_public_facts' AND succeeded=1 "
                "ORDER BY created_at DESC,id DESC LIMIT 4")]
        if len(sources) < 2:
            return {"status": "not_enough_success_evidence",
                    "reserved_calls": 0}
        fingerprint = sha256(json.dumps({
            "sources": sorted(sources), "failures": sorted(failures)
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        consumed = self.kernel.db.execute(
            "SELECT 1 FROM scheduled_reflection_runs WHERE source_hash=?",
            (fingerprint,)).fetchone()
        if consumed:
            return {"status": "already_processed", "reserved_calls": 0}
        count, used = self.kernel.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(reserved_evaluator_calls),0) "
            "FROM scheduled_reflection_runs WHERE day=?", (day,)).fetchone()
        if (count >= max_cycles_per_utc_day
                or used + required > max_evaluator_calls_per_utc_day):
            return {"status": "budget_exhausted", "reserved_calls": 0}
        return {"status": "ready", "reserved_calls": required}

    def tick(self, *, enabled=False, trusted_evaluator=False,
             allow_declassified_reflection=False, benchmark=None,
             reflector=None, max_cycles_per_utc_day=1,
             max_evaluator_calls_per_utc_day=20, now=None):
        if enabled is not True:
            # No DB mutations or callback calls while disabled.
            return {"status": "disabled", "evaluator_calls": 0}
        if (trusted_evaluator is not True or
                allow_declassified_reflection is not True):
            raise PermissionError("Explicit trusted host review is required")
        if (not isinstance(benchmark, GroundedFactBenchmark)
                or not callable(reflector)
                or type(max_cycles_per_utc_day) is not int
                or not 1 <= max_cycles_per_utc_day <= 3
                or type(max_evaluator_calls_per_utc_day) is not int
                or not 10 <= max_evaluator_calls_per_utc_day <= 80):
            raise ScheduleRejected("Invalid trusted bounded learning setup")
        current = datetime.now(timezone.utc) if now is None else now
        if (not isinstance(current, datetime)
                or current.tzinfo is None
                or current.utcoffset() is None):
            raise ScheduleRejected("Timezone-aware UTC clock required")
        current = current.astimezone(timezone.utc)
        day = current.date().isoformat()
        case_ids = benchmark.case_ids
        required_calls = len(case_ids) * 2
        if required_calls > max_evaluator_calls_per_utc_day:
            return {"status": "budget_exhausted", "evaluator_calls": 0}
        failures = self.ledger.recent_fingerprints()
        if not failures:
            return {"status": "no_verified_failure", "evaluator_calls": 0}
        sources = [
            row[0] for row in self.kernel.db.execute(
                "SELECT id FROM outcomes "
                "WHERE family='github_public_facts' AND succeeded=1 "
                "ORDER BY created_at DESC,id DESC LIMIT 4")]
        if len(sources) < 2:
            return {"status": "not_enough_success_evidence",
                    "evaluator_calls": 0}
        # Every source and failure is a host-recorded digest. No prompts,
        # extracted private conversations, or provider output are involved.
        fingerprint = sha256(json.dumps({
            "sources": sorted(sources), "failures": sorted(failures)
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        run_id = sha256((day + ":" + fingerprint).encode()).hexdigest()

        self.kernel.db.execute("BEGIN IMMEDIATE")
        try:
            previous = self.kernel.db.execute(
                "SELECT status FROM scheduled_reflection_runs "
                "WHERE source_hash=?", (fingerprint,)).fetchone()
            if previous is not None:
                self.kernel.db.execute("COMMIT")
                return {"status": "already_processed", "evaluator_calls": 0}
            row = self.kernel.db.execute(
                "SELECT COUNT(*),COALESCE(SUM(reserved_evaluator_calls),0) "
                "FROM scheduled_reflection_runs WHERE day=?", (day,)
            ).fetchone()
            if (row[0] >= max_cycles_per_utc_day or
                    row[1] + required_calls > max_evaluator_calls_per_utc_day):
                self.kernel.db.execute("COMMIT")
                return {"status": "budget_exhausted", "evaluator_calls": 0}
            # Reserve the entire comparison BEFORE any model callback.
            self.kernel.db.execute(
                "INSERT INTO scheduled_reflection_runs "
                "(id,source_hash,day,started_utc,"
                "reserved_evaluator_calls,status,candidate_id)"
                " VALUES(?,?,?,?,?,'running',NULL)",
                (run_id, fingerprint, day, current.isoformat(),
                 required_calls))
            self.kernel.db.execute("COMMIT")
        except BaseException:
            self.kernel.db.execute("ROLLBACK")
            raise

        note = (
            "A prior independently checked public GitHub fact read preserved "
            "repository, branch, stars, open item count and archived flag. "
            "A separate incorrect claim was caught by deterministic comparison."
        )
        lessons = [
            {"outcome_id": source_id, "lesson": note}
            for source_id in sources
        ]
        try:
            result = VerifiedReflectionWorker(self.kernel).learn(
                "github_public_facts", lessons,
                reflector=reflector,
                evaluator=benchmark.evaluate,
                heldout_cases=case_ids,
                allow_declassified_reflection=True,
                trusted_evaluator=True)
        except BaseException:
            self.kernel.db.execute(
                "UPDATE scheduled_reflection_runs SET status='needs_review' "
                "WHERE id=? AND status='running'", (run_id,))
            raise
        self.kernel.db.execute(
            "UPDATE scheduled_reflection_runs "
            "SET status=?,candidate_id=? WHERE id=? AND status='running'",
            (result["status"], result["candidate_id"], run_id))
        return {
            "status": result["status"],
            "evaluator_calls": benchmark.calls,
            "reserved_evaluator_calls": required_calls,
            "regressions": result["evaluation"]["regressions"],
            "model_weights_modified": False,
            "external_billing_cap_enforced": False,
        }
