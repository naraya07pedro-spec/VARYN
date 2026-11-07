# VARYN evidence-gated reflection worker (Stage 3)

This stage connects the verified-outcome registry (PR #2) to automatically
**propose, evaluate, accept or reject** a new versioned procedural skill.
It builds on the owner-approved execution loop (PR #3).

## Required trusted inputs

- At least two distinct, independently host-verified successful task outcomes
  belonging to the same skill family.
- Short lessons that the host explicitly reviewed and **declassified**. Lessons
  are held in RAM and passed to a registered reflector callback.
- A *separate* host-owned evaluator, with 5 to 40 distinct held-out case IDs
  that are **not disclosed to the reflector**.
- Both allow_declassified_reflection and trusted_evaluator must be explicitly
  true. These flags are trusted host assertions, NOT authentication.
- The reflector may generate skill text but cannot grant tools or choose test
  results. Improvement requires one new pass and zero previously-passing
  regressions. Otherwise the candidate is rejected.
- A source batch is fingerprinted, claimed once, and not processed again
  automatically after a failure. Failed attempts remain needs_review.
- Plaintext skill text is the only proposed artifact. It is an UNTRUSTED
  procedural reference, not system policy, software code, or tool authority.

## Privacy and scope limitations

- Does not read original private task text, provider logs, or user histories.
- Declassified lesson excerpts are not persisted in reflection_attempts.
- The existing LearningKernel stores skill bodies in local **plaintext**
  SQLite. Do not include personal data, credentials or confidential examples.
- An obvious-secret preflight is NOT comprehensive privacy/DLP protection.
- Reflector and evaluator are provided by trusted host code. No model
  integration, authentication, recurring scheduling, budget tracking, or
  Windows GUI activation is added automatically by this stage.
- The callback could invoke an LLM, but any external transmission must use
  independently scoped owner authorization and appropriate provider keys.
- Passing deterministic CI proves state transitions, NOT real-world skill
  quality, independent external evaluation or always-on autonomous learning.

## Verification

python -m unittest discover -s tests -p 'test_verified_reflection.py' -v

Run this together with test_learning_kernel.py and test_agent_execution_loop.py
on both Windows and Ubuntu.

## Next stages

1. Build trusted owner UI for the read-only execution loop.
2. Attach verified completion criteria to actual task results and collect
   reusable, consent-reviewed declassified lessons.
3. Provide local/background reflection with strict resource limits, prompt
   provenance, separate evaluator, and protected hold-out test suite.
4. Use canary runs, telemetry, and existing rollback before expanding to
   additional skills or code evolution.

PR #4 is stacked on PR #3, which is stacked on PR #2 and PR #1. No direct
main-branch changes are made.
