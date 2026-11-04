"""17Q: reproducible offline evaluation of baseline vs collaboration output.

Checks whether specified *literal facts/constraints* appear, NOT truth,
creativity, originality or real-world usefulness. No LLM, network, external
judge, hidden prompts or access to user data. A metric cannot prove its rubric.
"""
from dataclasses import dataclass
import json
import re

_TERM = re.compile(r"^[\w][\w .+/-]{0,79}$", re.UNICODE)
_MAX_RESPONSE_CHARS = 20000


class EvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    required: tuple
    forbidden: tuple
    alternatives: tuple = ()

    def __post_init__(self):
        if type(self.case_id) is not str or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,39}", self.case_id
        ):
            raise EvaluationError("Invalid case ID")
        for name in ("required", "forbidden", "alternatives"):
            values = getattr(self, name)
            if (type(values) is not tuple or len(values) > 12 or
                any(type(v) is not str or not _TERM.fullmatch(v)
                    for v in values) or len(set(v.casefold() for v in values)) != len(values)):
                raise EvaluationError("Invalid bounded rubric terms")
        if not self.required:
            raise EvaluationError("At least one required criterion")
        terms = list(self.required) + list(self.forbidden) + list(self.alternatives)
        if len(set(t.casefold() for t in terms)) != len(terms):
            raise EvaluationError("Rubric terms must be globally distinct")


def parse_rubric(raw):
    """Parse owner-authored bounded criteria. Never ask the model to grade itself."""
    if type(raw) is not str or not 1 <= len(raw) <= 2400:
        raise EvaluationError("Rubric JSON must be 1..2400 characters")
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        raise EvaluationError("Invalid rubric JSON") from None
    if type(doc) is not dict or set(doc) != {
        "case_id", "required", "forbidden", "alternatives"
    }:
        raise EvaluationError("Rubric needs exactly four named fields")
    for name in ("required", "forbidden", "alternatives"):
        if type(doc[name]) is not list:
            raise EvaluationError("Rubric criteria must be lists")
    return EvaluationCase(
        doc["case_id"], tuple(doc["required"]),
        tuple(doc["forbidden"]), tuple(doc["alternatives"]),
    )


def _found(text, phrase):
    """Case-insensitive, literal boundary-aware matching; not semantic entailment."""
    return re.search(
        r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)",
        text.casefold(),
    ) is not None


def evaluate_text(case, text):
    if type(case) is not EvaluationCase:
        raise EvaluationError("EvaluationCase required")
    if type(text) is not str or not 1 <= len(text.strip()) <= _MAX_RESPONSE_CHARS:
        raise EvaluationError("Response must be 1..20000 characters")
    required_hit = [x for x in case.required if _found(text, x)]
    forbidden_hit = [x for x in case.forbidden if _found(text, x)]
    alternatives_hit = [x for x in case.alternatives if _found(text, x)]
    return {
        "required_matched": len(required_hit),
        "required_total": len(case.required),
        "required_coverage": round(len(required_hit) / len(case.required), 4),
        "forbidden_mentions": len(forbidden_hit),
        "alternatives_mentioned": len(alternatives_hit),
        "alternatives_total": len(case.alternatives),
        "passed_literal_checks": (
            len(required_hit) == len(case.required) and not forbidden_hit
        ),
        "matched_required_terms": required_hit,
        "mentioned_forbidden_terms": forbidden_hit,
        "mentioned_alternative_terms": alternatives_hit,
        "semantic_entailment_verified": False,
        "factual_truth_verified": False,
        "human_creativity_judged": False,
    }


def compare_outputs(case, baseline, collaborative):
    """Compare supplied texts on the SAME declared rubric; never auto-impute quality."""
    first = evaluate_text(case, baseline)
    second = evaluate_text(case, collaborative)
    return {
        "format": "varyn.reasoning_eval.v1",
        "case_id": case.case_id,
        "baseline": first,
        "collaboration": second,
        "delta_required_coverage": round(
            second["required_coverage"] - first["required_coverage"], 4
        ),
        "delta_forbidden_mentions": (
            second["forbidden_mentions"] - first["forbidden_mentions"]
        ),
        "delta_alternatives_mentioned": (
            second["alternatives_mentioned"] - first["alternatives_mentioned"]
        ),
        "quality_winner": None,
        "improvement_proven": False,
        "controlled_baseline": False,
        "rubric_type": "literal_coverage_not_semantic_quality",
        "fake_outputs_prove_model_performance": False,
    }


def compare_collaboration_report(case, report):
    """Within one run analyst-vs-synthesizer diagnostic, NOT a controlled A/B."""
    if type(report) is not dict or report.get("format") != "varyn.collaboration.v1":
        raise EvaluationError("Expected collaboration result")
    stages = report.get("stages")
    if (type(stages) is not list or len(stages) != 3 or
        any(type(s) is not dict for s in stages) or
        [s.get("role") for s in stages] !=
        ["analyst", "critic", "synthesizer"] or
        type(report.get("final_answer")) is not str or
        report["final_answer"] != stages[-1].get("text")):
        raise EvaluationError("Incomplete or inconsistent collaboration report")
    result = compare_outputs(case, stages[0].get("text"),
                             report["final_answer"])
    result["baseline_type"] = "analyst_stage_in_same_run"
    result["controlled_baseline"] = False
    result["multi_model_review"] = report.get("multi_model_review") is True
    result["live_execution_independently_attested"] = False
    return result


def evaluate_fixture_suite(fixtures):
    """Run immutable synthetic triples; show regressions as well as improvements."""
    if type(fixtures) not in (list, tuple) or not 1 <= len(fixtures) <= 50:
        raise EvaluationError("Suite must contain 1..50 fixtures")
    cases = []
    seen = set()
    for item in fixtures:
        if type(item) is not dict or set(item) != {
            "case_id", "required", "forbidden", "alternatives",
            "baseline", "collaboration"
        }:
            raise EvaluationError("Invalid fixture schema")
        case = EvaluationCase(
            item["case_id"], tuple(item["required"]),
            tuple(item["forbidden"]), tuple(item["alternatives"]),
        )
        if case.case_id in seen:
            raise EvaluationError("Duplicate case ID")
        seen.add(case.case_id)
        cases.append(compare_outputs(case, item["baseline"],
                                     item["collaboration"]))
    return {
        "format": "varyn.reasoning_eval_suite.v1",
        "cases": cases,
        "sample_count": len(cases),
        "literal_coverage_better": sum(
            x["delta_required_coverage"] > 0 for x in cases
        ),
        "literal_coverage_worse": sum(
            x["delta_required_coverage"] < 0 for x in cases
        ),
        "literal_coverage_equal": sum(
            x["delta_required_coverage"] == 0 for x in cases
        ),
        "model_superiority_demonstrated": False,
        "human_validated": False,
        "api_calls": 0,
    }


def synthetic_fixtures():
    """Invented examples deliberately include a collaboration regression."""
    return [
        {
            "case_id": "synthetic_design_improves",
            "required": ["offline", "consent", "recovery"],
            "forbidden": ["unrestricted"],
            "alternatives": ["sqlite", "json"],
            "baseline": "Keep this offline.",
            "collaboration": "Offline design: consent, recovery, sqlite or json.",
        },
        {
            "case_id": "synthetic_design_regresses",
            "required": ["backup", "audit"],
            "forbidden": ["delete everything"],
            "alternatives": ["local", "remote"],
            "baseline": "Backup, audit and local checkpoints.",
            "collaboration": "Remote sync may delete everything.",
        },
        {
            "case_id": "synthetic_design_ties",
            "required": ["approval"],
            "forbidden": ["no review"],
            "alternatives": [],
            "baseline": "Approval is necessary.",
            "collaboration": "Approval is necessary.",
        },
    ]


def main():
    print(json.dumps(evaluate_fixture_suite(synthetic_fixtures()),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
