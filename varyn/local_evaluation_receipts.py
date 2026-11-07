"""Privacy-bounded local acceptance evidence for manually reviewed evaluations.

No model prompts, response text, API keys, raw public observations, private
paths or receipts supplied by an LLM are stored. A digest documents an
immutable summary AFTER a trusted host finishes the session.

SQLite is local plaintext, not encrypted or authenticated. This is an
audit aid, not independent provider billing proof or a security log signer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_hex
import json
import re

from varyn.learning_kernel import LearningKernel


class ReceiptRejected(ValueError):
    pass


_FORMAT = "varyn.learning_acceptance.v1"
_HEX = re.compile(r"\A[0-9a-f]{32}\Z")
_FINAL = {"completed", "rejected", "declined", "needs_review",
          "already_processed", "budget_exhausted", "skipped"}


class LocalEvaluationReceipts:
    """Metadata-only session journal. Start BEFORE reviewed network actions."""

    def __init__(self, kernel):
        if not isinstance(kernel, LearningKernel):
            raise TypeError("LearningKernel required")
        self.kernel = kernel
        kernel.db.execute("""
            CREATE TABLE IF NOT EXISTS live_evaluation_receipts(
                id TEXT PRIMARY KEY,
                started_utc TEXT NOT NULL,
                finished_utc TEXT,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_sha256 TEXT NOT NULL,
                estimated_micro_usd INTEGER NOT NULL,
                public_reads INTEGER NOT NULL,
                model_requests_attempted INTEGER NOT NULL,
                model_responses_succeeded INTEGER NOT NULL,
                model_requests_failed_or_uncertain INTEGER NOT NULL,
                reported_input_tokens INTEGER NOT NULL,
                reported_output_tokens INTEGER NOT NULL,
                responses_with_incomplete_usage INTEGER NOT NULL,
                evaluated_cases INTEGER,
                baseline_passes INTEGER,
                candidate_passes INTEGER,
                regressions INTEGER,
                case_observations_sha256 TEXT,
                evidence_sha256 TEXT,
                actual_provider_cost_known INTEGER NOT NULL DEFAULT 0
            )
        """)

    def begin(self, *, provider, model, estimated_micro_usd,
              explicit_session_approval=False):
        if explicit_session_approval is not True:
            raise PermissionError("Owner review required before journaling live run")
        if (provider not in ("openrouter", "deepseek")
                or type(model) is not str or not 1 <= len(model) <= 200
                or type(estimated_micro_usd) is not int
                or not 0 <= estimated_micro_usd <= 100000):
            raise ReceiptRejected("Invalid reviewed session metadata")
        ident = token_hex(16)
        now = datetime.now(timezone.utc).isoformat()
        self.kernel.db.execute(
            "INSERT INTO live_evaluation_receipts"
            "(id,started_utc,status,provider,model_sha256,"
            "estimated_micro_usd,public_reads,model_requests_attempted,"
            "model_responses_succeeded,model_requests_failed_or_uncertain,"
            "reported_input_tokens,reported_output_tokens,"
            "responses_with_incomplete_usage,actual_provider_cost_known)"
            "VALUES(?,?,'running',?,?,?,0,0,0,0,0,0,0,0)",
            (ident, now, provider, sha256(model.encode()).hexdigest(),
             estimated_micro_usd))
        return ident

    @staticmethod
    def _counts(before, after):
        keys = (
            "requests_reserved", "requests_succeeded",
            "requests_failed_or_uncertain", "reported_input_tokens",
            "reported_output_tokens", "responses_with_incomplete_usage")
        if (type(before) is not dict or type(after) is not dict):
            raise ReceiptRejected("Usage snapshots required")
        diff = {}
        for key in keys:
            a, b = before.get(key), after.get(key)
            if type(a) is not int or type(b) is not int or b < a:
                raise ReceiptRejected("Usage snapshot counter invalid")
            diff[key] = b - a
        if (diff["requests_succeeded"]
                + diff["requests_failed_or_uncertain"]
                > diff["requests_reserved"]
                or diff["requests_reserved"] > 10):
            raise ReceiptRejected("Out of bounds per-session attempted model calls")
        return diff

    def finish(self, ident, *, status, before, after, public_reads,
               evaluated_cases=None, baseline_passes=None,
               candidate_passes=None, regressions=None,
               case_observations_sha256=None):
        if (type(ident) is not str or _HEX.fullmatch(ident) is None
                or status not in _FINAL
                or type(public_reads) is not int
                or not 0 <= public_reads <= 5):
            raise ReceiptRejected("Invalid finished evaluation metadata")
        numbers = (evaluated_cases, baseline_passes,
                   candidate_passes, regressions)
        if all(x is None for x in numbers):
            if status == "completed" or status == "rejected":
                raise ReceiptRejected("Terminal quality result missing")
        elif (any(type(x) is not int for x in numbers)
              or not 5 <= evaluated_cases <= 20
              or not 0 <= baseline_passes <= evaluated_cases
              or not 0 <= candidate_passes <= evaluated_cases
              or not 0 <= regressions <= baseline_passes
              or status not in ("completed", "rejected")):
            raise ReceiptRejected("Invalid quality matrix")
        if (case_observations_sha256 is not None and
                (type(case_observations_sha256) is not str
                 or re.fullmatch(r"[0-9a-f]{64}",
                                 case_observations_sha256) is None)):
            raise ReceiptRejected("Invalid case fingerprint")
        diff = self._counts(before, after)
        if (status in ("completed", "rejected")
                and (public_reads != 5 or diff["requests_reserved"] != 10
                     or evaluated_cases != 5
                     or not case_observations_sha256)):
            raise ReceiptRejected("Incomplete benchmark cannot be reported")
        if (status == "completed"
                and not (candidate_passes > baseline_passes
                         and regressions == 0)):
            raise ReceiptRejected("Promotion quality gate not met")
        if (status == "rejected" and candidate_passes > baseline_passes
                and regressions == 0):
            raise ReceiptRejected("Reported rejection contradicts score")

        row = self.kernel.db.execute(
            "SELECT started_utc,provider,model_sha256,estimated_micro_usd "
            "FROM live_evaluation_receipts WHERE id=? AND status='running'",
            (ident,)).fetchone()
        if row is None:
            raise ReceiptRejected("Unknown or already finalized session")
        finished = datetime.now(timezone.utc).isoformat()
        record = {
            "format": _FORMAT, "id": ident, "started_utc": row[0],
            "finished_utc": finished, "status": status,
            "provider": row[1], "model_sha256": row[2],
            "estimated_micro_usd": row[3],
            "public_reads": public_reads,
            "model_requests_attempted": diff["requests_reserved"],
            "model_responses_succeeded": diff["requests_succeeded"],
            "model_requests_failed_or_uncertain":
                diff["requests_failed_or_uncertain"],
            "reported_input_tokens": diff["reported_input_tokens"],
            "reported_output_tokens": diff["reported_output_tokens"],
            "responses_with_incomplete_usage":
                diff["responses_with_incomplete_usage"],
            "evaluated_cases": evaluated_cases,
            "baseline_passes": baseline_passes,
            "candidate_passes": candidate_passes,
            "regressions": regressions,
            "case_observations_sha256": case_observations_sha256,
            "actual_provider_cost_known": False,
        }
        digest = sha256(json.dumps(
            record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        cur = self.kernel.db.execute(
            "UPDATE live_evaluation_receipts SET "
            "finished_utc=?,status=?,public_reads=?,"
            "model_requests_attempted=?,model_responses_succeeded=?,"
            "model_requests_failed_or_uncertain=?,reported_input_tokens=?,"
            "reported_output_tokens=?,responses_with_incomplete_usage=?,"
            "evaluated_cases=?,baseline_passes=?,candidate_passes=?,"
            "regressions=?,case_observations_sha256=?,evidence_sha256=? "
            "WHERE id=? AND status='running'",
            (finished, status, public_reads,
             diff["requests_reserved"], diff["requests_succeeded"],
             diff["requests_failed_or_uncertain"],
             diff["reported_input_tokens"], diff["reported_output_tokens"],
             diff["responses_with_incomplete_usage"],
             evaluated_cases, baseline_passes, candidate_passes,
             regressions, case_observations_sha256, digest, ident))
        if cur.rowcount != 1:
            raise ReceiptRejected("Concurrent session transition")
        return self.get(ident)

    def get(self, ident):
        if type(ident) is not str or _HEX.fullmatch(ident) is None:
            raise ReceiptRejected("Invalid session ID")
        row = self.kernel.db.execute(
            "SELECT * FROM live_evaluation_receipts WHERE id=?",
            (ident,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["format"] = _FORMAT
        record["actual_provider_cost_known"] = False
        record["provider_billing_ceiling_enforced"] = False
        record["usage_counters_are_session_local"] = True
        record["storage_is_encrypted"] = False
        record["quality_verified_against_public_tool_only"] = True
        if record["status"] == "running":
            record["status"] = "running_or_interrupted"
        return record

    def latest(self):
        row = self.kernel.db.execute(
            "SELECT id FROM live_evaluation_receipts "
            "ORDER BY started_utc DESC,id DESC LIMIT 1").fetchone()
        return None if row is None else self.get(row[0])
