# VARYN Stage 6: Verified Failure Feedback + Bounded Reflection

This is a **real integration milestone**, not a claim of self-learning
model weights or fully unattended intelligence. Based on PR #6.

## What now works

1. The existing Windows public GitHub agent's optional "Store hashed
   fact-match receipts AND failure categories" toggle covers BOTH validated
   successes and deterministic fact mismatch failures. It defaults OFF.
2. On a mismatching structured response, the trusted host stores one record
   of the failure **category** and a SHA-256 fingerprint of the original
   approved public GitHub observation. No raw model answer, user prompt,
   task ID, API key, tool description or personal conversation is recorded.
3. Factual failures are **never treated as successful outcomes**. Previous
   success receipt behavior remains subject to independent comparison.
4. GroundedFactBenchmark runs 5-20 host-owned, case-specific reference
   checks; the reflector receives no held-out cases. Runner responses
   are checked through the deterministic grounded GitHub verifier.
5. BudgetedReflectionScheduler can be invoked by a trusted host. An
   owner-approved tick requires a feedback failure, >=2 different verified
   successful outcome receipts, an owner-declassified safe lesson, a separate
   trusted evaluator, and resource-budget gates.
6. The scheduler reserves evaluation-call slots in SQLite BEFORE calling
   a runner; it defaults to 1 learning cycle per UTC day and at most 20
   evaluator invocations (two comparisons per case). On a crash the run
   stays needs_review, cannot replay, and still consumes its reservation.
7. A fixed, conservative, offline public-facts skill proposal is available
   as an example reflector. A candidate is selected ONLY when the
   independent evaluator shows >=1 additional success with no previously
   successful test regressing. Rejected candidates do not replace the
   active version. Existing LearningKernel rollback remains available.
8. Identical source/failure batches are never automatically repeated, even
   on a later day or after an interrupted evaluation.

## Explicit boundaries

- NO actual background daemon or Windows scheduled task is installed.
  The trusted host must invoke a tick while running. This milestone is
  the **durable bounded scheduler engine**, not unattended orchestration.
- NO real external model is invoked by the scheduler itself. Benchmark
  runners and reflectors are trusted callbacks supplied by the host.
- If a host chooses a billable model as an evaluator, **these counters
  only cap callback invocations**; they are NOT provider billing caps,
  token limits, usage verification or cross-device rate limits. The host
  must separately authorize each real provider request and enforce its
  actual account-specific budget.
- The callback trusted_evaluator=True is NOT proof of independence or
  caller authentication. Do NOT expose scheduler methods directly to AI
  tools, remote HTTP clients or untrusted plugins.
- Benchmark cases must be protected outside the candidate-generating
  model's reach. Synthetic CI cases are NOT evidence of real-world gains.
- A fact mismatch confirms disagreement with the approved tool response.
  It does not independently prove third-party GitHub facts are globally
  correct or that a model improved in general.
- LearningKernel skill text remains plaintext SQLite and lower-trust
  reference material, never executable code or elevated system policy.
  Safe lesson strings are generated from fixed templates and are held
  in RAM; they are not private scraped chat excerpts.
- This is not automatic native ChatGPT/Claude/Gemini synchronization,
  self-modifying production software, account access or background
  VPS deployment.

## Test commands

    python -m unittest discover -s tests -p "test_feedback_evaluation_scheduler.py" -v
    python -m unittest discover -s tests -p "test_grounded_learning_bridge.py" -v
    python -m unittest discover -s tests -p "test_verified_reflection.py" -v
    python -m unittest discover -s tests -p "test_agent_execution_loop.py" -v

CI tests Windows and Ubuntu. Windows Tk owner-agent smoke remains enabled.

## Next execution gate

A trusted owner app can opt-in to scheduled evaluations by connecting
the evaluator to a **real** independently verified model task runner
using a separate provider budget, hidden review cases and captured
acceptance evidence. That gate is not enabled just because CI passes.
