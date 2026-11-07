"""Deterministic grounding of a *structured public GitHub metadata claim*.

This validates a model's exact factual fields against a consent-gated public
tool observation. It never certifies unstructured prose or the underlying
truth of third-party data. No model, network or shell calls occur here.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

from varyn.learning_kernel import LearningKernel, LearningRejected


class GroundingRejected(ValueError):
    pass


_FACT_KEYS = frozenset({
    "repository", "default_branch", "stars",
    "open_items_including_prs", "archived",
})
_REPO = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_BRANCH = re.compile(r"\A[A-Za-z0-9_./-]{1,150}\Z")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GroundingRejected("Duplicate JSON key")
        result[key] = value
    return result


def _facts(record):
    """Allow only tightly bounded GitHub metadata scalars."""
    if (type(record) is not dict
            or record.get("format") != "varyn.github_public_repo_metadata.v1"
            or record.get("public") is not True
            or record.get("read_only") is not True
            or record.get("untrusted_external_data") is not True
            or record.get("provider_handoff") is not False):
        raise GroundingRejected("Not a validated public GitHub observation")
    facts = {key: record.get(key) for key in _FACT_KEYS}
    if (type(facts["repository"]) is not str
            or _REPO.fullmatch(facts["repository"]) is None
            or len(facts["repository"]) > 141
            or type(facts["default_branch"]) is not str
            or _BRANCH.fullmatch(facts["default_branch"]) is None
            or type(facts["stars"]) is not int or not 0 <= facts["stars"] <= 10**10
            or type(facts["open_items_including_prs"]) is not int
            or not 0 <= facts["open_items_including_prs"] <= 10**10
            or type(facts["archived"]) is not bool):
        raise GroundingRejected("Invalid public metadata fields")
    return facts


def validate_grounded_claim(raw, observation):
    """Require exact factual equality, never ask the model to grade itself.

    Returns a deterministic textual report and a digest of observed scalars.
    It verifies agreement with the received tool observation ONLY.
    """
    if (type(raw) is not str or
            not 1 <= len(raw.encode("utf-8")) <= 2500):
        raise GroundingRejected("Bounded JSON fact claim required")
    if (type(observation) is not dict
            or observation.get("network_dispatched") is not True
            or observation.get("status") != "completed"):
        raise GroundingRejected("No successful approved tool observation")
    expected = _facts(observation.get("result"))
    try:
        claim = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _x: (_ for _ in ()).throw(
                GroundingRejected("Non-finite JSON is not accepted")))
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise GroundingRejected("Model did not provide valid JSON facts") from None
    if (type(claim) is not dict or set(claim) != {"action", "facts"}
            or claim["action"] != "finish"
            or type(claim["facts"]) is not dict
            or set(claim["facts"]) != _FACT_KEYS):
        raise GroundingRejected("Model must return exact fact schema")
    for key in _FACT_KEYS:
        if type(claim["facts"][key]) is not type(expected[key]):
            raise GroundingRejected("Model fact field type mismatch")
        if claim["facts"][key] != expected[key]:
            raise GroundingRejected("Model fact does not match observation")
    # Do not display free-form unverifiable model prose as verified output.
    repo = expected["repository"]
    branch = expected["default_branch"]
    report = (
        "Public GitHub repository: " + repo + "\n"
        "Default branch: " + branch + "\n"
        "Stars: " + str(expected["stars"]) + "\n"
        "Open issues count (includes pull requests): "
        + str(expected["open_items_including_prs"]) + "\n"
        "Archived: " + ("Yes" if expected["archived"] else "No")
    )
    canonical = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    return {
        "report": report,
        "observation_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        "verified_against_tool_observation": True,
        "third_party_truth_independently_verified": False,
        "model_prose_verified": False,
        "repository": repo,
    }


def record_grounded_fact_receipt(kernel, verified_claim):
    """Record a successful read/check, NOT independent quality of a model.

    The trusted host must pass a verified_claim produced directly by
    validate_grounded_claim, not external or model-generated dictionaries.
    This API is NOT a standalone authentication boundary.
    """
    if (not isinstance(kernel, LearningKernel)
            or type(verified_claim) is not dict
            or verified_claim.get("verified_against_tool_observation") is not True
            or type(verified_claim.get("observation_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}",
                            verified_claim["observation_sha256"]) is None
            or type(verified_claim.get("repository")) is not str
            or _REPO.fullmatch(verified_claim["repository"]) is None):
        raise GroundingRejected("Host-validated observation required")
    family = "github_public_facts"
    receipt = verified_claim["observation_sha256"]
    # Deduplicate identical factual observations of a repository. Repeating
    # the same read is not independent new evidence of better reasoning.
    task_id = "public-github:" + verified_claim["repository"] + ":" + receipt
    try:
        ident = kernel.record_verified_outcome(
            family, task_id, receipt,
            succeeded=True, verified_by_host=True)
    except LearningRejected as error:
        if str(error) == "Duplicate task receipt":
            return {"status": "duplicate", "outcome_id": None}
        raise
    return {"status": "recorded", "outcome_id": ident}
