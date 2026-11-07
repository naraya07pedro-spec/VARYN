# Owner-gated agent execution loop (incremental development stage)

This milestone wires three existing pieces into one usable **library-level**
workflow: the UniversalGateway model request, PublicGithubToolGateway
read-only tool, and a new metadata-only SQLite recovery journal.

## Execution contract

- The host supplies a bounded goal and selects the OpenRouter or DeepSeek
  model from an existing verified-price registry. A FAKE model is available
  for existing local simulation but will not produce executable JSON intents.
- Fresh owner-host review occurs **before each model request**.
- The model returns strict JSON only: one public-repository metadata read
  request or a final answer. Additional fields and unknown actions are
  rejected.
- Each public metadata read requires a separate consent switch and an
  independent digest-bound owner decision. Existing PublicGithubToolGateway
  restrictions prevent arbitrary URLs, redirects, local files, writes, or
  private repository access.
- The public result is **not sent to the model by default**. The owner must
  enable public metadata upload and review the exact second prompt.
- At most two model calls and one read-only GitHub call can occur.
- A journal records state transitions **before uncertain actions**; it stores
  only a hashed goal and random ID. Restart marks uncertain work as needing
  review/reconciliation, and does not auto-replay anything.
- Optional submit_verified_result bridges a completed run into the previous
  LearningKernel only after an independent trusted host confirms success.

## Boundaries and honest limitations

This is **not yet connected to the Windows chat GUI** and does not run when
VARYN is closed. It does not install a background daemon, train model weights,
create skills automatically, enable shell commands, modify repositories,
use Gmail, deploy applications, or access private owner data.

Callbacks are trusted caller assertions, not identity authentication.
They MUST be provided by owner-controlled GUI or trusted host code, never
by the model, a remote HTTP client, or text from tools.
The locally stored journal is not encrypted; no user content is persisted.
Model request price ceilings use estimates and do not control real bills.
The public GitHub result may be processed by a provider only after opt-in.
A user's success assertion must not be confused with independent verification.

## Verification

The focused Ubuntu and Windows CI job executes these commands:

- python -m py_compile varyn/agent_execution_loop.py varyn/agent_loop_journal.py
- python -m unittest discover -s tests -p test_agent_execution_loop.py -v
- python -m unittest discover -s tests -p test_learning_kernel.py -v

All tests use deterministic local transports, not actual account credentials
or live GitHub requests. CI green validates protocol and state transitions,
not live end-user acceptance.

## Next stages

1. Expose the loop through trusted owner desktop controls with exact previews.
2. Implement independent completion receipts with task status and factual
   evaluation, then selectively retrieve versioned skills during tasks.
3. Add opt-in reflection, candidate generation, offline comparison, shadow
   tests, rollback and a budgeted scheduler.

Existing original PR #1 and LearningKernel PR #2 remain unmerged and isolated.
