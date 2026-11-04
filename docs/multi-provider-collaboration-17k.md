# Checkpoint 17K: First real multi-provider collaboration engine

**Date:** 2026-11-04. Branch: feat/local-memory-prototype-20261103, PR #1 DRAFT.
**Primary aim:** Make VARYN genuinely pass work through a three-stage chain (analyst -> critic -> synthesizer) using its **existing provider adapters**, rather than merely placing three labels on one model response. This is a library engine, not yet integrated into the Tk desktop.

## Delivered code

- varyn/collaboration.py: Stage, StageResult, CollaborationEngine, CollaborationError.
- Three mandatory explicit roles in one sequential work item: analyst constructs an answer, critic receives the original task AND analyst output as **untrusted text**, synthesizer receives the original task plus both earlier responses. The result contains each response, provider/model ID, sanitized reported usage, final answer and budget snapshot. A stage failure aborts subsequent stages with no automatic retry or failover.
- Uses existing ProviderRouter and BudgetedRouter, not a new undocumented model client or official-app history scraper. Provider IDs are fake/openai/anthropic/gemini and models are explicitly selected by the calling application.
- Live API dispatch is disabled unless allow_live=True at engine construction and **every individual live stage's positional confirmation is True**. A missing/False/invalid confirmation blocks the **whole plan before any stage**. No provider keys or network requests were used by 17K tests. The real existing API adapters may contact and bill providers if the host app explicitly opts in, configures credentials and confirms every step.
- Preflights exact role ordering, stage/model names, bounded task length, context schema/consent, provider registry, total local request/output reservation headroom. A context package is only passed to the FIRST stage under explicit context-upload consent. Intermediate model outputs are intentionally sent to subsequent explicitly selected providers: **the host UI must disclose this cross-provider sharing before allowing live stages**. The engine itself is not a consumer GUI and must NOT treat Python call arguments as authenticated human consent.
- Each prior stage response is tagged "UNTRUSTED DATA", and truncated to 950 characters inside the next request. This is a prompt-injection mitigation, not a mathematically guaranteed containment boundary.
- Report reflects work actually attempted: distinct_provider_model_pairs counts model/provider selections, but multi_model_review is FALSE for all-fake models and for only one non-fake provider. It becomes TRUE only if at least two distinct non-fake provider names are requested in a completed collaboration. **It does not prove actual identity of underlying models** (live_execution_independently_attested=false). Factual correctness and output quality are not independently verified.
- UsageBudget reservations are **local, in-memory request and maximum output-token allocations**, not a provider billing ceiling. Rejected calls retain no automatic retry; failed/uncertain calls may still cost money. A failed or malformed model response stops the workflow; text from errors is sanitized. A process restart loses in-memory progress.
- No automatic memory read/write, autonomous tool execution, official consumer-app sync, operating system isolation, or real user-account data touched in this checkpoint.

## Example embedded use by a trusted caller (not an owner-facing unattended script)

    from varyn.collaboration import CollaborationEngine, Stage
    from varyn.multi_provider import ProviderRouter
    from varyn.providers import FakeProvider

    router = ProviderRouter(providers={"fake": FakeProvider()})
    engine = CollaborationEngine(router)  # offline, default
    stages = [
        Stage("analyst", "fake", "fake-test"),
        Stage("critic", "fake", "fake-test"),
        Stage("synthesizer", "fake", "fake-test"),
    ]
    result = engine.run("Compare two synthetic designs.", stages)
    assert result["status"] == "completed"
    assert result["multi_model_review"] is False

This proves the code path, NOT model diversity. To run live, the host must deliberately install network-enabled provider adapters, configure credentials outside source, allow_live=True, obtain each-stage consent before dispatch, and budget/monitor actual costs. Never put keys in scripts or GitHub.

## Verification

Tests in tests/test_collaboration.py exercise actual role-to-role text transmission through three fake/test transport adapters with provider identities, stop-on-failure, per-stage consent, no unapproved context upload, bounded budgets and role plan validation, content/exception redaction, and false diversity claims. CI reruns the suite on both Windows and Ubuntu in addition to the full regression suite. The final run SHA/count/status is recorded in docs/progress-log.md, not inferred from a prior commit.

## Engineering limitations / next value milestone

1. Integrate a user-facing explicit stage planner and independent per-provider consent into VARYN Desktop. An unchecked checkbox or a single blanket approval must not silently authorize cross-provider forwarding of user prompts or earlier outputs.
2. Connect the real long-term memory layer by explicit project-boundary retrieval and source attribution, without automatically uploading memories to providers. Define consent and contamination controls.
3. Add deterministic quality evaluation: evidence coverage, citations, contradiction detection, repeated runs and comparisons with single-model baseline. Human verification remains required for high-stakes outputs.
4. Add durable checkpoints and controlled resume for long workflows: never replay uncertain billable stages automatically, track idempotency and approval freshness.
5. Official ChatGPT/Claude/Gemini consumer-app two-way history sync (Option C) remains BLOCKED pending independently verified supported READ+WRITE authority for those actual apps. Developer model APIs are not substitutes.

**Decision:** This is a genuine new collaboration *engine* with real role handoff capability, ready for further integration work. It is not yet a fully integrated autonomous multi-model product.
