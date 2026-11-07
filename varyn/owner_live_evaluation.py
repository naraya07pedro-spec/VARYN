"""Owner-reviewed LIVE public-GitHub evaluation using existing VARYN gateways.

This module is the first executable bridge between the durable reflection
scheduler and an actual configured OpenRouter/DeepSeek model. It may make
15 network requests (5 approved public GitHub GETs plus 10 separately
approved model calls), ONLY when every owner consent is granted.

IMPORTANT: estimate limits are NOT provider-enforced billing ceilings.
No daemon, account-login bypass, automatic approval, retry or write tools.
"""
from datetime import date
from hashlib import sha256
import json

from varyn.budgeted_reflection_scheduler import (
    BudgetedReflectionScheduler, conservative_public_fact_reflector)
from varyn.grounded_benchmark import GroundedFactBenchmark
from varyn.learning_kernel import LearningKernel
from varyn.public_github_tool import (
    PublicGithubToolGateway, parse_public_tool_intent)
from varyn.safety import assert_no_obvious_secrets
from varyn.universal_gateway import UniversalGateway
from varyn.verified_failure_feedback import VerifiedFailureLedger


class LiveEvaluationRejected(ValueError):
    pass


# Fixed PUBLIC targets, not model-chosen destinations. Five different
# repositories avoid treating one repeatedly copied snapshot as five cases.
PUBLIC_CASE_REPOSITORIES = (
    "python/cpython",
    "pallets/flask",
    "django/django",
    "psf/requests",
    "github/docs",
)


class OwnerReviewedLiveEvaluation:
    """One reviewed session, five distinct public observations, ten LLM calls.

    The host must supply callbacks that interact with a real trusted owner
    UI. An LLM-provided or remote untrusted callback is NOT authority.
    """
    def __init__(self, model_gateway, public_tool, kernel):
        if (not isinstance(model_gateway, UniversalGateway)
                or not isinstance(public_tool, PublicGithubToolGateway)
                or not isinstance(kernel, LearningKernel)):
            raise TypeError("VARYN gateways and LearningKernel required")
        self.gateway = model_gateway
        self.public_tool = public_tool
        self.kernel = kernel
        self.ledger = VerifiedFailureLedger(kernel)
        self.scheduler = BudgetedReflectionScheduler(kernel, self.ledger)

    def readiness(self, *, provider, input_estimate=512,
                  output_limit=256, max_total_estimate_micro_usd=100000):
        if (provider not in ("openrouter", "deepseek")
                or type(input_estimate) is not int
                or not 64 <= input_estimate <= 1024
                or type(output_limit) is not int
                or not 64 <= output_limit <= 512
                or type(max_total_estimate_micro_usd) is not int
                or not 0 <= max_total_estimate_micro_usd <= 100000):
            raise LiveEvaluationRejected("Invalid fixed evaluation limits")

        selected, quote = self.gateway.registry.choose(
            input_estimate=input_estimate, output_limit=output_limit,
            ceiling_micro_usd=max_total_estimate_micro_usd,
            today=date.today(), provider=provider)
        if selected.provider != provider or selected.provider == "fake":
            raise LiveEvaluationRejected("A reviewed live route is required")

        estimated_total = quote * 10
        if estimated_total > max_total_estimate_micro_usd:
            return {"status": "estimate_exceeded", "estimated_micro_usd":
                    estimated_total, "model": selected.model}
        snapshot = self.gateway.budget.snapshot()
        remaining_requests = (
            snapshot["max_requests"] - snapshot["requests_reserved"])
        remaining_output = (
            snapshot["max_reserved_output_tokens"] -
            snapshot["output_tokens_reserved"])
        successes = self.kernel.db.execute(
            "SELECT COUNT(*) FROM outcomes "
            "WHERE family='github_public_facts' AND succeeded=1"
        ).fetchone()[0]
        failures = self.ledger.summary()["total_failed_fact_checks"]
        # Check the durable scheduler BEFORE spending GitHub GET quota.
        # If a previous run/crash consumed the same source batch, refuse to
        # fetch five public references for a doomed second attempt.
        schedule = self.scheduler.preflight(
            case_count=5, max_cycles_per_utc_day=1,
            max_evaluator_calls_per_utc_day=10)
        enough_evidence = successes >= 2 and failures >= 1
        enough_model_budget = (
            remaining_requests >= 10
            and remaining_output >= 10 * output_limit)
        reason = (
            "insufficient_evidence" if not enough_evidence else
            "insufficient_model_budget" if not enough_model_budget else
            schedule["status"]
        )
        return {
            "status": reason,
            "model": selected.model,
            "provider": provider,
            "verified_successes": successes,
            "verified_failures": failures,
            "max_public_reads": 5,
            "max_model_requests": 10,
            "max_reserved_output_tokens": 10 * output_limit,
            "estimated_micro_usd": estimated_total,
            "provider_billing_cap_enforced": False,
            "live_network_dispatched": False,
        }

    def run(self, *, provider, review_model, review_tool,
            owner_enabled=False, max_total_estimate_micro_usd=100000,
            repositories=PUBLIC_CASE_REPOSITORIES,
            input_estimate=512, output_limit=256):
        if owner_enabled is not True:
            return {"status": "disabled", "public_reads": 0,
                    "model_calls": 0}
        if (not callable(review_model) or not callable(review_tool)
                or type(repositories) is not tuple
                or len(repositories) != 5 or len(set(repositories)) != 5):
            raise LiveEvaluationRejected("Five distinct approved public cases required")
        if repositories != PUBLIC_CASE_REPOSITORIES:
            raise LiveEvaluationRejected("Unreviewed evaluation target set refused")
        # Check precise read-only intent parsing before any network call.
        for repo in repositories:
            raw = json.dumps({
                "format": "varyn.public_tool_intent.v1",
                "tool": "github_public_repo_metadata",
                "arguments": {"repository": repo},
            })
            if parse_public_tool_intent(raw) != repo:
                raise LiveEvaluationRejected("Invalid public case")
        readiness = self.readiness(
            provider=provider, input_estimate=input_estimate,
            output_limit=output_limit,
            max_total_estimate_micro_usd=max_total_estimate_micro_usd)
        if readiness["status"] != "ready":
            return {**readiness, "public_reads": 0, "model_calls": 0}

        # The public case observations are genuine tool results, never
        # generated by the model. Each GET gets a one-use owner review.
        cases = []
        read_count = 0
        for index, repo in enumerate(repositories):
            intent = json.dumps({
                "format": "varyn.public_tool_intent.v1",
                "tool": "github_public_repo_metadata",
                "arguments": {"repository": repo},
            })
            proposal = self.public_tool.propose(intent, network_consent=True)
            choice = review_tool(proposal)
            if type(choice) is not bool:
                self.public_tool.reject_all_pending()
                raise LiveEvaluationRejected("Owner review must be exact bool")
            response = self.public_tool.decide(
                proposal.proposal_id, proposal.digest, approved=choice,
                network_consent=choice)
            if choice is not True:
                return {"status": "public_read_denied",
                        "public_reads": read_count, "model_calls": 0}
            if response["status"] != "completed":
                raise LiveEvaluationRejected("Public metadata read incomplete")
            read_count += 1
            cases.append({
                "id": "livecase-" + str(index),
                "observation": response,
            })

        model_calls = 0
        def model_runner(skill_text, case_id, public_fields):
            nonlocal model_calls
            # A candidate is strictly lower-trust reference text. Its
            # instructions cannot authorize writes, tools or more requests.
            assert_no_obvious_secrets(skill_text)
            prompt = json.dumps({
                "task": "Return the five public GitHub metadata fields as JSON.",
                "public_metadata_untrusted_data": public_fields,
                "optional_untrusted_procedural_hint": skill_text[:800],
                "require": {
                    "action": "finish",
                    "facts": {
                        "repository": "string",
                        "default_branch": "string",
                        "stars": "integer",
                        "open_items_including_prs": "integer",
                        "archived": "boolean",
                    },
                },
                "rule": "Copy exact scalar values and JSON types. "
                        "Return one JSON object only, no markdown.",
            }, ensure_ascii=False, separators=(",", ":"))
            if len(prompt) > 4000:
                raise LiveEvaluationRejected("Benchmark prompt exceeds limit")
            approval = review_model({
                "phase": "independent_benchmark",
                "provider": provider, "case_id": case_id,
                "exact_outgoing_prompt": prompt,
                "output_token_limit": output_limit,
                "billing_is_estimate_only": True,
                "remaining_approved_model_calls": 10 - model_calls,
            })
            if type(approval) is not bool:
                raise LiveEvaluationRejected("Model review must be exact bool")
            if approval is not True:
                raise PermissionError("Owner declined an evaluation model request")
            if model_calls >= 10:
                raise LiveEvaluationRejected("Evaluation call limit reached")
            # Reserve before dispatch, including uncertain request failures.
            model_calls += 1
            result = self.gateway.generate(
                prompt, provider=provider, approve_request=True,
                allow_real_task=True, input_estimate=input_estimate,
                max_output_tokens=output_limit,
                ceiling_micro_usd=readiness["estimated_micro_usd"] // 10)
            return result["reply"].text

        bench = GroundedFactBenchmark(tuple(cases), model_runner)
        # The durable scheduler gates evidence, daily reservations and
        # promotion. Its candidate is fixed and host-controlled, and the
        # independent evaluator uses the separate real model requests.
        outcome = self.scheduler.tick(
            enabled=True, trusted_evaluator=True,
            allow_declassified_reflection=True,
            benchmark=bench, reflector=conservative_public_fact_reflector,
            max_cycles_per_utc_day=1,
            max_evaluator_calls_per_utc_day=10)
        return {
            "status": outcome["status"],
            "public_reads": read_count,
            "model_calls": model_calls,
            "estimated_micro_usd": readiness["estimated_micro_usd"],
            "actual_charges_known": False,
            "provider_billing_cap_enforced": False,
            "skill_promoted": outcome["status"] == "promoted",
            "regressions": outcome.get("regressions"),
        }
