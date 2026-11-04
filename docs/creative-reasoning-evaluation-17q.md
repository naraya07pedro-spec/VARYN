# 17Q | Collaborative Reasoning & Creativity: testable offline contract

**Date:** 2026-11-04. Branch: `feat/local-memory-prototype-20261103`; PR #1 DRAFT. No main merge.

## What actually changed

1. The existing three-role collaboration prompts now explicitly differentiate work:
   - **Analyst / Divergence:** up to three materially different approaches (conventional, inverted constraint, cross-domain), mechanisms, assumptions and trade-offs.
   - **Critic / Adversarial verification:** steelman strongest counterargument, second-order impacts, failures, evidence gaps, simpler rival.
   - **Synthesizer / Convergence:** compare options, choose and justify a direction, propose mitigation and cheap falsification test, preserve uncertainty.
   These prompts can influence language-model outputs, but prompt design alone DOES NOT demonstrate creativity or reasoning improvement.

2. `varyn/reasoning_eval.py` implements a **reproducible, zero-network** rubric comparison. A trusted human supplies bounded literal criteria: required phrases (maximum 12), forbidden mentions (maximum 12), and named alternative concepts (maximum 12). The evaluator counts boundary-aware case-insensitive occurrences, computes required-coverage ratios and deltas, and explicitly marks `factual_truth_verified=false`, `human_creativity_judged=false`, `improvement_proven=false`, `controlled_baseline=false` and `quality_winner=null`. Its negative-check is **mention detection**, not semantic contradiction detection. For example, saying *do not delete everything* still counts the phrase *delete everything*.
   
3. `compare_collaboration_report` compares **Analyst output from the same run** against **Synthesizer output**, keeping the Critic as intervening work. This is NOT a controlled single-model vs multi-model benchmark. It neither runs a matched standalone baseline nor verifies the model behind an adapter. It does not grade truth, novelty or real-world effectiveness.

4. VARYN Desktop adds **Evaluate last collaboration** after a successful collaboration result. The button accepts user-authored JSON containing exactly `case_id`, `required`, `forbidden`, and `alternatives`; the evaluation runs locally without additional provider requests and displays the two literal coverages and forbidden/alternative counts, explicitly warning that quality superiority is NOT established. The last report stays in RAM for this desktop session; no report is newly persisted by this feature.

5. A built-in **synthetic regression demonstration** contains one case where collaborative literal coverage improves, one where it declines, and one tie. Run `python -m varyn.reasoning_eval` to see deterministic JSON output. This deliberately forbids cherry-picked positive-only evidence. It is synthetic text, **not a performance result from live ChatGPT, Claude, Gemini or any other model.**

## Safety and methodological limits

- No credentials, private notes, browser history, physical device data, external graders, paid APIs or official consumer-app histories are accessed by the evaluator.
- The user-selected Option C, automatic bi-directional syncing of actual official ChatGPT/Claude/Gemini consumer apps, is unchanged and BLOCKED pending verified official read/write permissions.
- Matching a phrase cannot prove an assertion is true, that it is endorsed rather than negated, or that a design is meaningfully original. Human judgment and external verification remain essential.
- Fake provider runs only exercise plumbing; they **never** justify claims of cross-provider intelligence or better creativity.
- A rigorous later controlled study needs identical tasks, same budget/time constraints, standalone model baselines, independent blinded human evaluation, inter-rater reliability, repeated samples, safety regression tracking and documented provider versions. The literal rubric is a diagnostic building block, not such a study.

## Validation

- `tests/test_reasoning_eval.py`: adversarial matching and false-quality-claim tests, input bounds, synthetics where collaboration loses, suite repeatability, report consistency and rubric validation.
- `tests/test_reasoning_eval_desktop.py`: user-authored rubric callback, cancellation, bad rubric, no result, busy state.
- `tests/test_reasoning_eval_tk.py`: hosted Windows native Tk evaluation button with synthetic in-memory report; programmatic UI invocation, not a human click.
- The entire previous Windows/Ubuntu regression suite remains mandatory, including 17K–17P, memory consent, task recovery and Option C no-sync gates. Final results must be verified at the last code/docs commit.

**Checkpoint verdict:** A real creative role protocol plus an offline, auditable evaluation method is implemented. Empirical model superiority has not been demonstrated.
