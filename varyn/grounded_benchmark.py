"""Independent evidence oracle for a protected public-facts evaluation suite.

The proposing reflector never receives the suite or expected outputs.
The trusted host owns case sources and the runner. Runner calls may be billed
if host chooses a real model: this class makes NO network calls or guarantees.
"""
from __future__ import annotations

from copy import deepcopy
import re

from varyn.grounded_github import (
    GroundingRejected, _facts, validate_grounded_claim)


class BenchmarkRejected(ValueError):
    pass


class GroundedFactBenchmark:
    """Check runner-generated JSON against actual case-specific observations.

    cases: tuple of {"id": opaque_id, "observation": completed-tool-record}
    runner(skill_text, case_id, public_metadata) -> JSON text
    The runner must use a fixed independent provider/configuration, should
    reserve its own actual external usage budget, and must not receive ground
    truth except the public metadata ordinarily available to the task.
    """
    def __init__(self, cases, runner):
        if (type(cases) is not tuple or not 5 <= len(cases) <= 20
                or not callable(runner)):
            raise BenchmarkRejected("Five to twenty host-owned cases required")
        mapping = {}
        for case in cases:
            if (type(case) is not dict or set(case) != {"id", "observation"}
                    or type(case["id"]) is not str or
                    re.fullmatch(r"[a-zA-Z0-9_-]{4,80}", case["id"]) is None
                    or case["id"] in mapping):
                raise BenchmarkRejected("Invalid or duplicate held-out case")
            observation = case["observation"]
            if (type(observation) is not dict
                    or observation.get("status") != "completed"
                    or observation.get("network_dispatched") is not True):
                raise BenchmarkRejected("Case lacks trusted observation")
            try:
                expected = _facts(observation.get("result"))
            except GroundingRejected as exc:
                raise BenchmarkRejected("Invalid held-out observation") from exc
            mapping[case["id"]] = {
                "expected": expected,
                "observation": deepcopy(observation),
            }
        self._cases = mapping
        self._runner = runner
        self._calls = 0

    @property
    def case_ids(self):
        return tuple(self._cases)

    @property
    def calls(self):
        return self._calls

    def evaluate(self, skill_text, case_id):
        if (type(skill_text) is not str or len(skill_text) > 4000
                or type(case_id) is not str or case_id not in self._cases):
            raise BenchmarkRejected("Invalid evaluator invocation")
        row = self._cases[case_id]
        # Runner sees only bounded public data, not private source metadata,
        # evaluation labels, database state or ground-truth verdict.
        fields = deepcopy(row["expected"])
        self._calls += 1
        attempt = self._runner(skill_text, case_id, fields)
        if type(attempt) is not str:
            raise BenchmarkRejected("Trusted benchmark runner must return JSON text")
        try:
            validate_grounded_claim(attempt, row["observation"])
        except GroundingRejected:
            return False
        return True
