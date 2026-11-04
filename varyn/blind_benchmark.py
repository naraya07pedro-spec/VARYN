"""17R: offline blinded paired benchmark protocol, not evidence of AI superiority.

No calls to model APIs. The user supplies frozen outputs and metadata.
Rater cards omit arm and provider labels; the organizer keeps a separate key.
Raw outputs are NEVER saved by this module or sent over any network.
"""
from hashlib import sha256
from hmac import new as hmac_new
import json
import re

from varyn.reasoning_eval import EvaluationError

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_RATER = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
_MAX_CASES = 30
_DIMENSIONS = ("accuracy", "reasoning", "creativity", "usefulness")
_ALLOWED_ARMS = ("single", "collaboration")


def _canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _require(condition, reason):
    if not condition:
        raise EvaluationError(reason)


def prepare_blinded(cases, *, organizer_secret):
    """Return separated blind cards and confidential answer key.

    Secret never appears in the reviewer packet; organizer must safeguard
    the returned key and prevent evaluator access until scoring is locked.
    """
    _require(type(organizer_secret) is str and
             16 <= len(organizer_secret) <= 128, "Organizer secret too short")
    _require(type(cases) is list and 1 <= len(cases) <= _MAX_CASES,
             "Expected 1..30 matched cases")
    cards, mapping, seen = [], {}, set()
    for case in cases:
        _require(type(case) is dict and set(case) == {
            "case_id", "task", "single", "collaboration",
            "single_meta", "collaboration_meta"
        }, "Invalid paired-case schema")
        case_id, task = case["case_id"], case["task"]
        _require(type(case_id) is str and bool(_ID.fullmatch(case_id))
                 and case_id not in seen, "Case ID invalid or duplicated")
        _require(type(task) is str and 1 <= len(task.strip()) <= 1200,
                 "Task must be 1..1200 chars")
        seen.add(case_id)
        for arm in _ALLOWED_ARMS:
            result = case[arm]
            _require(type(result) is str and 1 <= len(result.strip()) <= 20000,
                     "Output must be 1..20000 chars")
            meta = case[arm + "_meta"]
            _require(type(meta) is dict and set(meta) == {
                "requested_models", "requests", "reserved_output_tokens",
                "reported_input_tokens", "reported_output_tokens",
                "elapsed_ms", "api_cost_usd", "provider_attested",
            }, "Missing or unexpected provenance/budget metadata")
            _require(type(meta["requested_models"]) is list and
                     1 <= len(meta["requested_models"]) <= 3 and
                     all(type(x) is str and 1 <= len(x) <= 100
                         for x in meta["requested_models"]), "Model metadata invalid")
            for field in ("requests", "reserved_output_tokens",
                          "reported_input_tokens", "reported_output_tokens",
                          "elapsed_ms"):
                val = meta[field]
                _require(val is None or (type(val) is int and val >= 0),
                         "Invalid usage metadata")
            _require(meta["requests"] is not None and meta["requests"] >= 1,
                     "Request count required")
            _require(meta["reserved_output_tokens"] is not None and
                     meta["reserved_output_tokens"] >= 16,
                     "Reserved token budget required")
            price = meta["api_cost_usd"]
            _require(price is None or
                     (type(price) in (float, int) and price >= 0 and price < 1e7),
                     "Invalid reported cost")
            _require(type(meta["provider_attested"]) is bool,
                     "Attestation status must be bool")
        # Deterministic balance from organizer-only secret, not provider label.
        digest = hmac_new(organizer_secret.encode(), case_id.encode(), sha256).digest()
        order = ("single", "collaboration") if digest[0] % 2 == 0 else (
            "collaboration", "single"
        )
        mapping[case_id] = {"A": order[0], "B": order[1]}
        cards.append({
            "case_id": case_id, "task": task,
            "A": case[order[0]], "B": case[order[1]],
            "instructions": "Rate both blindly; higher is better (1..5).",
        })
    packet = {
        "format": "varyn.blind_packet.v1",
        "rubric_dimensions": list(_DIMENSIONS),
        "cases": cards,
        "rater_guidance": "Independent ratings. Do not see the organizer key, source, provider, or model before submitting.",
        "network_calls": 0,
    }
    key = {
        "format": "varyn.organizer_key.v1",
        "mapping": mapping,
        "metadata": {
            case["case_id"]: {
                "single": case["single_meta"],
                "collaboration": case["collaboration_meta"],
            } for case in cases
        },
        "packet_sha256": sha256(_canonical(packet).encode()).hexdigest(),
        "secret_included": False,
    }
    return packet, key


def score_blinded(packet, key, ratings):
    """Requires >=2 independent raters per case, report disagreements.

    This is a descriptive report, not p-values, calibrated judges, an RCT,
    or independently authenticated real model/provider runs.
    """
    _require(type(packet) is dict and packet.get("format") ==
             "varyn.blind_packet.v1", "Invalid blind packet")
    _require(type(key) is dict and key.get("format") ==
             "varyn.organizer_key.v1", "Invalid organizer key")
    _require(sha256(_canonical(packet).encode()).hexdigest() ==
             key.get("packet_sha256"), "Packet modified since blind prep")
    cases = packet.get("cases")
    mapping = key.get("mapping")
    meta = key.get("metadata")
    _require(type(cases) is list and type(mapping) is dict and
             type(meta) is dict and len(cases) == len(mapping) == len(meta) and
             1 <= len(cases) <= _MAX_CASES, "Broken study mapping")
    _require(type(ratings) is list and 2 <= len(ratings) <= 300,
             "Require independent rater submissions")
    case_ids = {x["case_id"] for x in cases}
    _require(len(case_ids) == len(cases) and
             set(mapping) == case_ids and set(meta) == case_ids,
             "Case mapping inconsistent")
    collected = {cid: {} for cid in case_ids}
    for record in ratings:
        _require(type(record) is dict and set(record) == {
            "case_id", "rater_id", "A", "B"
        }, "Invalid rating record")
        cid, rater = record["case_id"], record["rater_id"]
        _require(cid in case_ids and type(rater) is str and
                 bool(_RATER.fullmatch(rater)) and
                 rater not in collected[cid], "Unknown or duplicate rater")
        for label in ("A", "B"):
            values = record[label]
            _require(type(values) is dict and
                     set(values) == set(_DIMENSIONS) and
                     all(type(values[d]) is int and 1 <= values[d] <= 5
                         for d in _DIMENSIONS), "Invalid blinded scores")
        collected[cid][rater] = record
    rows = []
    for cid in sorted(case_ids):
        votes = list(collected[cid].values())
        _require(len(votes) >= 2, "At least two unique raters per task")
        _require(set(mapping[cid].keys()) == {"A", "B"} and
                 set(mapping[cid].values()) == set(_ALLOWED_ARMS),
                 "Bad sealed arm mapping")
        means = {}
        disagreement = {}
        for arm in _ALLOWED_ARMS:
            label = "A" if mapping[cid]["A"] == arm else "B"
            means[arm] = {
                dim: round(sum(v[label][dim] for v in votes) / len(votes), 3)
                for dim in _DIMENSIONS
            }
            disagreement[arm] = {
                dim: max(v[label][dim] for v in votes) -
                     min(v[label][dim] for v in votes)
                for dim in _DIMENSIONS
            }
        provenance = meta[cid]
        _require(set(provenance) == set(_ALLOWED_ARMS), "Bad provenance")
        sm, cm = provenance["single"], provenance["collaboration"]
        _require(type(sm) is dict and type(cm) is dict,
                 "Missing budget metadata")
        budget_matched = (
            sm.get("reserved_output_tokens") == cm.get("reserved_output_tokens")
            and sm.get("reported_input_tokens") is not None
            and cm.get("reported_input_tokens") is not None
            and sm.get("reported_input_tokens") == cm.get("reported_input_tokens")
        )
        rows.append({
            "case_id": cid,
            "rater_count": len(votes),
            "mean_scores": means,
            "collaboration_minus_single": {
                dim: round(means["collaboration"][dim] -
                           means["single"][dim], 3)
                for dim in _DIMENSIONS
            },
            "rater_score_range": disagreement,
            "request_count_single": sm.get("requests"),
            "request_count_collaboration": cm.get("requests"),
            "reserved_token_budget_matched": budget_matched,
            "provider_attested_both": (
                sm.get("provider_attested") is True and
                cm.get("provider_attested") is True
            ),
            "actual_cost_verified": False,
        })
    return {
        "format": "varyn.blind_study.v1",
        "results": rows,
        "cases": len(rows),
        "raters_per_case_min": min(x["rater_count"] for x in rows),
        "all_token_budgets_matched": all(
            row["reserved_token_budget_matched"] for row in rows
        ),
        "all_providers_attested": all(
            row["provider_attested_both"] for row in rows
        ),
        "blindness_independently_verified": False,
        "human_independence_authenticated": False,
        "performance_superiority_proven": False,
        "statistical_significance_claimed": False,
        "network_calls": 0,
    }

def synthetic_demo():
    """Fabricated paired outputs, NOT actual model performance."""
    def meta(requests, models):
        return {
            "requested_models": models, "requests": requests,
            "reserved_output_tokens": 768,
            "reported_input_tokens": None, "reported_output_tokens": None,
            "elapsed_ms": None, "api_cost_usd": None,
            "provider_attested": False,
        }
    cases = [
        {
            "case_id": "synthetic_improvement",
            "task": "Invented local workflow design",
            "single": "Offline execution.",
            "collaboration": "Offline execution with consent and recovery.",
            "single_meta": meta(1, ["fake-test"]),
            "collaboration_meta": meta(3, ["fake-test"] * 3),
        },
        {
            "case_id": "synthetic_regression",
            "task": "Invented backup choice",
            "single": "Backup and test restoration.",
            "collaboration": "Delete backups and skip review.",
            "single_meta": meta(1, ["fake-test"]),
            "collaboration_meta": meta(3, ["fake-test"] * 3),
        },
    ]
    packet, key = prepare_blinded(
        cases, organizer_secret="synthetic-demo-secret-not-for-real",
    )
    ratings = []
    for card in packet["cases"]:
        cid = card["case_id"]
        for rater in ("synthetic_rater_one", "synthetic_rater_two"):
            scores = {}
            for label in ("A", "B"):
                arm = key["mapping"][cid][label]
                preferred = (
                    (cid == "synthetic_improvement" and arm == "collaboration")
                    or (cid == "synthetic_regression" and arm == "single")
                )
                scores[label] = {
                    dim: 5 if preferred else 2 for dim in _DIMENSIONS
                }
            ratings.append({
                "case_id": cid, "rater_id": rater,
                "A": scores["A"], "B": scores["B"],
            })
    report = score_blinded(packet, key, ratings)
    report["synthetic_demo_only"] = True
    report["real_model_outputs_used"] = False
    return report


if __name__ == "__main__":
    print(json.dumps(synthetic_demo(), sort_keys=True, indent=2))
