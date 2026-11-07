# Stage 5: Grounded public facts and opt-in learning receipts

This stage builds on VARYN's experimental public GitHub agent in PR #5.

## Working path

1. In the Windows Public GitHub agent window, choose an authorized model
   and enable one reviewed public read and a separately approved upload of
   the public observations back to that model.
2. The model initially proposes ONE public read via the existing restricted
   gateway. After a successful read, the second model response must be
   structured JSON containing exactly these observed public fields:
   repository, default_branch, stars, open_items_including_prs, archived.
3. Host code compares **all five types and values** to the actual output
   from the consent-gated public tool. It rejects malformed, additional or
   inconsistent fields, without retrying or treating them as training truth.
4. On success, VARYN builds a **deterministic report directly from the
   observed fields**, not arbitrary free-form LLM prose.
5. If the owner enabled "Save a hashed evidence receipt" before running,
   VARYN stores a digest-backed *successful factual match* in the local
   LearningKernel. Identical observations of the same repository are
   deduplicated. Raw user goals, response text, raw logs, and credentials
   are not stored in the outcome row.
6. If the owner enabled use of an existing learned skill, a bounded skill
   excerpt is included as explicitly untrusted reference context in the
   exact first and second AI request previews. This option defaults OFF.

The receipt is evidence of *agreement with the approved tool observation*,
**not** independent truth verification against GitHub, proof that the
free-form model reasoning is correct, or proof of improvement over a
baseline. GitHub's own values are not an independent ground-truth oracle.

## Important limitations

- This validates a narrow read-only public GitHub fact task, not general
  browsing, coding, research, arbitrary text or autonomous task completion.
- A model choosing a direct finish without a tool may complete without
  verified public facts. That path DOES NOT issue a learning receipt.
- The callback enabling outcome recording is **trusted host code**, not
  authentication. Directly exposing it as a remote model tool would break
  this trust boundary.
- No skill proposal or promotion is automatic from these raw receipts.
  The VerifiedReflectionWorker still requires at least two independent
  successful outcomes with declassified lessons and protected evaluation
  cases. Repeated identical facts cannot count as two lessons.
- Stored skill bodies in SQLite are plaintext. Existing learned skill
  retrieval requires explicit permission to send the excerpt to the
  external model; exact outgoing text must be reviewed.
- Verification failure is recorded in the journal as
  "verification_failed", not "completed". No background retries.
- Encrypted cross-device storage, secure provider account acceptance,
  private GitHub access, and model-weight training are not provided.

## Tests

Run all three suites without provider/network credentials:

    python -m unittest discover -s tests -p 'test_grounded_learning_bridge.py' -v
    python -m unittest discover -s tests -p 'test_agent_execution_loop.py' -v
    python -m unittest discover -s tests -p 'test_verified_reflection.py' -v

The dedicated CI workflow runs new tests on Ubuntu and Windows, plus
Windows native consumer Tk smoke. Passing these proves deterministic
contracts, not live account connectivity or real-world accuracy.

## Follow-on

Build a trusted, independently validated task-result evaluator to produce
declassified learning lessons. Then schedule small budgeted reflection jobs,
evaluate candidates against withheld cases, roll back on regressions, and
measure whether repeated production tasks actually improve. Do not silently
promote a skill from a single fact match.

This PR is stacked on PR #5; no change to main or stable releases.
