# 17R | Blinded paired benchmark protocol (offline)

**Date:** 2026-11-04. Branch `feat/local-memory-prototype-20261103`; PR #1 remains draft, main unchanged.

## What was implemented

`varyn/blind_benchmark.py` implements a **paired, two-arm, blinded scoring protocol** over **1–30 pre-collected, frozen task/output pairs**. It does **not** invoke any AI model or independently verify the claimed provider identity. Each case contains the exact task, one standalone single-model answer, one multi-stage collaboration answer and explicit per-arm metadata for requested models, number of requests, reserved output tokens, reported input/output tokens, elapsed time, approximate USD cost, and whether provider execution is independently attested.

`prepare_blinded(cases, organizer_secret=...)` returns two separate objects:

- **Reviewer packet** with task text, answer A/B in secret-derived order, rubric dimensions `accuracy`, `reasoning`, `creativity` and `usefulness`, but **no provider identities, arm labels, usage/cost estimates or secret**.
- **Organizer-only mapping key** for converting scored A/B back to single/collaboration arms, along with claimed budget/provenance metadata and SHA-256 of the reviewer packet. The organizer must keep the key private until ratings are locked. **Packet hashing detects accidental edits; it is not a signature of the organizer key or independent proof of blinding.** Reviewers can still guess which answer is which based on style or length.

`score_blinded(packet, key, ratings)` requires **two distinct rater IDs per case** and exact numeric **1–5 scores on all four dimensions for both answers**. It validates the packet hash, checks all tasks have complete ratings, rejects invalid scores/unknown cases/duplicate rater submissions, then returns per-arm mean ratings, disagreement ranges, differences and token-budget comparison.

**Critical methodological restrictions:** A pair is reported as token-budget-matched only when the declared reserved output tokens are equal **and both reported input token counts exist and match**. Request count (typically 1 vs 3), latency, provider costs, task complexity, model capability and human/rater independence are separately reported or explicitly unverified. Therefore a fair total-cost and total-call comparison is NOT established by matching token budgets alone. A claim that `provider_attested=true` is accepted as self-supplied study metadata, **not independently verified**. Consequently the report always flags `performance_superiority_proven=false`, `human_independence_authenticated=false`, `blindness_independently_verified=false`, and `statistical_significance_claimed=false`.

## Reproducible offline demonstration

```powershell
py -3 -m varyn.blind_benchmark
```

The command prints JSON from two **invented** pairs and **invented raters**: one where the synthetic collaborative answer scores higher and one where it scores lower. All `requested_models` are `fake-test`; network calls are zero. **These numbers are not results from ChatGPT, Claude, Gemini, a real model, or human participants.**

## For a legitimate future live controlled experiment

Before requesting provider calls, register a fixed task sample independent from model selection, exact prompts/versions, model identity and date, a valid per-provider authorization pathway, a funding/cost ceiling outside the local output-token quota, and explicit API-consent steps. Run a standalone baseline on the same task, independently record measured usage and elapsed time, freeze outputs, then prepare the blind packet. Recruit actual independent reviewers and lock their ratings before revealing the organizer key. Compare paired results with uncertainty intervals and predeclared effect sizes, and report all negative results and costs. Repeating the same model call does not substitute for distinct independent provider models.

There is **no automatic paid study runner** in 17R, and no real-world improvement claim. The study harness is suitable for **offline trial-design and scorekeeping**, not for stating multi-AI works better.

## Evidence and remaining limits

- `tests/test_blind_benchmark.py`: bounded schemas; blind labels and secret separation; deterministic ordering; both improvement/regression; invalid scores and raters; missing cases; tampering with reviewer packets; falsifiable token-budget match; request-count differentiation; spoofed provider/provenance not treated as independent proof.
- CI runs both the test suite and the synthetic demonstration on Ubuntu and Windows. Final evidence must refer to the exact final source/documentation commit.
- Does NOT sync the official consumer ChatGPT/Claude/Gemini app histories. User-selected **Option C remains blocked** absent proven provider-supported read/write/history authorization.
